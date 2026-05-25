"""Bracket command parsing and execution."""
import re
from sqlalchemy.orm import Session
from backend.services.command_parser.away import user_is_leaving, response_is_farewell

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

    for match in re.finditer(r"\[FACE:(on|off)\]", response, re.IGNORECASE):
        commands.append({"type": "face", "action": match.group(1).lower()})

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
