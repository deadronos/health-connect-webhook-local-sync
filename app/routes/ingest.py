"""Main webhook ingest endpoint for receiving health data from Android and generic sources."""

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

TEST_DATA_HEADER = "x-openclaw-test-data"
MOCK_SENDER_USER_AGENT_PREFIX = "health-ingest-mock-sender/"
TRUTHY_HEADER_VALUES = {"1", "true", "yes", "on"}
FALSEY_HEADER_VALUES = {"0", "false", "no", "off"}


def _parse_test_data_header(value: str | None) -> bool | None:
    """Parse the X-OpenClaw-Test-Data header into a boolean or None.

    Args:
        value: Raw header value, or None if the header is absent.

    Returns:
        True if the header indicates test data, False if not, None if absent.

    Raises:
        HTTPException: If the header value is present but not a recognized truthy/falsey string.
    """
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in TRUTHY_HEADER_VALUES:
        return True
    if normalized in FALSEY_HEADER_VALUES:
        return False

    raise HTTPException(status_code=422, detail="X-OpenClaw-Test-Data must be true or false")


def _classify_delivery_data(request: Request) -> tuple[str, str | None]:
    """Classify a delivery as either "test" or "valid" based on headers.

    A delivery is classified as "test" if the X-OpenClaw-Test-Data header is true,
    or if the User-Agent matches the mock sender prefix.

    Args:
        request: The incoming HTTP request.

    Returns:
        A tuple of (data_class, reason). data_class is "test" or "valid".
        reason is a string describing why the classification was made, or None.
    """
    header_value = _parse_test_data_header(request.headers.get(TEST_DATA_HEADER))
    if header_value is True:
        return "test", "header:x-openclaw-test-data"
    if header_value is False:
        return "valid", None

    user_agent = request.headers.get("user-agent") or ""
    if user_agent.startswith(MOCK_SENDER_USER_AGENT_PREFIX):
        return "test", "user-agent:health-ingest-mock-sender"

    return "valid", None


@router.post("/health/v1", response_model=IngestResponse)
async def ingest_health(request: Request):
    """Ingest health data from either an Android Health Connect app or a generic webhook source.

    Accepts two payload formats:
    - Android format: nested JSON with typed arrays (steps, heart_rate, etc.)
    - Generic format: flat JSON with a "records" array

    The endpoint authenticates via Bearer token, validates and normalizes the payload,
    then stores the raw delivery and individual events in Convex.

    Args:
        request: The incoming HTTP request.

    Returns:
        An IngestResponse with counts of received and stored records and the delivery ID.

    Raises:
        HTTPException: 401 for auth failures, 413 if body is too large,
            422 for malformed/invalid JSON or unsupported record types,
            500 for database errors.
    """
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
    data_class, data_class_reason = _classify_delivery_data(request)

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
                "status": "completed",
                "recordCount": received_records,
                "dataClass": data_class,
                "dataClassReason": data_class_reason,
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
