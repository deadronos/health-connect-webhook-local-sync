import hashlib
import json
import uuid
from fastapi import APIRouter, Request, HTTPException

from app.auth import BearerAuth
from app.config import Settings
from app.schemas import IngestRequest, IngestResponse
from app.convex_client import ConvexClient
from app.normalizer import Normalizer, NormalizationError

settings = Settings()
auth = BearerAuth(token=settings.ingest_token)
client = ConvexClient(
    convex_url=settings.convex_self_hosted_url,
    admin_key=settings.convex_self_hosted_admin_key,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/health/v1", response_model=IngestResponse)
async def ingest_health(request: Request):
    # Verify auth
    auth_header = request.headers.get("authorization")
    auth.verify(auth_header)

    # Read body
    body = await request.body()
    if len(body) > settings.max_body_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")

    # Parse JSON
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Malformed JSON")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Payload must be a JSON object")

    # Validate payload structure
    try:
        ingest_req = IngestRequest.model_validate(payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {e}")

    # Compute hash and delivery ID
    payload_json = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
    delivery_id = str(uuid.uuid4())[:8]

    # Store raw delivery
    source_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    try:
        stored_delivery_id = client.store_raw_delivery(
            source_ip=source_ip,
            user_agent=user_agent,
            payload_json=payload_json,
            record_count=len(ingest_req.records),
            status="stored",
        )
    except Exception as e:
        try:
            client.store_raw_delivery(
                source_ip=source_ip,
                user_agent=user_agent,
                payload_json=payload_json,
                record_count=0,
                status="error",
                error_message=str(e),
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Database error")

    # Normalize and store events
    normalizer = Normalizer(payload=payload, payload_hash=payload_hash, delivery_id=stored_delivery_id)
    try:
        events = normalizer.normalize()
    except NormalizationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    stored_count = 0
    if events:
        try:
            client.store_health_events(events)
            stored_count = len(events)
        except Exception:
            pass  # Log but don't fail — raw delivery succeeded

    return IngestResponse(
        ok=True,
        received_records=len(ingest_req.records),
        stored_records=stored_count,
        delivery_id=stored_delivery_id,
    )