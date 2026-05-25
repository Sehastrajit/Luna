import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import httpx

from backend.config import settings

VISION_MODEL    = "moondream"
CACHE_TTL       = 120   # seconds before current frame is stale
SUMMARY_EVERY   = 300   # regenerate session summary every 5 min
LOG_MAXLEN      = 30    # keep last 30 observations in memory

_Q_ACTIVITY = "What is the person in this image doing, and what are they wearing or using?"
_Q_MOOD     = "How does this person look — happy, tired, focused, stressed, or neutral? Are they sitting or standing?"

_SUMMARY_SYSTEM = "You summarise visual observations of a person over time. Be concise and factual."
_SUMMARY_PROMPT = """\
Webcam snapshots of a person over the past session (oldest first):

{observations}

Write 2-3 sentences covering: what they have been doing, their mood/energy trend, \
and any notable changes in activity or posture. Present tense, factual, no filler."""


@dataclass
class Observation:
    raw: str
    ts: float = field(default_factory=time.time)

    def age_str(self) -> str:
        age = time.time() - self.ts
        if age < 90:   return "just now"
        if age < 3600: return f"{int(age / 60)}m ago"
        h = int(age / 3600)
        m = int((age % 3600) / 60)
        return f"{h}h {m}m ago" if m else f"{h}h ago"


@dataclass
class VisualContext:
    raw:        str   = ""
    history:    str   = ""   # LLM-generated session summary
    captured_at: float = field(default_factory=time.time)

    def is_stale(self) -> bool:
        return time.time() - self.captured_at > CACHE_TTL

    def as_prompt_text(self) -> str:
        parts = []
        if self.raw:
            parts.append(f"Right now: {self.raw}")
        if self.history:
            parts.append(f"Session so far: {self.history}")
        return "\n".join(parts)


# ── Module-level state ────────────────────────────────────────────────────────
_cached:           Optional[VisualContext] = None
_obs_log:          deque[Observation]      = deque(maxlen=LOG_MAXLEN)
_session_summary:  str   = ""
_last_summary_at:  float = 0.0
_prev_fingerprint: str   = ""
_retry_after:      float = 0.0   # backoff until after a 404 (model not installed)


def _safe_log(msg: str):
    print(msg.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def _fingerprint(image_b64: str) -> str:
    """Quick scene fingerprint — sample every 400th char of the b64 string."""
    return hashlib.md5(image_b64[::400].encode()).hexdigest()


async def _refresh_summary():
    """Regenerate the session summary from the observation log (rate-limited)."""
    global _session_summary, _last_summary_at
    if time.time() - _last_summary_at < SUMMARY_EVERY:
        return
    if len(_obs_log) < 3:
        return
    obs_text = "\n".join(f"[{o.age_str()}] {o.raw}" for o in _obs_log)
    from backend.services.llm import ollama
    try:
        summary = await ollama.complete(
            _SUMMARY_PROMPT.format(observations=obs_text),
            system=_SUMMARY_SYSTEM,
            temperature=0.2,
        )
        _session_summary = summary.strip()
        _last_summary_at = time.time()
        _safe_log(f"[vision] summary -> {_session_summary[:150]}")
    except Exception as e:
        _safe_log(f"[vision] summary failed: {e}")


async def _moondream_ask(client: httpx.AsyncClient, question: str, image_b64: str) -> str:
    r = await client.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": VISION_MODEL,
            "prompt": question,
            "images": [image_b64],
            "stream": False,
            "options": {"num_predict": 150, "temperature": 0.2},
        },
    )
    r.raise_for_status()
    return r.json().get("response", "").strip()


async def analyze_frame(image_b64: str) -> VisualContext:
    global _cached, _prev_fingerprint, _retry_after

    # Skip silently if moondream returned 404 recently (model not pulled)
    if time.time() < _retry_after:
        return _cached or VisualContext()

    # Skip moondream if the scene hasn't meaningfully changed
    fp = _fingerprint(image_b64)
    if fp == _prev_fingerprint and _cached and not _cached.is_stale():
        return _cached

    # Sequential — moondream is single-threaded on GPU; parallel requests time out.
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=45.0, write=10.0, pool=5.0)
        ) as client:
            ans_activity = await _moondream_ask(client, _Q_ACTIVITY, image_b64)
            ans_mood     = await _moondream_ask(client, _Q_MOOD,     image_b64)
        raw = f"{ans_activity}. {ans_mood}".strip(". ")
        if not raw:
            _safe_log("[vision] moondream returned empty — skipping cache update")
            return _cached or VisualContext()
    except Exception as e:
        if "404" in str(e):
            _retry_after = time.time() + 30  # 30s backoff after model-not-found
            _safe_log("[vision] moondream not found — run: ollama pull moondream  (retrying in 30s)")
        else:
            _safe_log(f"[vision] moondream failed: {e}")
        return _cached or VisualContext()

    # Only lock in the fingerprint after a successful response so that a
    # failed/empty moondream call doesn't permanently suppress retries.
    _prev_fingerprint = fp
    _safe_log(f"[vision] -> {raw[:300]}")

    # Append to rolling log and maybe refresh summary
    _obs_log.append(Observation(raw=raw))
    await _refresh_summary()

    ctx = VisualContext(raw=raw, history=_session_summary, captured_at=time.time())
    _cached = ctx
    return ctx


def get_visual_context() -> Optional[VisualContext]:
    if _cached and not _cached.is_stale():
        return _cached
    return None


def reset_retry() -> None:
    """Clear the model-not-found backoff so the next frame triggers immediately."""
    global _retry_after
    _retry_after = 0.0
    _safe_log("[vision] retry backoff cleared")


def get_observation_log() -> list[dict]:
    """Return the full observation history (for debug / UI display)."""
    return [{"raw": o.raw, "age": o.age_str(), "ts": o.ts} for o in _obs_log]
