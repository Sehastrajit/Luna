"""Command detection and parsing — intent detection, bracket command parsing, execution."""
import re
from sqlalchemy.orm import Session


# ── Coding request detection ──────────────────────────────────────────────────

_CODING_PATTERNS = [
    r"\b(write|create|generate|build|implement|make)\b.{0,70}\b(function|class|method|component|module|script|api|endpoint|algorithm|program)\b",
    r"\b(in|using|with)\s+(python|javascript|typescript|tsx?|rust|go|java|c\+\+|cpp|c#|csharp|ruby|php|swift|kotlin|sql|bash|shell|powershell|react|vue|django|flask|fastapi|express|node)\b",
    r"\b(debug|fix|refactor|optimize|review|unit.?test)\b.{0,60}\b(code|function|class|script|file|this|it)\b",
    r"\b(explain|what does|how does)\b.{0,60}\b(this code|this function|this class|this method|this script)\b",
    r"```",
    r"\b(write|give me|show me|make me)\b.{0,40}\b(code|snippet|example|implementation)\b",
    r"\b(how (do|to|can) (i|you))\b.{0,60}\b(implement|code|write|build|program)\b",
]


def is_coding_request(message: str) -> bool:
    lower = message.lower()
    return any(re.search(p, lower) for p in _CODING_PATTERNS)


# ── Direct intent parsers (no LLM needed) ────────────────────────────────────

