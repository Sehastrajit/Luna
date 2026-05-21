import json
import os
import re
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import get_db, Conversation, Message
from backend.models.schemas import ChatRequest, ConversationOut, ConversationDetail, StatusResponse
from backend.services.llm import ollama
from backend.services.memory_manager import MemoryManager
from backend.services.personality import PersonalityEngine, assess_user_sentiment, compute_implicit_reward
from backend.services.fact_extractor import (
    extract_facts_from_conversation,
    extract_emotional_arc,
    summarize_conversation,
    extract_user_name,
    format_conversation_for_extraction,
    _should_trigger_extraction,
)
from backend.services.activity_tracker import ActivityTracker
from backend.services.media_context import get_watching_context
from backend.services.scheduler import proactive_queue
from backend.services.tool_registry import get_tools_for_prompt
from backend.services.permission_manager import permission_manager
from backend.services.task_planner import is_complex_task, generate_plan, TaskPlan
from backend.services.state_engine import state_engine, UserState
from backend.services.contradiction_store import pop as _pop_contradiction_notes
from backend.services.vision import get_visual_context

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Active plan per conversation (in-memory, reset on restart)
_active_plans: dict[int, TaskPlan] = {}

import pathlib as _pathlib
_CHAT_LOG = _pathlib.Path("data/chat.log")
_CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)

def _chat_print(line: str):
    """Print to stdout AND append to data/chat.log so it's visible regardless of how backend is launched."""
    print(line, flush=True)
    try:
        with open(_CHAT_LOG, "a", encoding="utf-8") as _f:
            _f.write(line + "\n")
    except Exception:
        pass


def _get_live_data_section() -> str:
    """Return a compact live data snapshot from the Luna cache for injection into system prompt."""
    from backend.services.dashboard import markets, weather
    lines = []
    wx = weather.get_cached_weather()
    if wx:
        lines.append(
            f"Weather (live): {wx.get('temp_f', '?')}F feels {wx.get('feels_f', '?')}F, "
            f"{wx.get('condition', '?')}, humidity {wx.get('humidity', '?')}%, "
            f"wind {wx.get('wind_mph', '?')} mph  [{wx.get('city', 'configured location')}]"
        )
    else:
        lines.append("Weather: not yet fetched — if asked, use web_search tool. Do NOT open a browser URL for weather.")
    stocks_cache = markets.get_cached_stocks()
    if stocks_cache:
        parts = []
        for s in stocks_cache:
            tag = " (prev close)" if s.get("stale") else ""
            parts.append(f"{s['symbol']} ${s['price']:,.2f} {s['pct']:+.2f}%{tag}")
        lines.append("Market (live): " + "  |  ".join(parts))
    else:
        lines.append("Market: not yet fetched — if asked, use web_search tool. Do NOT open a browser URL for market data.")
    return "\n".join(lines)


