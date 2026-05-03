from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, research, workspaces
from app.core.config import get_settings
from app.db.base import Base
from app.db.migrations import apply_sqlite_migrations
from app.db.session import engine
from app import models  # noqa: F401


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    apply_sqlite_migrations()
    yield


app = FastAPI(title="Research Companion Agent API", lifespan=lifespan)


@app.middleware("http")
async def disable_caching_for_api(request: Request, call_next):
    """Avoid stale workspace JSON (e.g. missing new `briefs`) after reload in some browsers/proxies."""
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.get("/")
def root():
    """Base URL has no API surface; everything lives under /api and /docs."""
    return {
        "service": app.title,
        "docs": "/docs",
        "health": "/api/health/",
        "workspaces": "/api/workspaces/",
    }


origins = (
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    if settings.node_env == "development"
    else [settings.frontend_url]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(research.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")
app.include_router(workspaces.library_router, prefix="/api")
