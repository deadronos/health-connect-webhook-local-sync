"""Route module exposing sub-routers for the FastAPI application."""

from app.routes import analytics, browser_auth, dashboard, debug, health, ingest

__all__ = ["analytics", "browser_auth", "dashboard", "debug", "health", "ingest"]