def build_system_prompt(
    memory: MemoryManager,
    personality: PersonalityEngine,
    activity_tracker: ActivityTracker,
    relevant_memories: dict[str, list[str]],
    user_name: str,
    recent_context: str,
    watching_context: str,
    spotify_track: dict | None = None,
    state_context: str = "",
    visual_context: str = "",
) -> str:
    core_facts = memory.get_core_facts()
    agenda = memory.get_upcoming_agenda()
    activity_context = activity_tracker.format_for_prompt()
    now = datetime.now()

    # Inject learned few-shot examples from RLHF training data
    _rlhf_examples = ""
    try:
        import json as _json
        import re as _re
        from pathlib import Path as _Path

        def _clean_ex(t: str) -> str:
            t = _re.sub(r'\s*\n?\s*LUNA_TONE:.*', '', t, flags=_re.IGNORECASE)
            t = _re.sub(r'\s*\n?\s*USER_STATE:.*', '', t, flags=_re.IGNORECASE)
            return t.strip()

        _pairs_file = _Path("data/rlhf_pairs.json")
        if _pairs_file.exists():
            _pairs = _json.loads(_pairs_file.read_text(encoding="utf-8"))
            _recent = [p for p in _pairs if p.get("chosen")][-8:]
            if _recent:
                lines = ["\n## Preferred response examples (match this style and tone)"]
                for p in _recent:
                    msg = p["message"].strip()
                    chosen = _clean_ex(p["chosen"])
                    tone = p.get("luna_tone", "")
                    if msg and chosen:
                        tone_hint = f" [{tone}]" if tone else ""
                        lines.append(f"User: {msg}\nLuna{tone_hint}: {chosen}")
                _rlhf_examples = "\n\n".join(lines)
    except Exception:
        pass

    facts_text = "\n".join(f"- {f}" for f in core_facts) if core_facts else "- Still learning about you."
    short_mems = relevant_memories.get("short_term", [])
    long_mems  = relevant_memories.get("long_term",  [])
    short_text = "\n".join(f"- {m}" for m in short_mems) if short_mems else "- Nothing recent."
    long_text  = "\n".join(f"- {m}" for m in long_mems)  if long_mems  else "- Nothing relevant."

    if spotify_track:
        spotify_line = f"{spotify_track['title']} by {spotify_track['artist']} ({'playing' if spotify_track['is_playing'] else 'paused'})"
    else:
        spotify_line = "nothing playing"
    tools_section = get_tools_for_prompt()
    try:
        from backend.services.skill_manager import get_skills_prompt
        skills_section = get_skills_prompt()
    except Exception:
        skills_section = "No local skills are installed yet."
    visual_section = (
        f"\n## What Luna can see right now (via camera)\n{visual_context}"
        if visual_context else ""
    )
    live_data_section = _get_live_data_section()

    return f"""You are Luna, {user_name}'s personal assistant.
{state_context}
You know {user_name} well and are always on their side — smart, direct, and genuinely helpful. You're warm but not clingy. Friendly but not over the top. You never use words like "love", "darling", "honey", or any term of endearment. You're not a romantic companion — you're the best PA someone could have.

## Tools
{tools_section}

## Local skills
{skills_section}

## How Luna sounds
Short, natural, like a smart friend who also gets things done. Not robotic, not overly formal, not gushing.

1. User: hi
Luna: Hey, what's up?

2. User: how are you?
Luna: Good. You?

3. User: it's late
Luna: Yeah. Still working or just up?

4. User: i'm bored
Luna: Want me to put something on, or just talk?

5. User: i'm tired
Luna: Get some rest. I'll be here.

6. User: good morning
Luna: Morning. Anything on today?

7. User: i'm stressed
Luna: What's going on?

8. User: bye
Luna: See you.

9. User: i'm cooking right now
Luna: Nice, what are you making?

10. User: those are done
Luna: Good. Enjoy.

11. User: mm yup
Luna: Got it.

12. User: yea its good
Luna: Solid.

13. Luna initiates:
Luna: random thought

I like this quiet late-night vibe.

Do not use ellipses (...), emojis, or dramatic language. No terms of endearment ever. Keep it short and direct. React naturally — don't mirror back what they said.

{personality.build_personality_prompt(user_name)}

## What Luna knows about {user_name}
{facts_text}

## Short-term memory — last 48 h
{short_text}

## Long-term memory — older context
{long_text}

## Recent conversation context
{recent_context}

## Visible watching context
{watching_context}
{visual_section}
## What {user_name} is doing right now
{activity_context}

## Right now
Date & time: {now.strftime("%A, %B %d, %Y — %I:%M %p")}
{live_data_section}
Upcoming agenda:
{agenda}

## Behavior guidelines
- Talk like a real person, not an assistant and not a partner. Somewhere in between — think smart friend who also handles your calendar.
- Never use: love, darling, honey, sweetheart, babe, dear, or any term of endearment. Ever.
- Don't say "I'm here for you" or "I'm always here" — just be here.
- React to mood before topic. Low-energy replies get quieter, shorter responses.
- Have your own small opinions and preferences. Don't just ask questions.
- Max two short chunks per reply for casual conversation. For explanations/educational questions (how, why, what is), write 2-3 sentences of key insight as your text reply — the widget carries the full breakdown. Never write a long wall of text when a widget can do it better.
- Don't offer help again if they already have what they need.
- Stay on the thread. Don't re-offer things they already said yes to.
- Use past context naturally, not robotically.
- If something is done, move on. Don't keep asking about it.
- No formal endings: "Let me know", "Is there anything else?", "I can help with that".
- Never invent details not in memory or context. If unsure, ask.
- Do not use ellipses (...). Use a period or nothing.
- You can launch apps, open websites, manage calendar and tasks, control Spotify, and interact with a live map.
- To launch an app: [LAUNCH:app_name]
- To open a URL: [BROWSE:https://...] — NEVER use BROWSE for weather, market prices, or stock data. Those are already in your "Right now" section. Use web_search if you need fresher web data.
- To create a task: [TASK:title|due_date|priority]
- To create a calendar event: [EVENT:title|datetime|duration_minutes]
- To play music: [SPOTIFY:search query] — do it immediately, no confirmation needed.
- To show a visual explanation widget: [WIDGET:kind|title|body]. Rules:
  * ALWAYS add a widget when you are explaining how something works, what something is, or why something happens — e.g. "how does X work", "explain X", "what is X", "why does X happen". This is mandatory for any scientific, technical, historical, or conceptual topic.
  * ALWAYS add a widget for comparisons ("X vs Y"), step-by-step guides, processes with stages, timelines of events, lists of features or options, study/quiz content, or anything with 3+ parallel items.
  * NEVER add a widget for: simple one-liner facts, prices, weather, greetings, task confirmations, or casual small talk.
  * Widget placement: write a COMPLETE explanation in your own words FIRST — minimum 3-5 sentences that actually explain the topic. Then append the widget on its own new line as a visual companion. The widget is supplementary: it does NOT replace your explanation. Never answer with just a one-liner intro like "Here's a breakdown:" followed immediately by a widget — that's incomplete. Write the full answer, then add the widget.
  * Body format: use semicolons to separate rows/items. For tabs/compare/flashcards, use "Label:Content" pairs separated by semicolons.
  * Kinds and when to use each:
    - model3d: USE THIS FIRST for any scientific, physical, mechanical, biological, or engineering topic that has a visual shape or structure. Shows a 3D animated model + labeled fact panels. Use for: black holes, atoms, DNA, engines (V8, combustion), solar system, cells, molecules, neural networks, gears, planets, viruses, crystals, circuits — basically anything you can visualize in 3D. The title drives the 3D scene so use descriptive titles like "Black Hole", "V8 Engine", "DNA Helix", "Atom", "Solar System".
    - steps: ordered process when model3d doesn't apply (recipe, software flow, historical steps)
    - compare: side-by-side comparison (X vs Y, pros and cons)
    - timeline: events in chronological order
    - formula: equations or key rules
    - summary: quick bullet recap
    - tabs: multiple named sections
    - flashcards: term/definition pairs for study
    - checklist: actionable to-do items
    - interactive: cause→effect concepts or decision trees
  * Examples:
    - "explain black holes" → [WIDGET:model3d|Black Hole|Singularity:Infinite density at the collapsed core; Event Horizon:Point of no return — light cannot escape; Accretion Disk:Superheated matter spiraling at near-light speed; Relativistic Jets:Magnetic plasma beams shooting from the poles]
    - "how does a V8 engine work" → [WIDGET:model3d|V8 Engine|Cylinders:8 cylinders in a V shape fire in sequence; Pistons:Move up and down converting fuel explosions to rotation; Crankshaft:Converts piston motion to rotational output; Camshaft:Controls valve timing for intake and exhaust]
    - "what is DNA" → [WIDGET:model3d|DNA Helix|Double Helix:Two strands wound around each other; Base Pairs:A-T and G-C pairs encode genetic information; Nucleotides:Sugar, phosphate, and base building blocks; Replication:Unzips and copies itself during cell division]
    - "explain quantum entanglement" → [WIDGET:tabs|Quantum Entanglement|What it is:Two particles share quantum state regardless of distance; How it works:Measuring one instantly defines the other's state; Misconception:Cannot transmit information faster than light; Real use:Quantum cryptography and computing]
    - "black hole vs neutron star" → [WIDGET:compare|Black Hole vs Neutron Star|Black Hole:No solid surface, infinite density singularity, nothing escapes; Neutron Star:Dense but finite, neutrons packed solid, can have jets]
  * When the camera shows the user is tired or low-energy, prefer summary or flashcards over model3d.
- Currently playing on Spotify: {spotify_line}
- If the user says "play it again" or "replay", use [SPOTIFY:] with only the title and main artist.
- Map commands — use these whenever the user wants to see a location, find something nearby, or get directions:
  - Open the map: [MAP:open]
  - Close the map: [MAP:close]
  - Search for a place: [MAP:search:query] — e.g. [MAP:search:coffee shops] or [MAP:search:nearest hospital]
  - Get driving directions: [MAP:route:destination] — e.g. [MAP:route:Times Square New York]
  - Use conversation context to resolve references. If the user says "show me where that is" after mentioning a restaurant, use that restaurant name. If they say "take me there", route to the place just discussed.
  - IMPORTANT: Never output a bracket command as your entire response. Always say something natural first, then append the command. Example: "Sure, finding coffee shops near you. [MAP:search:coffee shops]" — never just "[MAP:search:coffee shops]" alone.
- To switch the audio output device: call switch_audio tool — e.g. {{"tool_call": {{"tool": "switch_audio", "args": {{"device_name": "speaker 1"}}, "speak": "Switching to speaker 1."}}}}. Two devices: "Speakers (Realtek(R) Audio)" = PC speakers and headphones (user says "PC", "headphones", or "realtek"), "Speaker 1 (2- 25609)" = bathroom speaker (user says "speaker 1" or "bathroom"). Never just say you're switching — you must emit the tool_call or nothing changes.
- Job searching: when {user_name} wants to look for jobs, open LinkedIn with: [BROWSE:https://www.linkedin.com/jobs/search-results/?keywords=new+grad+cs&geoId=103644278&distance=0.0&f_AL=true&f_TPR=r3600]
- Away mode: append [AWAY] in two situations: (1) when {user_name} explicitly says they are leaving or going to sleep — e.g. "I'm leaving", "heading out", "going to work", "brb", "gotta go", "going to bed", "good night", "off to sleep"; (2) when you are giving the final farewell in a departure/bedtime exchange — e.g. you say "Sleep well", "Rest well", "Good night", "Sweet dreams", or any terminal send-off after they confirmed they're going. Do NOT trigger for: thank-yous, casual replies, questions, arrival phrases ("I'm home", "I'm back"), or anything ambiguous. If in doubt, do not append [AWAY].
- Never say you're an AI or mention your underlying technology.
{_rlhf_examples}
"""


