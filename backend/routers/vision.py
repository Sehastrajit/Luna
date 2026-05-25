import asyncio
import json

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import settings
from backend.services.vision import analyze_frame, get_visual_context, reset_retry

router = APIRouter(prefix="/api/vision", tags=["vision"])


class FramePayload(BaseModel):
    image: str  # base64-encoded JPEG


@router.post("/frame")
async def receive_frame(payload: FramePayload):
    ctx = await analyze_frame(payload.image)
    return {
        "ok":      True,
        "raw":     ctx.raw,
        "history": ctx.history,
        "captured_at": ctx.captured_at,
    }


@router.post("/reset")
def reset_vision():
    reset_retry()
    return {"ok": True}


@router.get("/context")
def current_context():
    ctx = get_visual_context()
    if ctx and ctx.raw:
        return {
            "active":      True,
            "raw":         ctx.raw,
            "history":     ctx.history,
            "captured_at": ctx.captured_at,
        }
    return {"active": False}


@router.get("/status")
async def vision_status():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            if r.status_code == 200:
                models = r.json().get("models", [])
                installed = any("moondream" in m.get("name", "") for m in models)
                return {"moondream_installed": installed, "ollama_available": True}
    except Exception:
        pass
    return {"moondream_installed": False, "ollama_available": False}


@router.post("/install")
async def install_moondream():
    async def _stream():
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "pull", "moondream",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for raw in proc.stdout:
                text = raw.decode("utf-8", errors="replace").strip()
                if text:
                    yield f"data: {json.dumps({'line': text})}\n\n"
            code = await proc.wait()
            yield f"data: {json.dumps({'done': True, 'ok': code == 0})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")
