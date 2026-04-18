"""End-to-end ingest tests for Android format with mocked Convex."""
import pytest
from unittest.mock import patch


@pytest.fixture
def valid_android_steps():
    return {
        "timestamp": "2024-03-19T10:00:00Z",
        "app_version": "1.0.0",
        "steps": [
            {
                "count": 1000,
                "start_time": "2024-03-19T10:00:00Z",
                "end_time": "2024-03-19T10:15:00Z",
            },
            {
                "count": 500,
                "start_time": "2024-03-19T10:15:00Z",
                "end_time": "2024-03-19T10:30:00Z",
            },
        ],
    }


@pytest.fixture
def mock_convex_client():
    """Mock ConvexClient methods used by the ingest route."""
    with patch("app.routes.ingest.client") as mock_client:
        mock_client.store_raw_delivery.return_value = "test-delivery-id"
        mock_client.store_health_events.return_value = ["test-event-id"]
        yield mock_client


@pytest.mark.asyncio
async def test_android_format_payload_accepted(valid_android_steps, mock_convex_client):
    """Test that a properly structured Android format payload is accepted."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=valid_android_steps,
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["received_records"] == 2  # 2 steps records


@pytest.mark.asyncio
async def test_android_format_multiple_types_accepted(mock_convex_client):
    """Test that Android format with multiple record types is accepted and counted correctly."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {
        "timestamp": "2024-03-19T10:00:00Z",
        "app_version": "1.0.0",
        "steps": [{"count": 1000, "start_time": "2024-03-19T10:00:00Z", "end_time": "2024-03-19T10:15:00Z"}],
        "heart_rate": [{"bpm": 72, "time": "2024-03-19T10:00:00Z"}],
        "distance": [{"meters": 1000.0, "start_time": "2024-03-19T10:00:00Z", "end_time": "2024-03-19T10:15:00Z"}],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["received_records"] == 3  # 1 steps + 1 heart_rate + 1 distance


@pytest.mark.asyncio
async def test_flat_format_still_works(valid_android_steps, mock_convex_client):
    """Test that flat format still works alongside Android format."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    flat_payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 1000,
                "unit": "count",
                "start_time_ms": 1710800000000,
                "end_time_ms": 1710803600000,
            }
        ]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=flat_payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["received_records"] == 1


@pytest.mark.asyncio
async def test_android_format_invalid_payload_rejected():
    """Test that an invalid Android payload is rejected with 422."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    # Missing required fields for steps record
    payload = {
        "timestamp": "2024-03-19T10:00:00Z",
        "app_version": "1.0.0",
        "steps": [{"count": 1000}],  # missing start_time and end_time
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 422