def parse_user_launch_request(message: str) -> str | None:
    text = " ".join(message.lower().strip().split())
    patterns = [
        r"^(?:please\s+)?(?:open|launch|start|run)\s+(.+)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:open|launch|start|run)\s+(.+)$",
        r"^(?:i\s+want\s+you\s+to|i\s+need\s+you\s+to)\s+(?:open|launch|start|run)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        app_name = match.group(1).strip(" .?!")
        app_name = re.sub(r"\s+(?:for me|please)$", "", app_name).strip()
        if app_name and len(app_name) <= 80:
            return app_name
    return None


def parse_user_map_request(message: str) -> dict | None:
    text = " ".join(message.lower().strip().split()).strip(" .?!")
    text = re.sub(r"^(?:hey luna|luna)[, ]+", "", text).strip()

    close_patterns = [
        r"^(?:please\s+)?(?:close|hide|dismiss|exit)\s+(?:the\s+)?map$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:close|hide|dismiss|exit)\s+(?:the\s+)?map$",
    ]
    if any(re.match(p, text) for p in close_patterns):
        return {"action": "close"}

    open_patterns = [
        r"^(?:please\s+)?(?:bring up|pull up|open|show|display|launch)\s+(?:the\s+)?map$",
        r"^(?:please\s+)?(?:bring up|pull up|open|show|display|launch)\s+(?:the\s+)?(?:usa|us|america|united states)\s+map$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:bring up|pull up|open|show|display|launch)\s+(?:the\s+)?map$",
        r"^(?:show|display)\s+my\s+location$",
        r"^(?:where am i|where am i right now)$",
        r"^my location$",
    ]
    if any(re.match(p, text) for p in open_patterns):
        return {"action": "open"}

    text = re.sub(r"^(?:now\s+)?(?:can|could|would)\s+you\s+(?:please\s+)?", "", text).strip()
    route_patterns = [
        r"^(?:get\s+)?directions?\s+to\s+(.+)$",
        r"^(?:navigate|navigation)\s+to\s+(.+)$",
        r"^(?:how\s+do\s+i\s+(?:get|reach)\s+to\s+|how\s+to\s+(?:get|reach)\s+to\s+)(.+)$",
        r"^(?:route|routing)\s+to\s+(.+)$",
        r"^(?:take\s+me\s+to|go\s+to)\s+(.+)\s+on\s+(?:the\s+)?map$",
        r"^(?:show\s+(?:me\s+)?(?:the\s+)?(?:way|route)\s+to)\s+(.+)$",
        r"^how\s+(?:do\s+i\s+|to\s+)?(?:get|reach|go)\s+there(?:\s+from\s+here)?$",
        r"^how\s+(?:do\s+i\s+|to\s+)?(?:get|reach)\s+(?:to\s+)?(?:it|that|there)$",
    ]
    for p in route_patterns:
        m = re.match(p, text)
        if m:
            query = m.group(1).strip(" .?!")
            if query and len(query) <= 120:
                return {"action": "route", "query": query}

    text = re.sub(r"^(?:now\s+)?(?:can|could|would)\s+you\s+(?:please\s+)?", "", text).strip()
    where_is_patterns = [
        r"^where\s+is\s+(.+)$",
        r"^where(?:'s|\s+is)\s+(?:the\s+)?(.+)$",
    ]
    for p in where_is_patterns:
        m = re.match(p, text)
        if m:
            query = m.group(1).strip(" .?!")
            if query and len(query) <= 120:
                return {"action": "route", "query": query}

    search_patterns = [
        r"^(?:search|find|look\s+up|show\s+me)\s+(.+?)\s+on\s+(?:the\s+)?map$",
        r"^(?:search|find|look\s+up)\s+(.+?)\s+(?:near\s+(?:me|here)|nearby)$",
        r"^(?:where\s+is\s+the\s+nearest?)\s+(.+)$",
        r"^(?:find\s+(?:a|the|some|me\s+a|me\s+the|me\s+some|me\s+)\s*)(.+?)\s+(?:near\s+(?:me|here)|nearby|close\s+by)$",
        r"^(?:any\s+)(.+?)\s+(?:near\s+(?:me|here)|nearby)$",
        r"^(?:show\s+me\s+)(.+?)\s+(?:near\s+(?:me|here)|nearby|close\s+by)$",
        r"^(?:map\s+search\s+(?:for\s+)?)(.+)$",
        r"^(.+?)\s+(?:near\s+(?:me|here)|nearby)$",
    ]
    for p in search_patterns:
        m = re.match(p, text)
        if m:
            query = m.group(1).strip(" .?!")
            if query and len(query) <= 120:
                return {"action": "search", "query": query}
    return None


def parse_user_spotify_request(message: str, current_track: dict | None = None) -> dict | None:
    text = " ".join(message.lower().strip().split()).strip(" .?!")
    if not text:
        return None
    text = re.sub(r"^(?:hey luna|luna)[, ]+", "", text).strip()
    text = re.sub(r"\b(?:on spotify|from spotify)\b", "", text).strip()
    text = re.sub(r"\s+", " ", text)

    if text in {
        "pause", "pause music", "pause song", "pause track",
        "pause the music", "pause the song", "pause spotify",
        "stop music", "stop the music", "stop spotify",
    }:
        return {"action": "pause"}

    if text in {
        "next", "next song", "next track", "skip", "skip song", "skip track",
        "skip this", "skip this song", "skip this track",
    }:
        return {"action": "next"}

    if text in {
        "previous", "prev", "last song", "previous song", "previous track",
        "go back", "back one", "go to previous song", "go to the previous song",
    }:
        return {"action": "prev"}

    if text in {
        "resume", "resume music", "resume the music", "resume spotify",
        "resume song", "resume the song", "resume track", "resume the track",
        "resume playback", "resume it", "unpause", "unpause music",
        "unpause the music", "unpause song", "unpause the song",
        "play", "play music", "play the music", "play spotify",
        "play some music", "start music", "start the music",
        "continue", "continue music", "continue the music",
        "continue song", "continue the song", "keep playing",
    }:
        return {"action": "play", "query": None}

    if text in {"replay", "play it again", "play that again", "run it back", "restart this song"}:
        if current_track:
            return {"action": "play", "query": f"{current_track['title']} {current_track['artist']}"}
        return {"action": "play", "query": None}

    queue_patterns = [
        r"^(?:please\s+)?(?:queue up|queue)\s+(.+)$",
        r"^(?:please\s+)?(?:add)\s+(.+?)\s+(?:to|into|in)\s+(?:the\s+)?queue$",
        r"^(?:please\s+)?(?:add)\s+(.+?)\s+(?:next|up next)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:queue up|queue)\s+(.+)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:add)\s+(.+?)\s+(?:to|into|in)\s+(?:the\s+)?queue$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:add)\s+(.+?)\s+(?:next|up next)$",
    ]
    for pattern in queue_patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        query = match.group(1).strip(" .?!")
        query = re.sub(r"^(?:the song|song|track|music)\s+", "", query).strip()
        query = re.sub(r"\s+(?:for me|please|right now|now)$", "", query).strip()
        if query and len(query) <= 120:
            return {"action": "queue", "query": query}

    lead_in = (
        r"(?:please\s+)?"
        r"(?:(?:can|could|would)\s+you\s+(?:please\s+)?|"
        r"(?:i\s+want\s+you\s+to|i\s+need\s+you\s+to|i\s+wanna|i\s+want\s+to)\s+)?"
    )
    play_verbs = (
        r"let'?s listen to|i want to hear|i wanna hear|start playing|"
        r"play me|put on|put some|throw on|turn on|listen to|"
        r"play|put|start"
    )
    patterns = [
        rf"^{lead_in}(?:{play_verbs})\s+(.+)$",
        r"^i(?:'| a)?m in the mood for\s+(.+)$",
        r"^some\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        query = match.group(1).strip(" .?!")
        query = re.sub(r"^(?:the song|song|track|music)\s+", "", query).strip()
        query = re.sub(r"\s+(?:for me|please|right now|now)$", "", query).strip()
        if query in {"music", "some music", "spotify", "a song", "song", "track"}:
            query = ""
        if len(query) <= 120:
            return {"action": "play", "query": query or None}
    return None


def extract_direct_research_query(message: str) -> str | None:
    """Return a query when the user explicitly asks for research/citations."""
    text = (message or "").strip()
    if not text:
        return None
    wants_research = re.search(
        r"\b(research|investigate|source-backed|sources?|references?|citations?|citings?|sitations?)\b",
        text, flags=re.IGNORECASE,
    )
    if not wants_research:
        return None
    query = re.sub(
        r"^\s*(please\s+)?(can you\s+|could you\s+|would you\s+)?"
        r"(research|investigate)\b\s+(?:on|about)\s+",
        "", text, flags=re.IGNORECASE,
    )
    query = re.sub(
        r"^\s*(please\s+)?(can you\s+|could you\s+|would you\s+)?"
        r"(research|investigate|look up|search for|find out about|find out)\b\s*",
        "", query, flags=re.IGNORECASE,
    )
    query = re.sub(
        r"\b(and\s+)?(include|show|add|give|provide|cite|citing|with)\s+(the\s+)?"
        r"(citations?|citings?|sitations?|references?|sources?)\b.*$",
        "", query, flags=re.IGNORECASE,
    )
    query = re.sub(
        r"\b(with|including)\s+(citations?|citings?|sitations?|references?|sources?)\b.*$",
        "", query, flags=re.IGNORECASE,
    )
    query = query.strip(" .?!:;-")
    if len(query) < 3:
        query = text
    return query


# ── Away detection ────────────────────────────────────────────────────────────

_AWAY_TRIGGERS = frozenset({
    "leaving", "i'm leaving", "im leaving", "heading out", "going out",
    "going to work", "brb", "be right back", "be back", "gotta go", "got to go",
    "gotta run", "got to run", "see you later", "see ya", "i'll be back",
    "ill be back", "stepping out", "going home", "going to the", "i'm out",
    "im out", "i'm going", "im going", "on my way out", "out for a bit",
    "running errands", "going for a walk", "going to get",
    "going to bed", "going to sleep", "heading to bed", "heading to sleep",
    "off to bed", "off to sleep", "goodnight", "good night", "gonna sleep",
    "gonna go to bed", "time to sleep", "time to go to bed", "hitting the bed",
    "hitting the sack", "calling it a night",
})

_HEDGE_WORDS = frozenset({
    "thinking", "think", "considering", "might", "may", "maybe", "perhaps",
    "probably", "wondering", "wonder", "not sure", "kind of", "kinda",
    "sort of", "sorta", "planning", "plan", "want to", "wanna", "would",
    "should", "could", "feel like", "feel like going",
})

_FAREWELL_PHRASES = frozenset({
    "sleep well", "rest well", "good night", "goodnight", "sweet dreams",
    "night night", "rest up", "get some rest", "have a good sleep",
})


def user_is_leaving(msg: str) -> bool:
    lower = msg.lower().strip()
    for phrase in _AWAY_TRIGGERS:
        if phrase not in lower:
            continue
        idx = lower.find(phrase)
        before = lower[:idx]
        if any(h in before for h in _HEDGE_WORDS):
            continue
        return True
    return False


def response_is_farewell(response: str) -> bool:
    lower = response.lower()
    return any(p in lower for p in _FAREWELL_PHRASES)


# ── Bracket command parsing ───────────────────────────────────────────────────

_BROWSE_BLOCK = re.compile(
    r"(weather\.com|wttr\.in|open-meteo|wunderground|weather\.gov"
    r"|openweathermap|accuweather|forecast\.io|darksky"
    r"|stooq\.com|finance\.yahoo|marketwatch|bloomberg\.com|cnbc\.com/quotes"
    r"|tradingview\.com|investing\.com|barchart\.com"
    r"|coinmarketcap|coingecko|cryptocompare)", re.IGNORECASE
)


def parse_commands(response: str, user_message: str = "") -> list[dict]:
    """Extract embedded action commands from Luna's response."""
    commands: list[dict] = []

    def _emit_away(msg: str, resp: str):
        _bedtime_words = frozenset({"bed", "sleep", "night", "nap"})
        is_bedtime = any(w in msg.lower() for w in _bedtime_words) or response_is_farewell(resp)
        commands.append({"type": "away", "action": "on", "label": "bedtime" if is_bedtime else "away"})

    from backend.config import settings as _cfg
    if _cfg.luna_variant == "personal":
        has_away_bracket = bool(re.search(r'\[AWAY\]', response))
        has_away_literal = bool(re.search(r'(?<!\[)\bAWAY\b(?!\s*])', response))
        if has_away_bracket or has_away_literal:
            if not user_message or user_is_leaving(user_message) or response_is_farewell(response):
                _emit_away(user_message, response)
        elif user_message and user_is_leaving(user_message):
            _emit_away(user_message, response)

    for match in re.finditer(r"\[BROWSE:([^\]]+)\]", response):
        url = match.group(1).strip()
        if not _BROWSE_BLOCK.search(url):
            commands.append({"type": "browse", "url": url})

    for match in re.finditer(r"\[MAP:([^\]]*)\]", response):
        raw = match.group(1).strip()
        lower = raw.lower()
        if lower.startswith("search:"):
            query = raw[7:].strip()
            if query:
                commands.append({"type": "map", "action": "search", "query": query})
        elif lower.startswith("route:"):
            query = raw[6:].strip()
            if query:
                commands.append({"type": "map", "action": "route", "query": query})
        elif lower == "close":
            commands.append({"type": "map", "action": "close"})
        else:
            commands.append({"type": "map", "action": "open"})

    for match in re.finditer(r"\[SPOTIFY:([^\]]*)\]", response):
        raw_query = match.group(1).strip()
        if raw_query.lower().startswith("queue "):
            commands.append({"type": "spotify_queue", "query": raw_query[6:].strip()})
        else:
            commands.append({"type": "spotify", "query": raw_query})

    for match in re.finditer(r"\[LAUNCH:([^\]]+)\]", response):
        commands.append({"type": "launch", "app": match.group(1).strip()})

    for match in re.finditer(r"\[WIDGET:([^|\]]+)\|([^|\]]+)\|([^\]]+)\]", response):
        commands.append({
            "type": "widget",
            "kind": match.group(1).strip(),
            "title": match.group(2).strip(),
            "body": match.group(3).strip(),
        })

    for match in re.finditer(r"\[TASK:([^|]+)\|?([^|]*)\|?([^\]]*)\]", response):
        commands.append({
            "type": "task",
            "title": match.group(1).strip(),
            "due": match.group(2).strip() or None,
            "priority": match.group(3).strip() or "medium",
        })

    for match in re.finditer(r"\[EVENT:([^|]+)\|([^|]+)\|?([^\]]*)\]", response):
        commands.append({
            "type": "event",
            "title": match.group(1).strip(),
            "datetime": match.group(2).strip(),
            "duration": match.group(3).strip() or "60",
        })

    return commands


def execute_commands(commands: list[dict], db: Session, conversation_id: int) -> None:
    """Execute parsed bracket action commands."""
    import os
    from datetime import datetime
    from backend.services.app_launcher import launch_app
    from backend.models.database import Task, CalendarEvent

    for cmd in commands:
        try:
            if cmd["type"] == "away":
                from backend.services.away_state import set_away
                set_away(True, label=cmd.get("label", "away"))

            elif cmd["type"] == "browse":
                url = cmd.get("url", "")
                if url.startswith("http"):
                    os.startfile(url)

            elif cmd["type"] == "map":
                pass

            elif cmd["type"] == "spotify":
                from backend.services.spotify import spotify_service
                spotify_service.play(cmd.get("query") or None)

            elif cmd["type"] == "spotify_queue":
                from backend.services.spotify import spotify_service
                spotify_service.queue(cmd.get("query") or "")

            elif cmd["type"] == "launch":
                launch_app(cmd["app"])

            elif cmd["type"] == "task":
                due = None
                if cmd.get("due"):
                    try:
                        due = datetime.fromisoformat(cmd["due"])
                    except Exception:
                        pass
                task = Task(title=cmd["title"], due_date=due, priority=cmd.get("priority", "medium"))
                db.add(task)

            elif cmd["type"] == "event":
                try:
                    dt = datetime.fromisoformat(cmd["datetime"])
                    duration = int(cmd.get("duration", 60))
                    end_dt = dt.replace(minute=dt.minute + duration) if duration else None
                    event = CalendarEvent(title=cmd["title"], start_datetime=dt, end_datetime=end_dt)
                    db.add(event)
                except Exception:
                    pass
        except Exception:
            pass

    db.commit()
