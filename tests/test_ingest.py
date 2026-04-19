"""End-to-end ingest tests with mocked Convex."""
import pytest
from unittest.mock import patch


@pytest.fixture
def valid_record():
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
async def test_valid_payload_accepted(valid_record, mock_convex_client):
    """Test that a properly structured payload is accepted."""
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
        data = resp.json()
        assert data["ok"] is True
        assert data["received_records"] == 1
        raw_delivery = mock_convex_client.ingest_delivery.call_args.kwargs["raw_delivery"]
        assert raw_delivery["dataClass"] == "valid"
        assert raw_delivery.get("dataClassReason") is None


@pytest.mark.asyncio
async def test_missing_auth_rejected():
    """Test that requests without auth header are rejected."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {"records": []}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_auth_token_rejected():
    """Test that requests with wrong token are rejected."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {"records": []}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_empty_records_list_accepted(valid_record, mock_convex_client):
    """Test that an empty records list is a valid payload."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {"records": []}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["received_records"] == 0


@pytest.mark.asyncio
async def test_multiple_records_accepted(valid_record, mock_convex_client):
    """Test that multiple records are processed."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    record1 = dict(valid_record)
    record2 = dict(valid_record)
    record2["record_type"] = "heart_rate"
    record2["value"] = 72
    record2["unit"] = "bpm"
    payload = {"records": [record1, record2]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["received_records"] == 2


@pytest.mark.asyncio
async def test_header_marks_delivery_as_test_data(valid_record, mock_convex_client):
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {"records": [valid_record]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={
                "Authorization": "Bearer test-token",
                "X-OpenClaw-Test-Data": "true",
            },
        )

    assert resp.status_code == 200
    raw_delivery = mock_convex_client.ingest_delivery.call_args.kwargs["raw_delivery"]
    assert raw_delivery["dataClass"] == "test"
    assert raw_delivery["dataClassReason"] == "header:x-openclaw-test-data"


@pytest.mark.asyncio
async def test_mock_sender_user_agent_marks_delivery_as_test_data(valid_record, mock_convex_client):
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {"records": [valid_record]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={
                "Authorization": "Bearer test-token",
                "User-Agent": "health-ingest-mock-sender/1.0",
            },
        )

    assert resp.status_code == 200
    raw_delivery = mock_convex_client.ingest_delivery.call_args.kwargs["raw_delivery"]
    assert raw_delivery["dataClass"] == "test"
    assert raw_delivery["dataClassReason"] == "user-agent:health-ingest-mock-sender"


@pytest.mark.asyncio
async def test_explicit_false_test_data_header_overrides_mock_sender_user_agent(valid_record, mock_convex_client):
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {"records": [valid_record]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={
                "Authorization": "Bearer test-token",
                "User-Agent": "health-ingest-mock-sender/1.0",
                "X-OpenClaw-Test-Data": "false",
            },
        )

    assert resp.status_code == 200
    raw_delivery = mock_convex_client.ingest_delivery.call_args.kwargs["raw_delivery"]
    assert raw_delivery["dataClass"] == "valid"
    assert raw_delivery.get("dataClassReason") is None


@pytest.mark.asyncio
async def test_invalid_test_data_header_rejected(valid_record, mock_convex_client):
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {"records": [valid_record]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={
                "Authorization": "Bearer test-token",
                "X-OpenClaw-Test-Data": "sometimes",
            },
        )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "X-OpenClaw-Test-Data must be true or false"