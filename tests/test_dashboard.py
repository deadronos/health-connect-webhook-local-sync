import pytest


@pytest.mark.asyncio
async def test_dashboard_requires_auth():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_returns_html():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/dashboard",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Health Analytics Dashboard" in response.text
