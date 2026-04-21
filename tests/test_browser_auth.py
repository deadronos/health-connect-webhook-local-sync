"""Tests for browser-based login/logout flow and session management."""

import pytest


@pytest.mark.asyncio
async def test_login_page_renders_html():
    """GET /login should return the login form HTML page."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/login")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Sign in with your ingest token" in response.text


@pytest.mark.asyncio
async def test_login_sets_session_cookie_and_redirects():
    """POST /login with valid credentials should set a session cookie and redirect."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/login",
            data={"token": "test-token", "next": "/dashboard"},
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    assert "hc_test_session=" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_login_rejects_invalid_token():
    """POST /login with a wrong token should return 401 with an error message."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/login",
            data={"token": "wrong-token", "next": "/dashboard"},
        )

    assert response.status_code == 401
    assert "Invalid token" in response.text


@pytest.mark.asyncio
async def test_logout_clears_dashboard_session():
    """POST /logout should clear the session and redirect back to login."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"token": "test-token", "next": "/dashboard"})
        logout_response = await client.post("/logout")
        dashboard_response = await client.get("/dashboard")

    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"
    assert dashboard_response.status_code == 303
    assert dashboard_response.headers["location"] == "/login?next=%2Fdashboard"


@pytest.mark.asyncio
async def test_dashboard_session_does_not_authorize_ingest_or_debug():
    """A dashboard session cookie should not grant access to ingest or debug endpoints."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_response = await client.post(
            "/login",
            data={"token": "test-token", "next": "/dashboard"},
        )
        ingest_response = await client.post("/ingest/health/v1", json={"records": []})
        debug_response = await client.get("/debug/recent")

    assert login_response.status_code == 303
    assert ingest_response.status_code == 401
    assert debug_response.status_code == 401
