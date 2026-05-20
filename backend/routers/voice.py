"""
Voice API — state SSE stream + enable/disable toggle.
"""
import asyncio
import json
import os
import tempfile
from fastapi import APIRouter
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse

from backend.services.voice import voice_service, VoiceState

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Each entry: (event_loop, asyncio.Queue) — one per active SSE client
_subscribers: list[tuple[asyncio.AbstractEventLoop, "asyncio.Queue[object]"]] = []


def _push_state(state: VoiceState):
    """Called from the voice background thread — bridges into each client's event loop."""
    for loop, q in list(_subscribers):
        try:
            loop.call_soon_threadsafe(q.put_nowait, state.value)
        except RuntimeError:
            pass


def _push_quit():
    """Push a quit event to all SSE subscribers."""
    for loop, q in list(_subscribers):
        try:
            loop.call_soon_threadsafe(q.put_nowait, "__quit__")
        except RuntimeError:
            pass


def _push_ui_event(event: dict):
    """Push a UI event to all SSE subscribers."""
    for loop, q in list(_subscribers):
        try:
            loop.call_soon_threadsafe(q.put_nowait, event)
        except RuntimeError:
            pass


voice_service.on_state_change(_push_state)
voice_service.on_quit(_push_quit)
voice_service.on_ui_event(_push_ui_event)


@router.get("/state")
def get_state():
    return {"state": voice_service.state, "enabled": voice_service.enabled}


@router.post("/toggle")
def toggle_voice():
    enabled = voice_service.toggle()
    return {"enabled": enabled, "state": voice_service.state}


@router.post("/away/off")
def away_off():
    from backend.services.away_state import set_away
    set_away(False)
    return {"ok": True}


@router.post("/mobile")
async def mobile_voice(audio: UploadFile = File(...)):
    suffix = ".webm"
    if audio.filename and "." in audio.filename:
        suffix = "." + audio.filename.rsplit(".", 1)[-1].lower()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        audio_path = f.name
        f.write(await audio.read())

    try:
        transcript = voice_service.transcribe_file(audio_path)
        transcript = transcript.strip()
        if not transcript:
            return {"transcript": "", "response": ""}
        response = voice_service.collect_response_text(transcript)
        return {"transcript": transcript, "response": response}
    finally:
        try:
            os.unlink(audio_path)
        except OSError:
            pass


@router.get("/events")
async def voice_events():
    """SSE stream — emits {state} on every voice state change, pings every 25 s."""
    loop = asyncio.get_event_loop()
    q: asyncio.Queue[object] = asyncio.Queue()
    _subscribers.append((loop, q))

    async def stream():
        try:
            # Send current state immediately so the client doesn't start blind
            yield f"data: {json.dumps({'state': voice_service.state.value})}\n\n"
            while True:
                try:
                    state = await asyncio.wait_for(q.get(), timeout=25)
                    if state == "__quit__":
                        yield f"data: {json.dumps({'type': 'quit'})}\n\n"
                    elif isinstance(state, dict):
                        yield f"data: {json.dumps(state)}\n\n"
                    else:
                        yield f"data: {json.dumps({'state': state})}\n\n"
                except asyncio.TimeoutError:
                    yield "data: ping\n\n"
        except Exception:
            pass
        finally:
            _subscribers[:] = [(l, sq) for l, sq in _subscribers if sq is not q]

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
