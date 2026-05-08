"""Tests for ingest endpoint edge cases: payload-too-large, non-dict payload, database errors, and more."""

import pytest
from unittest.mock import patch


@pytest.fixture
def valid_record():
    """A minimal valid generic-format webhook record for steps."""
    return {
        "record_type": "steps",
        "value": 1000,
        "unit": "count",
        "start_time_ms": 1710800000000,
        "end_time_ms": 1710803600000,
    }


@pytest.fixture
def mock_convex_client():
    """Mock ConvexClient methods used by the ingest route."""
    with patch("app.routes.ingest.client") as mock_client:
        mock_client.ingest_delivery.return_value = {
            "delivery_id": "test-delivery-id",
            "received_records": 1,
            "stored_records": 1,
            "duplicate_records": 0,
        }
        yield mock_client


@pytest.mark.asyncio
async def test_payload_too_large_rejected():
    """The ingest endpoint should reject payloads exceeding the max body size."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    # 262144 bytes is the default MAX_BODY_BYTES
    huge_payload = {"records": [{"record_type": "steps", "value": 1, "unit": "count",
                                  "start_time_ms": 1, "end_time_ms": 2}] * 20000}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=huge_payload,
            headers={"Authorization": "Bearer test-token"},
        )
        # Either 413 or 422 depending on how the body is processed
        assert resp.status_code in (413, 422)


@pytest.mark.asyncio
async def test_non_dict_payload_rejected():
    """The ingest endpoint should reject JSON arrays or primitives."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Send a JSON array instead of an object
        resp = await client.post(
            "/ingest/health/v1",
            json=[1, 2, 3],
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 422
        assert "must be a JSON object" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_database_error_returns_500(valid_record, mock_convex_client):
    """A database error during ingest should return 500."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    mock_convex_client.ingest_delivery.side_effect = Exception("Database error")

    app = create_app()
    payload = {"records": [valid_record]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Database error"


@pytest.mark.asyncio
async def test_invalid_record_type_returns_422(mock_convex_client):
    """Unsupported record types in flat format should return 422."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {
        "records": [
            {"record_type": "unsupported_type", "value": 100, "unit": "count",
             "start_time_ms": 1710800000000, "end_time_ms": 1710803600000}
        ]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        # NormalizeError is caught and returns 422
        # The mock won't be called if normalizer raises
        assert resp.status_code == 422
        assert "unsupported record type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_data_classification_valid_default(valid_record, mock_convex_client):
    """A delivery without test-data headers or mock sender UA should be classified as valid."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {"records": [valid_record]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        raw_delivery = mock_convex_client.ingest_delivery.call_args.kwargs["raw_delivery"]
        assert raw_delivery["dataClass"] == "valid"
        assert raw_delivery.get("dataClassReason") is None


@pytest.mark.asyncio
async def test_data_classification_test_by_header(valid_record, mock_convex_client):
    """X-OpenClaw-Test-Data: true should classify as test."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {"records": [valid_record]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer test-token", "X-OpenClaw-Test-Data": "1"},
        )
        assert resp.status_code == 200
        raw_delivery = mock_convex_client.ingest_delivery.call_args.kwargs["raw_delivery"]
        assert raw_delivery["dataClass"] == "test"


@pytest.mark.asyncio
async def test_data_classification_test_by_various_truthy_values(valid_record, mock_convex_client):
    """Various truthy values for X-OpenClaw-Test-Data should classify as test."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    for truthy in ("1", "true", "yes", "on", "TRUE", "Yes", "ON"):
        payload = {"records": [valid_record]}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/ingest/health/v1",
                json=payload,
                headers={"Authorization": "Bearer test-token", "X-OpenClaw-Test-Data": truthy},
            )
            assert resp.status_code == 200
            raw_delivery = mock_convex_client.ingest_delivery.call_args.kwargs["raw_delivery"]
            assert raw_delivery["dataClass"] == "test"


@pytest.mark.asyncio
async def test_data_classification_false_by_various_falsy_values(valid_record, mock_convex_client):
    """Various falsey values for X-OpenClaw-Test-Data should classify as valid."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    for falsy in ("0", "false", "no", "off", "FALSE", "No", "OFF"):
        payload = {"records": [valid_record]}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/ingest/health/v1",
                json=payload,
                headers={"Authorization": "Bearer test-token", "X-OpenClaw-Test-Data": falsy},
            )
            assert resp.status_code == 200
            raw_delivery = mock_convex_client.ingest_delivery.call_args.kwargs["raw_delivery"]
            assert raw_delivery["dataClass"] == "valid"