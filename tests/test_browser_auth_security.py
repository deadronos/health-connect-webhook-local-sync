"""Tests for browser auth security: safe redirect paths and session persistence."""

import pytest


@pytest.mark.asyncio
async def test_safe_next_path_allows_relative_paths():
    """_safe_next_path should allow safe relative paths."""
    from app.routes.browser_auth import _safe_next_path

    assert _safe_next_path("/dashboard") == "/dashboard"
    assert _safe_next_path("/analytics/overview") == "/analytics/overview"
    assert _safe_next_path("/") == "/"


@pytest.mark.asyncio
async def test_safe_next_path_rejects_absolute_urls():
    """_safe_next_path should reject URLs with schemes (open redirect prevention)."""
    from app.routes.browser_auth import _safe_next_path

    assert _safe_next_path("https://evil.com") == "/dashboard"
    assert _safe_next_path("http://evil.com") == "/dashboard"
    assert _safe_next_path("//evil.com") == "/dashboard"


@pytest.mark.asyncio
async def test_safe_next_path_rejects_backslashes():
    """_safe_next_path should reject paths containing backslashes."""
    from app.routes.browser_auth import _safe_next_path

    assert _safe_next_path("/dashboard\\evil") == "/dashboard"
    assert _safe_next_path("\\\\evil.com") == "/dashboard"


@pytest.mark.asyncio
async def test_safe_next_path_rejects_empty_and_none():
    """_safe_next_path should default to /dashboard for empty or None input."""
    from app.routes.browser_auth import _safe_next_path

    assert _safe_next_path(None) == "/dashboard"
    assert _safe_next_path("") == "/dashboard"


@pytest.mark.asyncio
async def test_safe_next_path_rejects_non_leading_slash():
    """_safe_next_path should reject paths that don't start with /."""
    from app.routes.browser_auth import _safe_next_path

    assert _safe_next_path("dashboard") == "/dashboard"


@pytest.mark.asyncio
async def test_login_with_bearer_header_auto_creates_session():
    """GET /login with valid Bearer header should create a session and redirect."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/login?next=/analytics/overview",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/analytics/overview"
    assert "hc_test_session=" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_login_with_invalid_bearer_shows_login_page():
    """GET /login with an invalid Bearer header should fall through to showing the login form."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/login",
            headers={"Authorization": "Bearer wrong-token"},
        )

    # Invalid bearer is caught by the login handler and falls through to
    # rendering the login page with status 200
    assert response.status_code == 200
    assert "Sign in with your ingest token" in response.text


@pytest.mark.asyncio
async def test_login_form_includes_next_path():
    """The login page should embed the next path in the form."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/login?next=/analytics/overview")

    assert response.status_code == 200
    assert "/analytics/overview" in response.text


@pytest.mark.asyncio
async def test_login_post_with_safe_redirect():
    """POST /login with valid token should redirect to the safe next path."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/login",
            data={"token": "test-token", "next": "/analytics/overview"},
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/analytics/overview"


@pytest.mark.asyncio
async def test_login_post_rejects_unsafe_redirect():
    """POST /login should redirect to /dashboard when given an unsafe next path."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/login",
            data={"token": "test-token", "next": "https://evil.com"},
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


@pytest.mark.asyncio
async def test_analytics_disabled_returns_404():
    """Analytics endpoints should return 404 when disabled."""
    from unittest.mock import patch
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.analytics.settings.enable_analytics_routes", False), \
         patch("app.routes.browser_auth.settings.enable_analytics_routes", False), \
         patch("app.routes.dashboard.settings.enable_analytics_routes", False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login_resp = await client.get("/login")
            analytics_resp = await client.get(
                "/analytics/overview",
                headers={"Authorization": "Bearer test-token"},
            )

        assert login_resp.status_code == 404
        assert analytics_resp.status_code == 404


@pytest.mark.asyncio
async def test_debug_disabled_returns_404():
    """Debug endpoints should return 404 when disabled."""
    from unittest.mock import patch
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.debug.settings.enable_debug_routes", False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/debug/recent",
                headers={"Authorization": "Bearer test-token"},
            )

        assert resp.status_code == 404