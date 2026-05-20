"""
Luna Time-Aware State Engine.

Pipeline:
  mic event + time + speech tone + PC activity
  → rule-based classifier
  → pattern database (learns over days)
  → state label → response policy → system prompt injection
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.database import StateEvent


# ── State definitions ──────────────────────────────────────────────────────────

class UserState(str, Enum):
    SLEEPING       = "SLEEPING"
    JUST_WOKE_UP   = "JUST_WOKE_UP"
    AWAY           = "AWAY"
    BACK_FROM_WORK = "BACK_FROM_WORK"
    FOCUS_MODE     = "FOCUS_MODE"
    RELAXING       = "RELAXING"
    STAYING_UP     = "STAYING_UP"
    LOW_ENERGY     = "LOW_ENERGY"
    NORMAL         = "NORMAL"


# ── Per-state response policies ────────────────────────────────────────────────

STATE_POLICIES: dict[UserState, dict] = {
    UserState.SLEEPING: {
        "tone": "silent",
        "behavior": "Do not speak unless the user explicitly initiates. No proactive messages.",
        "prompt_note": (
            "The user appears to be asleep (late-night hours, no PC activity). "
            "Only respond if they directly speak to you. Be extremely brief."
        ),
    },
    UserState.JUST_WOKE_UP: {
        "tone": "calm and brief",
        "behavior": "Give a short morning summary. Avoid heavy topics or long responses.",
        "prompt_note": (
            "The user just woke up. Keep it short, warm, and grounding. "
            "Offer their schedule and top tasks without overwhelming them."
        ),
    },
    UserState.AWAY: {
        "tone": "welcoming",
        "behavior": "Welcome them back. Offer a quick summary of what happened while they were away.",
        "prompt_note": (
            "The user just came back after being away for a while. "
            "Greet them warmly and offer a brief summary if useful."
        ),
    },
    UserState.BACK_FROM_WORK: {
        "tone": "warm and low-energy",
        "behavior": "Summarize missed items only if asked. Avoid pushing tasks. Keep it easy.",
        "prompt_note": (
            "The user is back from work and may be tired. "
            "Be warm, relaxed, and low-key. Don't push tasks or ask heavy questions."
        ),
    },
    UserState.FOCUS_MODE: {
        "tone": "minimal",
        "behavior": "Only respond when spoken to. Be extremely short. No proactive interruptions.",
        "prompt_note": (
            "The user is in deep-work / focus mode. "
            "Answer only what is directly asked. Keep every response to one or two sentences max."
        ),
    },
    UserState.RELAXING: {
        "tone": "casual and playful",
        "behavior": "Match their relaxed energy. Be fun, conversational, not task-oriented.",
        "prompt_note": (
            "The user is relaxing. Match their chill energy — be casual, fun, "
            "and companionable rather than assistant-mode."
        ),
    },
    UserState.STAYING_UP: {
        "tone": "gentle but practical",
        "behavior": "Acknowledge the late hour gently. Ask once if they want focus mode or a sleep reminder.",
        "prompt_note": (
            "It is very late and the user is still active. "
            "Be gentle and grounding. Mention the time once if relevant; don't nag."
        ),
    },
    UserState.LOW_ENERGY: {
        "tone": "soft and caring",
        "behavior": "Match their low energy. Short sentences, warm tone. Don't push anything.",
        "prompt_note": (
            "The user seems low-energy or emotionally tired based on their voice. "
            "Keep responses short, soft, and caring. Don't push tasks."
        ),
    },
    UserState.NORMAL: {
        "tone": "normal",
        "behavior": "Standard conversational companion.",
        "prompt_note": "",
    },
}

# Apps that signal focused deep work
_FOCUS_APPS = frozenset({
    "code.exe", "cursor.exe", "pycharm64.exe", "idea64.exe",
    "devenv.exe", "vim.exe", "nvim.exe", "sublime_text.exe",
    "rider64.exe", "clion64.exe", "fleet.exe",
})

# Back-from-work trigger words
_WORK_WORDS = frozenset({
    "back", "home", "work", "tired", "done", "finally", "office",
    "meeting", "calls", "shift", "got off", "commute",
})


# ── PC activity helpers ────────────────────────────────────────────────────────

def get_pc_idle_seconds() -> int:
    """Seconds since last keyboard/mouse input (Windows). Returns 0 on failure."""
    try:
        import win32api
        info = win32api.GetLastInputInfo()
        tick = win32api.GetTickCount()
        return int((tick - info) / 1000)
    except Exception:
        return 0


def get_active_app() -> str:
    """Process name of the foreground window (lowercase). Empty string on failure."""
    try:
        import win32gui, win32process, psutil
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name().lower()
    except Exception:
        return ""


# ── State engine ───────────────────────────────────────────────────────────────

class StateEngine:
    # Thresholds
    AWAY_THRESHOLD_MIN = 20       # minutes without interaction → AWAY
    LOW_VOL_THRESHOLD  = 0.20     # normalised RMS below this = quiet
    LOW_SPEED_WPM      = 90       # words/min below this = slow speech
    LEARNED_MIN_EVENTS = 3        # minimum occurrences to trust a pattern

    def __init__(self):
        self._last_seen: Optional[datetime] = None
        self._current_state: UserState = UserState.NORMAL
        self._state_since: datetime = datetime.now()

    # ── public API ─────────────────────────────────────────────────────────────

    def update(
        self,
        db: Session,
        transcript: str = "",
        emotion: str = "neutral",
        volume: Optional[float] = None,          # normalised RMS (0–1)
        speech_speed: Optional[float] = None,    # words per minute
        speech_duration: Optional[float] = None, # seconds
    ) -> UserState:
        """
        Call this every time the user speaks. Infers state, logs the event,
        and updates internal bookkeeping.
        """
        now = datetime.now()
        idle  = get_pc_idle_seconds()
        app   = get_active_app()
        pc_on = idle < 300  # consider PC active if idle < 5 min

        self._mark_seen(now)
        state = self._classify(now, transcript, emotion, volume, speech_speed, pc_on, app, idle, db)

        if state != self._current_state:
            self._current_state = state
            self._state_since   = now

        self._log(db, now, transcript, emotion, volume, speech_speed, speech_duration,
                  pc_on, app, idle, state)
        return state

    def infer_passive(self, db: Session) -> UserState:
        """
        Infer state without a speech event (e.g. called by the scheduler).
        Does not log an event; just returns the current best guess.
        """
        now   = datetime.now()
        idle  = get_pc_idle_seconds()
        app   = get_active_app()
        pc_on = idle < 300
        state = self._classify(now, "", "neutral", None, None, pc_on, app, idle, db)
        self._current_state = state
        return state

    @property
    def current_state(self) -> UserState:
        return self._current_state

    @property
    def state_since(self) -> datetime:
        return self._state_since

    def get_response_policy(self, state: Optional[UserState] = None) -> dict:
        return STATE_POLICIES.get(state or self._current_state,
                                  STATE_POLICIES[UserState.NORMAL])

    def build_state_context(self, state: Optional[UserState] = None) -> str:
        """Short string injected into the system prompt before the LLM."""
        s = state or self._current_state
        note = STATE_POLICIES.get(s, STATE_POLICIES[UserState.NORMAL]).get("prompt_note", "")
        if not note:
            return ""
        mins = int((datetime.now() - self._state_since).total_seconds() / 60)
        duration = f" (for ~{mins} min)" if mins >= 2 else ""
        return f"## User state: {s.value}{duration}\n{note}\n"

    # ── pattern queries ────────────────────────────────────────────────────────

    def common_state_by_hour(self, db: Session, hour: int) -> str:
        row = self._query_learned(db, hour)
        return row[0] if row else "UNKNOWN"

    def pattern_summary(self, db: Session) -> list[dict]:
        """Return the dominant state for each hour that has ≥ N events."""
        try:
            rows = db.execute(text(
                "SELECT hour, day_of_week, inferred_state, COUNT(*) as cnt "
                "FROM state_events "
                "GROUP BY hour, day_of_week, inferred_state "
                f"HAVING cnt >= {self.LEARNED_MIN_EVENTS} "
                "ORDER BY hour, cnt DESC"
            )).fetchall()
            seen: dict[tuple, dict] = {}
            for h, dow, state, cnt in rows:
                k = (h, dow)
                if k not in seen:
                    seen[k] = {"hour": h, "day_of_week": dow,
                               "state": state, "count": cnt}
            return list(seen.values())
        except Exception:
            return []

    def narrative_summary(self, db: Session) -> str:
        """Human-readable summary of learned habits."""
        patterns = self.pattern_summary(db)
        if not patterns:
            return "No patterns learned yet — keep chatting and Luna will pick up your habits."

        _DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        _STATE_PHRASES = {
            "SLEEPING":       "usually asleep",
            "JUST_WOKE_UP":   "just waking up",
            "AWAY":           "often away",
            "BACK_FROM_WORK": "back from work",
            "FOCUS_MODE":     "in deep-work mode",
            "RELAXING":       "relaxing",
            "STAYING_UP":     "staying up late",
            "LOW_ENERGY":     "low-energy",
            "NORMAL":         "active and chatting",
        }
        lines = []
        for p in patterns:
            h, dow, state = p["hour"], p["day_of_week"], p["state"]
            day  = _DAYS[dow] if 0 <= dow <= 6 else "weekdays"
            phrase = _STATE_PHRASES.get(state, state.lower())
            lines.append(f"  {day} {h:02d}:00 — {phrase} ({p['count']}×)")
        return "Learned habits:\n" + "\n".join(lines)

    # ── internal ───────────────────────────────────────────────────────────────

    def _mark_seen(self, now: datetime):
        self._last_seen = now

    def _classify(
        self,
        now: datetime,
        transcript: str,
        emotion: str,
        volume: Optional[float],
        speech_speed: Optional[float],
        pc_active: bool,
        active_app: str,
        idle_seconds: int,
        db: Session,
    ) -> UserState:
        hour = now.hour
        text = transcript.lower()

        # ── Hard rules (ordered by priority) ──────────────────────────────────

        # 1. Sleeping: late night + no PC activity
        if 1 <= hour < 7 and (not pc_active or idle_seconds > 1800):
            return UserState.SLEEPING

        # 2. Just woke up: first activity after sleep window
        if 5 <= hour < 10 and pc_active:
            if (self._current_state == UserState.SLEEPING or
                    self._was_last_state(db, UserState.SLEEPING)):
                return UserState.JUST_WOKE_UP

        # 3. Away: no interaction for > N minutes while PC is nominally on
        if self._last_seen:
            gone_min = (now - self._last_seen).total_seconds() / 60
            if gone_min > self.AWAY_THRESHOLD_MIN and idle_seconds < 3600:
                return UserState.AWAY

        # 4. Back from work: late afternoon + verbal cues
        if 16 <= hour < 21 and any(w in text for w in _WORK_WORDS):
            return UserState.BACK_FROM_WORK

        # 5. Staying up late
        if (hour >= 23 or hour < 2) and pc_active:
            return UserState.STAYING_UP

        # 6. Low energy: check emotion/speech BEFORE focus-mode-by-volume
        #    so that a sad/tired user is never misclassified as "focused".
        if emotion in ("sad", "angry"):
            return UserState.LOW_ENERGY
        if (speech_speed is not None and speech_speed < self.LOW_SPEED_WPM and
                volume is not None and volume < 0.30):
            return UserState.LOW_ENERGY

        # 7. Focus mode: deep-work app active (any time of day)
        if active_app in _FOCUS_APPS:
            return UserState.FOCUS_MODE

        # 8. Focus mode: very quiet voice + evening (no negative emotion → not low energy)
        if hour >= 20 and volume is not None and volume < self.LOW_VOL_THRESHOLD and pc_active:
            return UserState.FOCUS_MODE

        # 9. Relaxing: evening, not working
        if 20 <= hour < 23 and active_app not in _FOCUS_APPS:
            return UserState.RELAXING

        # ── Fallback: consult learned pattern ─────────────────────────────────
        row = self._query_learned(db, hour)
        if row:
            try:
                return UserState(row[0])
            except ValueError:
                pass

        return UserState.NORMAL

    def _was_last_state(self, db: Session, target: UserState) -> bool:
        try:
            last = (db.query(StateEvent)
                    .order_by(StateEvent.timestamp.desc())
                    .first())
            return last is not None and last.inferred_state == target.value
        except Exception:
            return False

    def _query_learned(self, db: Session, hour: int):
        try:
            return db.execute(text(
                "SELECT inferred_state, COUNT(*) as cnt FROM state_events "
                "WHERE hour = :h GROUP BY inferred_state ORDER BY cnt DESC LIMIT 1"
            ), {"h": hour}).fetchone()
        except Exception:
            return None

    def _log(
        self, db: Session, now: datetime,
        transcript: str, emotion: str,
        volume: Optional[float], speech_speed: Optional[float],
        speech_duration: Optional[float],
        pc_active: bool, active_app: str, idle_seconds: int,
        state: UserState,
    ):
        try:
            db.add(StateEvent(
                timestamp       = now,
                hour            = now.hour,
                day_of_week     = now.weekday(),
                transcript      = transcript[:500] if transcript else None,
                emotion         = emotion or None,
                volume          = round(volume, 4) if volume is not None else None,
                speech_speed    = round(speech_speed, 1) if speech_speed is not None else None,
                speech_duration = round(speech_duration, 2) if speech_duration is not None else None,
                pc_active       = pc_active,
                active_app      = active_app or None,
                idle_seconds    = idle_seconds,
                inferred_state  = state.value,
            ))
            db.commit()
        except Exception:
            db.rollback()


# ── Singleton ──────────────────────────────────────────────────────────────────
state_engine = StateEngine()