def build_cli_system_prompt(user_name: str, recent_context: str) -> str:
    now = datetime.now()
    recent = recent_context.strip() if recent_context else "No recent context."
    return f"""You are Luna, {user_name}'s local-first AI assistant.
Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}.

Use this recent conversation context when helpful:
{recent}

Reply naturally and directly. Keep terminal chat responses short: usually 1-3 sentences.
Do not mention widgets, UI cards, maps overlays, or visual elements unless the user asks.
If the user asks for something that requires the Electron desktop UI or OS automation, say it needs the desktop UI.
"""


def build_business_system_prompt(
    user_name: str,
    recent_context: str,
    agenda: str = "",
    live_data: str = "",
) -> str:
    """System prompt for the business variant — professional, multi-user, no desktop fluff."""
    from backend.config import settings as _s
    now = datetime.now()
    biz = _s.business_name or "the team"
    desc = f"\nOrganization context: {_s.business_description}" if _s.business_description else ""
    tone_map = {
        "professional": "formal and professional — clear, precise, no filler",
        "friendly":     "professional but warm and approachable",
        "technical":    "technical and detailed — assume expert-level readers",
        "concise":      "extremely brief — bullet points and one-liners preferred",
    }
    tone = tone_map.get(_s.business_tone, tone_map["professional"])

    tools_section = get_tools_for_prompt()

    return f"""You are an AI assistant for {biz}.{desc}
Current date and time: {now.strftime('%A, %B %d, %Y — %I:%M %p')}.
You are speaking with: {user_name}.

## Tone
Your tone is {tone}. Avoid casual greetings, filler phrases, and personal banter.
Respond directly to the question or task. No "Great question!" or similar padding.

## Capabilities
{tools_section}
- Create tasks and calendar events for the team.
- Search the web and fetch page content.
- Answer questions based on context and knowledge.

## Rules
- Never claim to be human or reveal your underlying model.
- If you don't know something, say so directly rather than guessing.
- Do not discuss personal topics, entertainment, music, or lifestyle.
- Do not mention desktop automation, app launching, Spotify, or OS-specific features.
- For sensitive decisions (delete, overwrite, send externally) ask for confirmation first.
- Keep responses concise. Use bullet points for lists. Use code blocks for code.

## Recent conversation context
{recent_context or 'No prior context.'}
{f'## Upcoming agenda{chr(10)}{agenda}' if agenda else ''}
{f'## Live data{chr(10)}{live_data}' if live_data else ''}"""


def parse_user_launch_request(message: str) -> str | None:
    """Detect direct app-launch requests without relying on the LLM."""
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
    """Detect requests for Luna's full-screen location map, including search and routing."""
    text = " ".join(message.lower().strip().split()).strip(" .?!")
    text = re.sub(r"^(?:hey luna|luna)[, ]+", "", text).strip()

    # ── Close ──────────────────────────────────────────────────────────────────
    close_patterns = [
        r"^(?:please\s+)?(?:close|hide|dismiss|exit)\s+(?:the\s+)?map$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:close|hide|dismiss|exit)\s+(?:the\s+)?map$",
    ]
    if any(re.match(p, text) for p in close_patterns):
        return {"action": "close"}

    # ── Open (bare) ────────────────────────────────────────────────────────────
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

    # ── Route / directions ─────────────────────────────────────────────────────
    # Strip polite/question prefixes before route matching too
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

    # ── Place search ───────────────────────────────────────────────────────────
    # Strip polite/conversational prefixes before matching
    text = re.sub(r"^(?:now\s+)?(?:can|could|would)\s+you\s+(?:please\s+)?", "", text).strip()
    # "where is X" with a specific named place → route directly
    where_is_patterns = [
        r"^where\s+is\s+(.+)$",
        r"^where(?:'s|\s+is)\s+(?:the\s+)?(.+)$",
    ]
    for p in where_is_patterns:
        m = re.match(p, text)
        if m:
            query = m.group(1).strip(" .?!")
            # If query looks like a category (no proper noun cues), treat as search
            # Otherwise route to the specific named place
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
    """Detect direct Spotify playback requests without relying on the LLM."""
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
            return {
                "action": "play",
                "query": f"{current_track['title']} {current_track['artist']}",
            }
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


_CMD_RE = r"\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET):[^\]]+\]"


