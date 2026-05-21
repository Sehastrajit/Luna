import json
import re
from fastapi import APIRouter, Request
from backend.models.schemas import AppLaunchRequest, StatusResponse
from backend.services.app_launcher import launch_app, list_app_profiles, list_known_apps
from backend.services.media_context import get_watching_context
from backend.services.scheduler import proactive_queue

router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/launch", response_model=StatusResponse)
def launch_application(req: AppLaunchRequest):
    success, message = launch_app(req.name)
    return StatusResponse(status="ok" if success else "error", message=message)


@router.get("/apps")
def get_apps():
    return {"apps": list_known_apps()}


@router.get("/apps/profiles")
def get_app_profiles():
    return list_app_profiles()


@router.get("/watching")
def get_current_watching():
    ctx = get_watching_context()
    return {
        "title": ctx.title,
        "cleaned_title": ctx.cleaned_title,
        "source": ctx.source,
        "confidence": ctx.confidence,
    }


@router.get("/proactive")
def get_proactive_messages():
    msgs = list(proactive_queue)
    proactive_queue.clear()
    return {"messages": msgs}


@router.get("/audio-devices")
def get_audio_devices():
    from backend.services.audio_switcher import list_output_devices, get_default_device_id
    try:
        devices = list_output_devices()
        current = get_default_device_id()
        return {"devices": devices, "current": current}
    except Exception as e:
        return {"devices": [], "current": None, "error": str(e)}


@router.post("/audio-device")
async def set_audio_device(request: Request):
    from backend.services.audio_switcher import set_default_device
    body = await request.json()
    device_id = body.get("device_id", "")
    if not device_id:
        return {"ok": False, "error": "missing device_id"}
    ok = set_default_device(device_id)
    return {"ok": ok}


_SCENE_SYSTEM = (
    "You are a 3D scene designer. Output ONLY valid JSON — no markdown, no explanation, no code fences."
)

_SCENE_PROMPT = """\
Generate a holographic 3D scene spec for: "{topic}"

Build the {topic} from geometric primitives. Each shape represents one key component.
The scene will render as a holographic wireframe — no colors needed.

Output this exact JSON schema:
{{
  "shapes": [
    {{
      "type": "cylinder" | "sphere" | "box" | "torus" | "cone",
      "pos": [x, y, z],
      "label": "Component Name",
      // cylinder: "r": radius(float), "h": height(float), "rot": [rx,ry,rz](degrees, optional)
      // sphere:   "r": radius(float)
      // box:      "w": width(float), "h": height(float), "d": depth(float)
      // torus:    "r": major_radius(float), "tube": tube_radius(float), "rot": [rx,ry,rz](optional)
      // cone:     "r": base_radius(float), "h": height(float)
    }}
  ],
  "animate": "turntable"
}}

Rules:
- 6-12 shapes that together clearly represent {topic}
- pos values MUST be in range -3 to 3 on every axis
- Spatially accurate: parts in correct relative positions
- Labels are the real component names (barrel, cylinder, piston, nucleus, etc.)
- Realistic proportions

Output ONLY the JSON object:"""


@router.get("/scene")
async def generate_scene(topic: str = ""):
    """Generate a holographic 3D scene spec for a given topic using the LLM."""
    if not topic.strip():
        return {"error": "topic required"}
    from backend.services.llm import ollama
    prompt = _SCENE_PROMPT.format(topic=topic)
    try:
        raw = await ollama.complete(prompt, system=_SCENE_SYSTEM, temperature=0.3)
    except Exception as e:
        return {"error": str(e)}

    # Extract JSON even if model added surrounding text
    m = re.search(r'\{[\s\S]*\}', raw)
    if not m:
        return {"error": "LLM did not return JSON", "raw": raw[:300]}
    try:
        spec = json.loads(m.group())
        # Basic validation
        if not isinstance(spec.get("shapes"), list):
            raise ValueError("missing shapes")
        return spec
    except Exception as e:
        return {"error": f"JSON parse failed: {e}", "raw": raw[:300]}


@router.get("/health")
async def health():
    from backend.services.llm import ollama
    available = await ollama.is_available()
    return {
        "status": "ok",
        "llm": available,
        "llm_provider": ollama.provider,
        "ollama": available,
        "model": ollama.model,
    }
