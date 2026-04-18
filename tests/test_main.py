from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient
from app.main import create_app


async def test_healthz_no_auth():
    app = create_app()
    # Mock the ConvexClient.check_db_health to avoid actual HTTP call
    with patch("app.routes.health.client") as mock_client:
        mock_client.check_db_health.return_value = {"ok": True, "db": "test"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/healthz")
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True

async def test_ingest_requires_auth():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingest/health/v1", json={"records": []})
        assert resp.status_code == 401