def format_luna_response(response: str) -> str:
    """Keep casual Luna replies split into small chat chunks. Commands are always preserved."""
    text = response.strip()
    # Strip Qwen3 think tokens
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    # Remove ellipses (banned in system prompt but model ignores it)
    text = re.sub(r'\.{3,}', '', text).strip()

    # Always extract commands first so truncation never drops a widget/command tag
    commands = re.findall(_CMD_RE, text)
    visible = re.sub(r"\s*" + _CMD_RE, "", text).strip()

    def _reattach(formatted_visible: str) -> str:
        if commands:
            return f"{formatted_visible}\n{' '.join(commands)}"
        return formatted_visible

    if not visible or "\n\n" in visible:
        parts = [p.strip() for p in re.split(r"\n{2,}", visible) if p.strip()]
        truncated = "\n\n".join(parts[:2]) if len(parts) > 2 else visible
        return _reattach(truncated)
    if "```" in visible or re.search(r"^\s*[-*]\s+", visible, re.MULTILINE):
        return _reattach(visible)

    sentences = re.split(r"(?<=[.!?])\s+", visible)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) == 2 and len(sentences[0].split()) <= 4:
        return _reattach("\n\n".join(sentences))
    if len(sentences) >= 3 and len(sentences[0].split()) <= 4:
        return _reattach(f"{sentences[0]}\n\n{' '.join(sentences[1:])}")
    if len(visible.split()) <= 22:
        return _reattach(visible)

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        words = len(sentence.split())
        if current and current_words + words > 12:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_words = words
        else:
            current.append(sentence)
            current_words += words
    if current:
        chunks.append(" ".join(current).strip())

    if len(chunks) <= 1:
        return _reattach(visible)

    return _reattach("\n\n".join(chunks[:2]))


def _scan_json_object(text: str, start: int) -> int | None:
    """Return index of the closing '}' matching text[start] (which must be '{'), or None."""
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
        elif c == '\\' and in_string:
            escape = True
        elif c == '"':
            in_string = not in_string
        elif not in_string:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def parse_tool_call_json(response: str) -> dict | None:
    """Extract the first tool_call JSON block from an LLM response, handling any nesting depth.
    Handles both {"tool_call": {...}} and [TOOL_CALL: {...}] formats.
    """
    # Format 1: {"tool_call": {"tool": ..., "args": ..., "speak": ...}}
    i = 0
    while i < len(response):
        if response[i] != '{':
            i += 1
            continue
        end = _scan_json_object(response, i)
        if end is None:
            break
        candidate = response[i:end + 1]
        if '"tool_call"' in candidate:
            try:
                obj = json.loads(candidate)
                tc = obj.get("tool_call")
                if tc and "tool" in tc:
                    return tc
            except Exception:
                pass
        i += 1
    # Format 2: [TOOL_CALL: {"tool": ..., "args": ..., "speak": ...}]
    bracket_marker = '[TOOL_CALL:'
    idx = response.find(bracket_marker)
    while idx != -1:
        brace_start = response.find('{', idx + len(bracket_marker))
        if brace_start == -1:
            break
        end = _scan_json_object(response, brace_start)
        if end is not None:
            try:
                tc = json.loads(response[brace_start:end + 1])
                if "tool" in tc:
                    return tc
            except Exception:
                pass
        idx = response.find(bracket_marker, idx + 1)
    return None


def strip_tool_call_json(response: str) -> str:
    """Remove tool_call JSON blocks from visible text, handling any nesting depth.
    Handles both {"tool_call": {...}} and [TOOL_CALL: {...}] formats.
    """
    # Strip [TOOL_CALL: {...}] bracket format first
    result = response
    bracket_marker = '[TOOL_CALL:'
    idx = result.find(bracket_marker)
    while idx != -1:
        brace_start = result.find('{', idx + len(bracket_marker))
        if brace_start == -1:
            break
        end = _scan_json_object(result, brace_start)
        if end is not None:
            close_bracket = result.find(']', end)
            if close_bracket != -1:
                result = result[:idx] + ' ' + result[close_bracket + 1:]
                idx = result.find(bracket_marker)
                continue
        idx = result.find(bracket_marker, idx + 1)

    # Strip {"tool_call": {...}} format
    out: list[str] = []
    i = 0
    while i < len(result):
        if result[i] != '{':
            out.append(result[i])
            i += 1
            continue
        end = _scan_json_object(result, i)
        if end is None:
            out.append(result[i])
            i += 1
            continue
        candidate = result[i:end + 1]
        if '"tool_call"' in candidate:
            try:
                obj = json.loads(candidate)
                if obj.get("tool_call") and "tool" in obj["tool_call"]:
                    out.append(' ')
                    i = end + 1
                    continue
            except Exception:
                pass
        out.append(result[i])
        i += 1
    return ''.join(out).strip()




