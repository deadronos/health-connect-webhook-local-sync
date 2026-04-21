"""Tests for the dashboard HTML page rendering."""

import pytest


@pytest.mark.asyncio
async def test_dashboard_requires_auth():
    """Unauthenticated requests to /dashboard should be redirected to /login."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard")

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fdashboard"


@pytest.mark.asyncio
async def test_dashboard_returns_html():
    """Authenticated requests should receive the dashboard HTML page."""
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
    assert "Track your daily activity" in response.text
    assert "Recent events" in response.text
    assert "dashboard-page" in response.text
    assert 'data-section-target="feature"' in response.text
    assert 'id="overview"' in response.text
    assert "hc_test_session=" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_dashboard_accepts_existing_session_cookie():
    """Requests with a valid session cookie should be authenticated without re-authorizing."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_response = await client.post(
            "/login",
            data={"token": "test-token", "next": "/dashboard"},
        )
        response = await client.get("/dashboard")

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert "Health Analytics Dashboard" in response.text
    assert "Trend spotlight" in response.text
