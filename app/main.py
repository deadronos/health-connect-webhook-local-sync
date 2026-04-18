from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes import ingest, health, debug


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify Convex connection
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="Health Connect Webhook Ingest",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(debug.router)
    return app


app = create_app()