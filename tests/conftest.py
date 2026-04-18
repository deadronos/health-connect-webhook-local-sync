import os
from unittest.mock import patch, MagicMock

import pytest


# Set test env vars before importing app modules
os.environ.setdefault("INGEST_TOKEN", "test-token")
os.environ.setdefault("CONVEX_SELF_HOSTED_URL", "http://127.0.0.1:3210")
os.environ.setdefault("CONVEX_SELF_HOSTED_ADMIN_KEY", "test-admin-key")


@pytest.fixture
def mock_convex():
    """Mock ConvexClient for unit tests."""
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
    """Mock ConvexClient that also responds to health check."""
    mock_convex.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"value": {"ok": True, "db": "ok"}},
        raise_for_status=MagicMock(),
    )
    return mock_convex