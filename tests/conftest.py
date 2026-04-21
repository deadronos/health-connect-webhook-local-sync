"""Pytest configuration and shared fixtures for the test suite.

Sets environment variables to isolate tests from local shell and .env configuration,
then provides mock fixtures for the Convex HTTP client.
"""

import os
from unittest.mock import patch, MagicMock

import pytest


# Set test env vars before importing app modules.
# Use direct assignment so local shell or .env values do not leak into the test process.
os.environ["INGEST_TOKEN"] = "test-token"
os.environ["CONVEX_SELF_HOSTED_URL"] = "http://127.0.0.1:3210"
os.environ["CONVEX_SELF_HOSTED_ADMIN_KEY"] = "test-admin-key"
os.environ["ENABLE_DEBUG_ROUTES"] = "true"
os.environ["ENABLE_ANALYTICS_ROUTES"] = "true"
os.environ["SESSION_SECRET"] = "test-session-secret"
os.environ["SESSION_COOKIE_NAME"] = "hc_test_session"
os.environ["SESSION_MAX_AGE_SECONDS"] = "3600"


@pytest.fixture
def mock_convex():
    """Mock ConvexClient for unit tests.

    Patches the httpx.Client used internally so that ConvexClient
    operations succeed without a real backend.
    """
    with patch("app.convex_client.httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"value": "test-id"},
            raise_for_status=MagicMock(),
        )
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_convex_with_health(mock_convex):
    """Mock ConvexClient that also responds to health check.

    Extends mock_convex so that /healthz returns a healthy response.
    """
    mock_convex.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"value": {"ok": True, "db": "ok"}},
        raise_for_status=MagicMock(),
    )
    return mock_convex