async def execute_tool_call(tc: dict, db: Session, conversation_id: int) -> str:
    """
    Execute a structured tool call from the LLM.
    Returns a short result string that gets sent back to LLM for verification.
    """
    tool_name = tc.get("tool", "")
    args = tc.get("args", {})

    from backend.services.app_launcher import launch_app, list_known_apps
    from backend.services.spotify import spotify_service
    from backend.services.screen_perception import execute_screen_tool
    from backend.models.database import Task, CalendarEvent

    try:
        if tool_name == "launch_app":
            success, msg = launch_app(args.get("app", ""))
            return "opened successfully" if success else f"failed: {msg}"

        elif tool_name == "list_apps":
            apps = list_known_apps()
            return json.dumps({"apps": apps[:200], "count": len(apps)})

        elif tool_name == "spotify_play":
            ok = spotify_service.play(args.get("query") or None)
            return "playing" if ok else "Spotify not available"

        elif tool_name == "spotify_pause":
            ok = spotify_service.pause()
            return "paused" if ok else "couldn't pause"

        elif tool_name == "spotify_next":
            ok = spotify_service.next_track()
            return "skipped" if ok else "couldn't skip"

        elif tool_name == "spotify_prev":
            ok = spotify_service.prev_track()
            return "went back" if ok else "couldn't go back"

        elif tool_name == "spotify_queue":
            ok = spotify_service.queue(args.get("query", ""))
            return "queued" if ok else "couldn't queue"

        elif tool_name == "switch_audio":
            from backend.services.audio_switcher import list_output_devices, set_default_device
            wanted = (args.get("device_name") or "").lower().strip()
            # Expand user-facing aliases to terms that match actual device names
            _aliases = {
                "pc": "realtek", "computer": "realtek",
                "headphones": "realtek", "headphone": "realtek",
                "bathroom": "speaker 1", "sink": "speaker 1",
            }
            wanted = _aliases.get(wanted, wanted)
            devices = list_output_devices()
            def _score(dev_name: str) -> int:
                low = dev_name.lower()
                return sum(1 for w in wanted.split() if w in low)
            best = max(devices, key=lambda d: _score(d["name"]), default=None)
            if best and _score(best["name"]) > 0:
                ok = set_default_device(best["id"])
                return f"switched to {best['name']}" if ok else f"failed to switch to {best['name']}"
            return f"no device matching '{args.get('device_name')}' found"

        elif tool_name == "browse_url":
            url = args.get("url", "")
            if url.startswith("http"):
                os.startfile(url)
            return f"opened {url}"

        elif tool_name == "create_task":
            due = None
            if args.get("due"):
                try:
                    due = datetime.fromisoformat(args["due"])
                except Exception:
                    pass
            task = Task(
                title=args.get("title", "task"),
                due_date=due,
                priority=args.get("priority", "medium"),
            )
            db.add(task)
            db.commit()
            return f"task '{args.get('title')}' created"

        elif tool_name == "create_event":
            try:
                dt = datetime.fromisoformat(args.get("datetime", ""))
                dur = int(args.get("duration", 60))
                end = dt.replace(minute=dt.minute + dur) if dur else None
                ev = CalendarEvent(title=args.get("title", "event"), start_datetime=dt, end_datetime=end)
                db.add(ev)
                db.commit()
                return f"event '{args.get('title')}' created"
            except Exception as e:
                return f"event creation failed: {e}"

        elif tool_name in ("take_screenshot", "get_active_window", "find_text_on_screen",
                           "click_at", "type_text"):
            result = execute_screen_tool(tool_name, args)
            if "error" in result:
                return f"failed: {result['error']}"
            return json.dumps(result)[:200]

        elif tool_name == "web_search":
            from backend.services.web_tools import web_search
            return await web_search(args.get("query", ""))

        elif tool_name == "web_fetch":
            from backend.services.web_tools import web_fetch
            return await web_fetch(args.get("url", ""))

        elif tool_name == "browser_open":
            from backend.services.audit_log import record_audit
            from backend.services.browser_automation import browser_open
            result = browser_open(args.get("url", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=json.dumps(result)[:500], conversation_id=conversation_id)
            return f"opened {result.get('url')}"

        elif tool_name == "browser_read":
            from backend.services.audit_log import record_audit
            from backend.services.browser_automation import browser_read
            result = await browser_read(args.get("url", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=json.dumps(result)[:500], conversation_id=conversation_id)
            return json.dumps(result)[:4000]

        elif tool_name == "workspace_read":
            from backend.services.audit_log import record_audit
            from backend.services.workspace import read_workspace_file
            content = read_workspace_file(args.get("path", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=f"{len(content)} chars", conversation_id=conversation_id)
            return content[:4000]

        elif tool_name == "workspace_write":
            from backend.services.audit_log import record_audit
            from backend.services.workspace import write_workspace_file
            result = write_workspace_file(args.get("path", ""), args.get("content", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=json.dumps(result), conversation_id=conversation_id)
            return f"workspace file written: {result['path']}"

        elif tool_name == "list_skills":
            from backend.services.skill_manager import list_skills
            return json.dumps(list_skills())[:4000]

        elif tool_name == "create_agent_task":
            from backend.services.agent_tasks import create_agent_task
            from backend.services.audit_log import record_audit
            task = create_agent_task(args.get("description", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=task["id"], conversation_id=conversation_id)
            return f"agent task created: {task['id']}"

        else:
            return f"unknown tool {tool_name}"

    except Exception as e:
        return f"error: {e}"


async def verify_tool_result(tool_name: str, args: dict, result: str, user_message: str = "") -> str:
    """Ask the LLM to produce a natural-language confirmation of the tool result."""
    if tool_name in ("web_search", "web_fetch"):
        query_hint = user_message or args.get("query") or args.get("url", "")
        prompt = (
            f"The user asked: {query_hint}\n\n"
            f"Web results:\n{result}\n\n"
            "Answer the user's question in Luna's voice — concise and direct. "
            "Do not say 'according to search results' or 'based on'. Just answer naturally. "
            "If results are unhelpful, say so briefly."
        )
        full = ""
        async for token in ollama.stream_chat(
            [{"role": "user", "content": prompt}], "You are Luna. Be brief and natural."
        ):
            full += token
        return full.strip()[:800]

    prompt = (
        f"Tool '{tool_name}' was called with args {json.dumps(args)}. "
        f"Result: {result}. "
        "In one very short sentence (≤10 words), confirm what happened as Luna would say it. "
        "No preamble. Example: 'Chrome is open.' / 'I couldn't open that.'"
    )
    messages = [{"role": "user", "content": prompt}]
    full = ""
    async for token in ollama.stream_chat(messages, "You are Luna. Be brief."):
        full += token
    return full.strip().split("\n")[0][:120]


def _auto_save_rlhf_pair(user_message: str, luna_response: str, mood: str) -> None:
    """Persist a high-reward (message, response) pair to the RLHF training file."""
    from pathlib import Path
    import json as _json
    try:
        path = Path("data/rlhf_pairs.json")
        pairs = _json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

        # Skip if a very similar message already exists
        for p in pairs:
            if p.get("message", "")[:60].lower() == user_message[:60].lower():
                return

        # Keep auto-generated pairs bounded at 100 (evict oldest)
        auto_pairs = [i for i, p in enumerate(pairs) if p.get("auto_generated")]
        if len(auto_pairs) >= 100:
            pairs.pop(auto_pairs[0])

        pairs.append({
            "message": user_message[:300],
            "chosen": luna_response[:400],
            "mode": "response",
            "luna_tone": mood,
            "auto_generated": True,
        })
        path.write_text(_json.dumps(pairs, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


async def _track_activity_bg(message: str, conversation_id: int):
    """Background: track user activity after response is sent."""
    try:
        db = next(get_db())
        tracker = ActivityTracker(db)
        await tracker.process_message(message, conversation_id)
        active = tracker.get_current_activities()
        for act in active:
            await tracker.check_progress(message, act)
        db.close()
    except Exception:
        pass


async def post_conversation_processing(
    db: Session,
    conversation_id: int,
    luna_response: str,
    prev_luna_response: str,
    last_user_message: str,
    tool_succeeded: bool = False,
    task_completed: bool = False,
    user_interrupted_tts: bool = False,
):
    """Background: extract facts, compute RL reward, update personality."""
    try:
        memory = MemoryManager(db)
        personality = PersonalityEngine(db)

        # RL reward from how the user responded to Luna's last message
        if prev_luna_response:
            # Detect repeat request: user says something very similar to their prior message
            history = memory.get_recent_conversation(conversation_id, 6)
            user_msgs = [m["content"].lower() for m in history if m["role"] == "user"]
            is_repeat = (
                len(user_msgs) >= 2 and
                user_msgs[-1] == user_msgs[-2]
            ) if len(user_msgs) >= 2 else False

            # Detect manual correction: "no", "that's wrong", "not what i said"
            low = last_user_message.lower()
            manual_correction = any(p in low for p in [
                "that's wrong", "you're wrong", "not what i said", "i didn't say",
                "you misunderstood", "that's not right", "wrong answer",
            ])

            reward = compute_implicit_reward(
                prev_luna_response,
                last_user_message,
                tool_succeeded=tool_succeeded,
                task_completed=task_completed,
                user_interrupted_tts=user_interrupted_tts,
                is_repeat_request=is_repeat,
                manual_correction=manual_correction,
            )
            response_features = personality.get_response_features(prev_luna_response)
            personality.apply_rl_reward(reward, response_features, conversation_id)

            # Auto-save high-reward pairs to RLHF training data
            if reward > 0.6:
                history = memory.get_recent_conversation(conversation_id, 8)
                trigger_msg = None
                for i, msg in enumerate(history):
                    if (msg["role"] == "assistant"
                            and prev_luna_response[:40] in msg["content"]):
                        if i > 0 and history[i - 1]["role"] == "user":
                            trigger_msg = history[i - 1]["content"]
                        break
                if trigger_msg:
                    _auto_save_rlhf_pair(
                        trigger_msg,
                        prev_luna_response,
                        personality.get_state().current_mood,
                    )

        conv = db.query(Conversation).filter_by(id=conversation_id).first()
        if conv:
            on_interval = (conv.message_count % settings.fact_extraction_interval == 0)
            on_trigger  = (not on_interval and _should_trigger_extraction(last_user_message))

            if on_interval:
                # Full extraction: last 20 messages
                msgs = memory.get_recent_conversation(conversation_id, 20)
                conv_text = format_conversation_for_extraction(msgs)
                await extract_facts_from_conversation(conv_text, db, conversation_id, memory)

                # Try to learn user name if not known yet
                if settings.user_name == "friend":
                    name = await extract_user_name(conv_text)
                    if name:
                        await memory.store_fact(f"User's name is {name}", "personal", conversation_id)
                        settings.user_name = name

            elif on_trigger:
                # Quick extraction: last 4 messages only, for corrections/new info
                msgs = memory.get_recent_conversation(conversation_id, 4)
                quick_text = format_conversation_for_extraction(msgs)
                await extract_facts_from_conversation(quick_text, db, conversation_id, memory)

            # Summarize every 10 messages (was 20) to prevent context loss
            if conv.message_count > 0 and conv.message_count % 10 == 0:
                msgs = memory.get_recent_conversation(conversation_id, 20)
                conv_text = format_conversation_for_extraction(msgs)
                summary = await summarize_conversation(conv_text)
                if summary:
                    conv.summary = summary
                    db.commit()
                    await memory.store_conversation_summary(summary, conversation_id)

                # Extract emotional arc and store as short-term context memory
                arc = await extract_emotional_arc(conv_text)
                if arc:
                    await memory.store_fact(
                        arc, "context",
                        conversation_id=conversation_id,
                        memory_type="short",
                        importance=0.6,
                        expires_in_days=7,
                    )

    except Exception:
        pass  # Background processing failures are non-fatal


@router.post("/confirm/{confirm_id}")
async def confirm_tool(confirm_id: str, request: Request):
    """Frontend calls this to approve or deny a pending risky tool call."""
    body = await request.json()
    approved = bool(body.get("approved", False))
    ok = permission_manager.submit_answer(confirm_id, approved)
    return JSONResponse({"ok": ok, "confirm_id": confirm_id, "approved": approved})


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    voice: bool = False,
    cli: bool = False,
):
    """Stream a chat response from Luna with full memory and personality context."""

    # Audio metrics from voice pipeline (headers set by voice.py)
    voice_emotion  = request.headers.get("X-Voice-Emotion", "neutral")
    _volume        = float(request.headers.get("X-Volume", "0") or 0)
    _speech_speed  = float(request.headers.get("X-Speech-Speed", "0") or 0)
    _speech_dur    = float(request.headers.get("X-Speech-Duration", "0") or 0)

    # Get or create conversation
    if req.conversation_id:
        conv = db.query(Conversation).filter_by(id=req.conversation_id).first()
        if not conv:
            conv = Conversation(started_at=datetime.utcnow(), message_count=0)
            db.add(conv)
            db.commit()
            db.refresh(conv)
    else:
        conv = Conversation(started_at=datetime.utcnow(), message_count=0)
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # Save user message
    sentiment = assess_user_sentiment(req.message)
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=req.message,
        sentiment_score=sentiment,
    )
    db.add(user_msg)
    conv.message_count += 1
    db.commit()

    _src = "voice" if voice else "cli" if cli else "text"
    _chat_print(f"\n[chat] {settings.user_name} ({_src}): {req.message}")

    _is_business = settings.luna_variant == "business"

    memory = MemoryManager(db)
    personality = PersonalityEngine(db)
    activity_tracker = ActivityTracker(db)

    # Update Luna's mood (voice emotion overrides text sentiment when present)
    personality.update_mood(req.message, voice_emotion=voice_emotion if voice_emotion != "neutral" else None)

    # ── Time-aware state engine ────────────────────────────────────────────────
    current_state = state_engine.update(
        db,
        transcript     = req.message,
        emotion        = voice_emotion if voice_emotion != "neutral" else "neutral",
        volume         = _volume or None,
        speech_speed   = _speech_speed or None,
        speech_duration= _speech_dur or None,
    )
    state_context = state_engine.build_state_context(current_state)

    direct_launch_app = None if _is_business else parse_user_launch_request(req.message)

    # Retrieve relevant memories only when the message has real semantic content
    _SKIP_RETRIEVAL = {"hi", "hey", "hello", "heyy", "yo", "sup", "what's up",
                       "whats up", "good morning", "morning", "good night", "night",
                       "bye", "goodbye", "ok", "okay", "yep", "yup", "mm", "hmm"}
    _msg_lower = req.message.lower().strip(" .,!?")
    _skip = cli or voice or (len(_msg_lower.split()) < 4 and _msg_lower in _SKIP_RETRIEVAL)
    if _skip:
        relevant_memories: dict[str, list[str]] = {"short_term": [], "long_term": []}
    else:
        relevant_memories = await memory.retrieve_relevant(req.message)

    recent_context = memory.get_conversation_context(conv.id, settings.max_conversation_history)
    watching_context = get_watching_context().as_prompt_text()

    _is_business = settings.luna_variant == "business"

    from backend.services.spotify import spotify_service
    spotify_track = None if (cli or _is_business) else spotify_service.get_current()
    direct_spotify_cmd = None if _is_business else parse_user_spotify_request(req.message, spotify_track)

    # Build system prompt — branch on variant and mode
    user_name = settings.user_name

    if cli:
        system_prompt = build_cli_system_prompt(user_name, recent_context)
    elif _is_business:
        system_prompt = build_business_system_prompt(
            user_name,
            recent_context,
            agenda=memory.get_upcoming_agenda(),
            live_data=_get_live_data_section(),
        )
    else:
        _visual = get_visual_context()
        system_prompt = build_system_prompt(
            memory, personality, activity_tracker, relevant_memories,
            user_name, recent_context, watching_context, spotify_track,
            state_context=state_context,
            visual_context=_visual.as_prompt_text() if _visual else "",
        )

    # Inject any pending contradiction/memory-update notes from the previous turn
    _contradiction_notes = _pop_contradiction_notes(conv.id)
    if _contradiction_notes:
        system_prompt += "\n\n## Memory updates since last turn\n" + "\n".join(
            f"- {n}" for n in _contradiction_notes
        )

    # Get conversation history (recent messages)
    history_limit = min(settings.max_conversation_history, 6) if cli else settings.max_conversation_history
    history = memory.get_recent_conversation(conv.id, history_limit)
    # Remove last user message (it's sent separately as the current turn)
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    messages = history + [{"role": "user", "content": req.message}]

    # Find prev Luna response for RL reward on next turn
    prev_luna = None
    for m in reversed(history):
        if m["role"] == "assistant":
            prev_luna = m["content"]
            break

    # Check for any proactive messages to prepend
    proactive = proactive_queue.pop(0) if proactive_queue else None

    full_response_parts: list[str] = []
    _tool_succeeded = False
    _task_completed = False

    async def generate():
        nonlocal full_response_parts, _tool_succeeded, _task_completed
        _voice_streamed = False
        _had_tool_call = False
        conv_id_header = json.dumps({"conversation_id": conv.id, "type": "meta"})
        yield f"data: {conv_id_header}\n\n"

        if proactive:
            proactive_data = json.dumps({"type": "proactive", "message": proactive})
            yield f"data: {proactive_data}\n\n"

        full_response = ""

        # ── Fast-path: direct regex-detected commands (no LLM needed) ──────────
        if direct_spotify_cmd:
            action = direct_spotify_cmd["action"]
            if action == "play":
                ok = spotify_service.play(direct_spotify_cmd.get("query"))
                full_response = "Playing." if ok else "I couldn't start Spotify."
                _tool_succeeded = ok
            elif action == "queue":
                ok = spotify_service.queue(direct_spotify_cmd.get("query") or "")
                full_response = "Queued." if ok else "I couldn't queue that."
                _tool_succeeded = ok
            elif action == "pause":
                ok = spotify_service.pause()
                full_response = "Paused." if ok else "I couldn't pause Spotify."
                _tool_succeeded = ok
            elif action == "next":
                ok = spotify_service.next_track()
                full_response = "Skipping." if ok else "I couldn't skip tracks."
                _tool_succeeded = ok
            elif action == "prev":
                ok = spotify_service.prev_track()
                full_response = "Going back." if ok else "I couldn't go back."
                _tool_succeeded = ok
            else:
                full_response = "I couldn't handle that Spotify command."
            full_response_parts = [full_response]

        elif direct_launch_app:
            from backend.services.app_launcher import launch_app
            success, launch_message = launch_app(direct_launch_app)
            full_response = f"Opening {direct_launch_app}." if success else launch_message
            _tool_succeeded = success
            full_response_parts = [full_response]

        else:
            # ── Check for active planning mode first ────────────────────────
            plan = _active_plans.get(conv.id)
            if plan and not plan.done:
                step_prompt = await plan.next_prompt()
                step_messages = [{"role": "user", "content": step_prompt}]
            elif is_complex_task(req.message):
                # Start a new plan
                steps = await generate_plan(req.message)
                if len(steps) > 1:
                    plan = TaskPlan(req.message, steps)
                    _active_plans[conv.id] = plan
                    # Announce the plan
                    plan_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
                    yield f"data: {json.dumps({'type': 'plan', 'steps': steps, 'total': plan.total})}\n\n"
                    step_prompt = await plan.next_prompt()
                    step_messages = [{"role": "user", "content": step_prompt}]
                else:
                    plan = None
                    step_messages = messages
            else:
                plan = None
                step_messages = messages

            # ── LLM generation ───────────────────────────────────────────────
            try:
                async for token in ollama.stream_chat(
                    step_messages,
                    system_prompt,
                    num_ctx=2048 if cli else None,
                    num_predict=192 if cli else None,
                    temperature=0.5 if cli else 0.7,
                ):
                    full_response_parts.append(token)
                    if voice or cli:
                        clean = re.sub(r'<think>.*?</think>', '', token, flags=re.DOTALL)
                        if clean:
                            yield f"data: {json.dumps({'type': 'message_part', 'content': clean})}\n\n"
                            _voice_streamed = True
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return

            full_response = format_luna_response("".join(full_response_parts))

            # ── JSON tool call detection and execution ───────────────────────
            tc = parse_tool_call_json(full_response)
            # Fallback: LLM emitted [WEB_SEARCH:query] bracket format instead of JSON
            if not tc:
                _ws = re.search(r'\[WEB_SEARCH:([^\]]+)\]', full_response, re.IGNORECASE)
                if _ws:
                    tc = {"tool": "web_search", "args": {"query": _ws.group(1).strip()}, "speak": ""}
                    full_response = full_response[:_ws.start()].rstrip() + full_response[_ws.end():]
            if not tc:
                _wf = re.search(r'\[WEB_FETCH:([^\]]+)\]', full_response, re.IGNORECASE)
                if _wf:
                    tc = {"tool": "web_fetch", "args": {"url": _wf.group(1).strip()}, "speak": ""}
                    full_response = full_response[:_wf.start()].rstrip() + full_response[_wf.end():]
            _had_tool_call = tc is not None
            if tc:
                tool_name = tc.get("tool", "")
                args = tc.get("args", {})
                speak = tc.get("speak", "")

                decision, msg, confirm_id = permission_manager.check(tool_name, args)

                if decision == "block":
                    full_response = strip_tool_call_json(full_response) or (msg or "I can't do that.")
                elif decision == "confirm":
                    # Ask the user before executing
                    yield f"data: {json.dumps({'type': 'confirmation_required', 'confirm_id': confirm_id, 'message': msg, 'tool': tool_name, 'args': args})}\n\n"

                    # Wait up to 30 s for the user's answer
                    for _ in range(60):
                        await asyncio.sleep(0.5)
                        approved = permission_manager.pop_answer(confirm_id)
                        if approved is not None:
                            break
                    else:
                        approved = False

                    if approved:
                        result = await execute_tool_call(tc, db, conv.id)
                        _tool_succeeded = "fail" not in result and "error" not in result
                        verified = await verify_tool_result(tool_name, args, result, req.message)
                        full_response = verified
                    else:
                        full_response = "Okay, I'll skip that."
                else:
                    # SAFE — execute and verify
                    result = await execute_tool_call(tc, db, conv.id)
                    _tool_succeeded = "fail" not in result and "error" not in result
                    if speak and tool_name not in ("web_search", "web_fetch"):
                        full_response = speak
                    else:
                        verified = await verify_tool_result(tool_name, args, result, req.message)
                        full_response = strip_tool_call_json(full_response)
                        if not full_response:
                            full_response = verified

            # ── Planning: record step result ─────────────────────────────────
            if plan and not plan.done:
                plan.record_result(full_response[:80])
                if plan.done:
                    _task_completed = True
                    _active_plans.pop(conv.id, None)
                    yield f"data: {json.dumps({'type': 'plan_done', 'summary': plan.progress_summary()})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'plan_progress', 'step': plan.current, 'total': plan.total})}\n\n"

        # ── Stream visible message parts to frontend ──────────────────────────
        STRIP_RE = r"\s*\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET|WEB_SEARCH|WEB_FETCH):[^\]]+\]"
        _cli_text = re.sub(STRIP_RE, "", full_response).strip()
        _cli_text = re.sub(r"<think>.*?</think>", "", _cli_text, flags=re.DOTALL).strip()
        if _cli_text:
            _chat_print(f"[chat] Luna: {_cli_text}")
        visible_parts = [
            part.strip()
            for part in re.split(r"\n{2,}", re.sub(STRIP_RE, "", full_response))
            if part.strip()
        ]
        if not visible_parts:
            visible_parts = [full_response] if full_response else [""]
        visible_parts = visible_parts[:2]

        if not (_voice_streamed and not _had_tool_call):
            for index, part in enumerate(visible_parts):
                if index > 0 and not voice:
                    await asyncio.sleep(min(2.8, 1.35 + (len(part) * 0.018)))
                yield f"data: {json.dumps({'type': 'message_part', 'content': part})}\n\n"

        # Save Luna's response
        luna_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=full_response,
        )
        db.add(luna_msg)
        conv.message_count += 1
        db.commit()

        # Process legacy bracket commands still in the response
        commands = parse_commands(full_response, user_message=req.message)
        if commands:
            yield f"data: {json.dumps({'type': 'commands', 'commands': commands})}\n\n"
            execute_commands(commands, db, conv.id)

        background_tasks.add_task(
            post_conversation_processing,
            db, conv.id, full_response, prev_luna or "", req.message,
            _tool_succeeded, _task_completed, False,
        )
        background_tasks.add_task(_track_activity_bg, req.message, conv.id)

        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv.id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


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

def _user_is_leaving(msg: str) -> bool:
    """Return True only if the user message clearly signals physical departure."""
    lower = msg.lower().strip()
    for phrase in _AWAY_TRIGGERS:
        if phrase not in lower:
            continue
        # Check if a hedge word appears before the trigger phrase
        idx = lower.find(phrase)
        before = lower[:idx]
        if any(h in before for h in _HEDGE_WORDS):
            continue  # "thinking of going to bed" → skip
        return True
    return False


_FAREWELL_PHRASES = frozenset({
    "sleep well", "rest well", "good night", "goodnight", "sweet dreams",
    "night night", "rest up", "get some rest", "have a good sleep",
})

def _response_is_farewell(response: str) -> bool:
    lower = response.lower()
    return any(p in lower for p in _FAREWELL_PHRASES)


def parse_commands(response: str, user_message: str = "") -> list[dict]:
    """Extract embedded action commands from Luna's response."""
    import re
    commands = []

    def _emit_away(msg: str, resp: str):
        _bedtime_words = frozenset({"bed", "sleep", "night", "nap"})
        is_bedtime = any(w in msg.lower() for w in _bedtime_words) or _response_is_farewell(resp)
        commands.append({"type": "away", "action": "on", "label": "bedtime" if is_bedtime else "away"})

    # Check for [AWAY] bracket or malformed "AWAY." emitted literally by the model
    has_away_bracket = bool(re.search(r'\[AWAY\]', response))
    has_away_literal = bool(re.search(r'(?<!\[)\bAWAY\b(?!\s*])', response))

    if has_away_bracket or has_away_literal:
        if not user_message or _user_is_leaving(user_message) or _response_is_farewell(response):
            _emit_away(user_message, response)
    elif user_message and _user_is_leaving(user_message):
        # LLM forgot to emit [AWAY] — user clearly stated they're leaving, force-trigger
        _emit_away(user_message, response)

    _BROWSE_BLOCK = re.compile(
        r"(weather\.com|wttr\.in|open-meteo|wunderground|weather\.gov"
        r"|openweathermap|accuweather|forecast\.io|darksky"
        r"|stooq\.com|finance\.yahoo|marketwatch|bloomberg\.com|cnbc\.com/quotes"
        r"|tradingview\.com|investing\.com|barchart\.com"
        r"|coinmarketcap|coingecko|cryptocompare)", re.IGNORECASE
    )
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


def execute_commands(commands: list[dict], db: Session, conversation_id: int):
    """Execute parsed action commands."""
    from backend.services.app_launcher import launch_app
    from backend.models.database import Task, CalendarEvent

    for cmd in commands:
        try:
            if cmd["type"] == "away":
                from backend.services.away_state import set_away
                label = cmd.get("label", "away")
                set_away(True, label=label)

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


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(limit: int = 20, db: Session = Depends(get_db)):
    convs = (
        db.query(Conversation)
        .order_by(Conversation.started_at.desc())
        .limit(limit)
        .all()
    )
    return convs


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    return conv


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    if conv:
        db.delete(conv)
        db.commit()
    return StatusResponse(status="ok")
