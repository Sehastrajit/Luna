from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings
from backend.models.database import init_db, Base, engine
from backend.services.activity_tracker import Activity
from backend.services.scheduler import luna_scheduler
from backend.routers import chat, memory, calendar, system, voice as voice_router, spotify as spotify_router, state as state_router, train as train_router, sleep as sleep_router, vision as vision_router, luna as luna_router, agent as agent_router
from backend.processes.registry import start_lifecycle_processes, stop_lifecycle_processes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB (creates all tables including Activity)
    Base.metadata.create_all(bind=engine)
    init_db()
    luna_scheduler.start()
    start_lifecycle_processes()
    yield
    luna_scheduler.stop()
    stop_lifecycle_processes()


app = FastAPI(
    title="L.U.N.A.",
    description="Large Unified Nexus Mind AI",
    version="1.0.0",
    lifespan=lifespan,
)

class APIKeyMiddleware(BaseHTTPMiddleware):
    _SKIP = {"/api/system/health", "/api/auth/check", "/api/spotify/callback"}

    async def dispatch(self, request: Request, call_next):
        key = settings.luna_api_key
        if not key:
            return await call_next(request)
        path = request.url.path
        if request.method == "OPTIONS":
            return await call_next(request)
        # Always allow health check + static assets + the SPA shell
        if path in self._SKIP or not path.startswith("/api/"):
            return await call_next(request)
        provided = (
            request.headers.get("X-Luna-Key")
            or request.query_params.get("key")
        )
        if provided != key:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Luna-Key", "X-Voice-Emotion", "X-Volume", "X-Speech-Speed", "X-Speech-Duration"],
)

@app.get("/api/auth/check")
def auth_check(request: Request):
    """Returns whether auth is enabled and validates a key if provided."""
    key = settings.luna_api_key
    if not key:
        return {"auth_required": False}
    provided = (
        request.headers.get("X-Luna-Key")
        or request.query_params.get("key")
    )
    return {"auth_required": True, "valid": provided == key}


# Routers
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(calendar.router)
app.include_router(system.router)
app.include_router(voice_router.router)
app.include_router(spotify_router.router)
app.include_router(state_router.router)
app.include_router(train_router.router)
app.include_router(sleep_router.router)
app.include_router(vision_router.router)
app.include_router(luna_router.router)
app.include_router(agent_router.router)

# Serve React frontend (production build)
frontend_dist = Path(settings.frontend_dist)
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = frontend_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"detail": "Frontend not built. Run: cd frontend && npm run build"}
