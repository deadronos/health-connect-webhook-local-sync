from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import analytics, dashboard, debug, health, ingest


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify Convex connection
    yield
    # Shutdown


def create_app() -> FastAPI:
    static_dir = Path(__file__).resolve().parent / "static"

    app = FastAPI(
        title="Health Connect Webhook Ingest",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(debug.router)
    app.include_router(analytics.router)
    app.include_router(dashboard.router)
    return app


app = create_app()