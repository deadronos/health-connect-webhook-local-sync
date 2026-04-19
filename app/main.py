"""FastAPI application entry point for the Health Connect Webhook Ingest service."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import Settings
from app.routes import analytics, browser_auth, dashboard, debug, health, ingest


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events for the FastAPI application.
    Currently performs no explicit startup/shutdown operations.
    Yields control to the application, then cleans up on shutdown.
    """
    # Startup: verify Convex connection
    yield
    # Shutdown


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Returns:
        A fully configured FastAPI application with middleware, routes, and static files mounted.
    """
    static_dir = Path(__file__).resolve().parent / "static"
    settings = Settings()

    app = FastAPI(
        title="Health Connect Webhook Ingest",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.session_https_only,
    )
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(debug.router)
    app.include_router(analytics.router)
    app.include_router(browser_auth.router)
    app.include_router(dashboard.router)
    return app


app = create_app()