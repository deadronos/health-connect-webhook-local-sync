"""Debug endpoints for inspecting recent deliveries and internal state."""

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request, HTTPException

from app.auth import BearerAuth
from app.config import Settings
from app.schemas import DebugResponse, DebugDelivery
from app.convex_client import ConvexClient

settings = Settings()
auth = BearerAuth(token=settings.ingest_token)
client = ConvexClient(
    convex_url=settings.convex_self_hosted_url,
    admin_key=settings.convex_self_hosted_admin_key,
)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/recent", response_model=DebugResponse)
async def debug_recent(request: Request, limit: int = Query(default=10, ge=1, le=100)):
    """Fetch the most recent raw deliveries for debugging purposes.

    Requires a valid Bearer token for authentication. Disabled when
    enable_debug_routes is False in settings.

    Args:
        request: The incoming HTTP request.
        limit: Maximum number of deliveries to return (default 10, max 100).

    Returns:
        A DebugResponse containing a list of recent deliveries with their
        status, record counts, and timestamps.

    Raises:
        HTTPException: 404 if debug routes are disabled, 401 if unauthorized.
    """
    if not settings.enable_debug_routes:
        raise HTTPException(status_code=404, detail="Debug routes disabled")

    auth.require_bearer_request(request)

    deliveries = client.list_recent_deliveries(limit=limit)
    return DebugResponse(
        deliveries=[
            DebugDelivery(
                delivery_id=d["deliveryId"],
                received_at=datetime.fromtimestamp(d["receivedAt"] / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                record_count=d["recordCount"],
                status=d["status"],
            )
            for d in deliveries
        ]
    )
