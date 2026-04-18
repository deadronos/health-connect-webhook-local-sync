import pytest


@pytest.mark.asyncio
async def test_malformed_json_rejected():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingest/health/v1",
            content=b"not valid json",
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_missing_record_type_rejected():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"records": [{"value": 100, "unit": "count"}]}
        resp = await client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 422