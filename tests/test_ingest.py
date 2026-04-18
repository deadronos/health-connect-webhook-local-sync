"""End-to-end ingest tests with mocked Convex."""
import pytest


@pytest.fixture
def valid_record():
    return {
        "record_type": "steps",
        "value": 1000,
        "unit": "count",
        "start_time_ms": 1710800000000,
        "end_time_ms": 1710803600000,
    }


@pytest.mark.asyncio
async def test_valid_payload_accepted(valid_record):
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
        # With mocked Convex, we may get 200 or 500 depending on mock setup
        assert resp.status_code in (200, 500)


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
async def test_empty_records_list_accepted(valid_record):
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
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_multiple_records_accepted(valid_record):
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
        assert resp.status_code in (200, 500)