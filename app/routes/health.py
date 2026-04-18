from fastapi import APIRouter
from pydantic import BaseModel

from app.convex_client import ConvexClient
from app.config import Settings

settings = Settings()
client = ConvexClient(
    convex_url=settings.convex_self_hosted_url,
    admin_key=settings.convex_self_hosted_admin_key,
)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    ok: bool
    db: str


@router.get("/healthz", response_model=HealthResponse)
async def healthz():
    health = client.check_db_health()
    return HealthResponse(
        ok=health.get("ok", False),
        db=health.get("db", "unknown"),
    )