import hashlib
import json
from datetime import UTC, datetime
from fastapi import APIRouter, Request, HTTPException

from app.auth import BearerAuth
from app.config import Settings
from app.schemas import IngestRequest, IngestResponse, AndroidPayload
from app.convex_client import ConvexClient
from app.normalizer import Normalizer, AndroidPayloadNormalizer, NormalizationError

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
    auth.require_bearer_request(request)

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

    # Detect format before validation
    is_android_format = "records" not in payload and any(
        key in payload
        for key in [
            "steps",
            "heart_rate",
            "heart_rate_variability",
            "sleep",
            "distance",
            "active_calories",
            "total_calories",
            "weight",
            "height",
            "oxygen_saturation",
            "resting_heart_rate",
            "exercise",
            "nutrition",
            "basal_metabolic_rate",
            "body_fat",
            "lean_body_mass",
            "vo2_max",
        ]
    )

    # Validate payload structure based on format
    if is_android_format:
        try:
            android_payload = AndroidPayload.model_validate(payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid Android payload: {e}")
        received_records = sum(
            len(getattr(android_payload, key, []) or [])
            for key in [
                "steps",
                "sleep",
                "heart_rate",
                "heart_rate_variability",
                "distance",
                "active_calories",
                "total_calories",
                "weight",
                "height",
                "oxygen_saturation",
                "resting_heart_rate",
                "exercise",
                "nutrition",
                "basal_metabolic_rate",
                "body_fat",
                "lean_body_mass",
                "vo2_max",
            ]
        )
    else:
        try:
            ingest_req = IngestRequest.model_validate(payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload: {e}")
        received_records = len(ingest_req.records)

    # Compute hash and provisional delivery ID for normalization.
    payload_json = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
    provisional_delivery_id = payload_hash[:8]

    source_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    if is_android_format:
        normalizer = AndroidPayloadNormalizer(
            payload=payload, payload_hash=payload_hash, delivery_id=provisional_delivery_id
        )
    else:
        normalizer = Normalizer(payload=payload, payload_hash=payload_hash, delivery_id=provisional_delivery_id)

    try:
        events = normalizer.normalize()
    except NormalizationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        result = client.ingest_delivery(
            raw_delivery={
                "receivedAt": int(datetime.now(UTC).timestamp() * 1000),
                "sourceIp": source_ip,
                "userAgent": user_agent,
                "payloadJson": payload_json,
                "payloadHash": payload_hash,
                "status": "stored",
                "recordCount": received_records,
            },
            events=events,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Database error")

    return IngestResponse(
        ok=True,
        received_records=received_records,
        stored_records=result["stored_records"],
        delivery_id=result["delivery_id"],
    )