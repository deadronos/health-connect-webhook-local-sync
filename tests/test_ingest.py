"""End-to-end ingest tests with mocked Convex."""
import pytest
from unittest.mock import patch, MagicMock


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
        mock_client.store_raw_delivery.return_value = "test-delivery-id"
        mock_client.store_health_events.return_value = ["test-event-id"]
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