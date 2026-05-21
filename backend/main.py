from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.models.database import init_db, Base, engine
from backend.services.activity_tracker import Activity
from backend.services.scheduler import luna_scheduler
from backend.routers import chat, memory, calendar, system, voice as voice_router, spotify as spotify_router, state as state_router, train as train_router, sleep as sleep_router, vision as vision_router, luna as luna_router, agent as agent_router, channels as channels_router, admin as admin_router
from backend.middleware.rate_limit import RateLimitMiddleware
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

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Voice-Emotion", "X-Volume", "X-Speech-Speed", "X-Speech-Duration"],
)


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
app.include_router(channels_router.router)
app.include_router(admin_router.router)

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
