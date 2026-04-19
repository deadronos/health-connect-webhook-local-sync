from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app

@pytest.mark.asyncio
async def test_healthz_healthy():
    app = create_app()
    with patch("app.routes.health.client") as mock_client:
        mock_client.check_db_health.return_value = {"ok": True, "db": "ok"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["db"] == "ok"

@pytest.mark.asyncio
async def test_healthz_unhealthy():
    app = create_app()
    with patch("app.routes.health.client") as mock_client:
        mock_client.check_db_health.return_value = {"ok": False, "db": "unhealthy"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["db"] == "unhealthy"

@pytest.mark.asyncio
async def test_healthz_empty_response():
    app = create_app()
    with patch("app.routes.health.client") as mock_client:
        mock_client.check_db_health.return_value = {}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["db"] == "unknown"

@pytest.mark.asyncio
async def test_healthz_error():
    app = create_app()
    with patch("app.routes.health.client") as mock_client:
        mock_client.check_db_health.side_effect = Exception("DB error")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/healthz")

    assert response.status_code == 500
