"""Tests for BearerAuth session persistence and combined auth scenarios."""

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException, Request
from app.auth import BearerAuth


def test_has_valid_bearer_request_returns_false_for_missing_header():
    """has_valid_bearer_request should return False when no Authorization header is present."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    request.headers = {}
    assert auth.has_valid_bearer_request(request) is False


def test_has_valid_bearer_request_returns_true_for_valid_token():
    """has_valid_bearer_request should return True for a valid Bearer token."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    request.headers = {"authorization": "Bearer secret"}
    assert auth.has_valid_bearer_request(request) is True


def test_require_dashboard_access_raises_with_no_auth():
    """require_dashboard_access should raise 401 when no auth is provided."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    request.headers = {}
    request.session = {}

    with pytest.raises(HTTPException) as exc_info:
        auth.require_dashboard_access(request)
    assert exc_info.value.status_code == 401


def test_require_dashboard_access_passes_with_bearer():
    """require_dashboard_access should return True with a valid Bearer token."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    request.headers = {"authorization": "Bearer secret"}
    request.session = {}

    result = auth.require_dashboard_access(request)
    assert result is True


def test_require_dashboard_access_passes_with_session():
    """require_dashboard_access should return True with an active dashboard session."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    request.headers = {}
    request.session = {"dashboard_authenticated": True}

    result = auth.require_dashboard_access(request)
    assert result is True


def test_require_dashboard_access_persists_session_with_bearer():
    """require_dashboard_access with persist_bearer_session=True should create a session."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    request.headers = {"authorization": "Bearer secret"}
    request.session = {}

    result = auth.require_dashboard_access(request, persist_bearer_session=True)
    assert result is True
    assert request.session.get("dashboard_authenticated") is True


def test_require_dashboard_access_does_not_persist_without_flag():
    """require_dashboard_access without persist_bearer_session should NOT create a session."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    request.headers = {"authorization": "Bearer secret"}
    request.session = {}

    result = auth.require_dashboard_access(request)
    assert result is True
    # Session should remain empty (no persist)
    assert "dashboard_authenticated" not in request.session


def test_has_dashboard_session_handles_assertion_error():
    """has_dashboard_session should return False when session access raises AssertionError."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    type(request).session = property(lambda self: (_ for _ in ()).throw(AssertionError("no session")))
    
    result = auth.has_dashboard_session(request)
    assert result is False


def test_clear_dashboard_session_handles_assertion_error():
    """clear_dashboard_session should silently handle AssertionError."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    
    # Make session.clear() raise AssertionError
    request.session = MagicMock()
    request.session.clear.side_effect = AssertionError("no session")
    
    # Should not raise
    auth.clear_dashboard_session(request)


def test_start_dashboard_session_clears_existing():
    """start_dashboard_session should clear existing session data before setting the flag."""
    auth = BearerAuth(token="secret")
    request = MagicMock(spec=Request)
    request.session = {"old_key": "old_value"}

    auth.start_dashboard_session(request)
    assert request.session.get("dashboard_authenticated") is True
    # The old session data should have been cleared
    assert "old_key" not in request.session


def test_verify_malformed_header():
    """verify() should raise 401 for a malformed Authorization header."""
    auth = BearerAuth(token="secret")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify("Token secret")
    assert exc_info.value.status_code == 401
    assert "Invalid authorization header format" in exc_info.value.detail


def test_verify_missing_scheme():
    """verify() should raise 401 for an Authorization header with no scheme."""
    auth = BearerAuth(token="secret")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify("secret")
    assert exc_info.value.status_code == 401