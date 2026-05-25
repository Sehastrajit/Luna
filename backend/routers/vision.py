from fastapi import APIRouter
from pydantic import BaseModel

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
