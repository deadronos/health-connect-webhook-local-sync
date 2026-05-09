"""Tests for BearerAuth token and session authentication."""

import pytest
from fastapi import HTTPException
from app.auth import BearerAuth


def test_missing_token_raises():
    """verify() should raise 401 when no authorization header is provided."""
    auth = BearerAuth(token="secret-token-at-least-32-chars-long-12345")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify(None)
    assert exc_info.value.status_code == 401


def test_wrong_token_raises():
    """verify() should raise 401 when the token does not match."""
    auth = BearerAuth(token="secret-token-at-least-32-chars-long-12345")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify("Bearer wrong")
    assert exc_info.value.status_code == 401


def test_correct_token_passes():
    """verify() should return True when the Bearer token matches."""
    auth = BearerAuth(token="secret-token-at-least-32-chars-long-12345")
    result = auth.verify("Bearer secret-token-at-least-32-chars-long-12345")
    assert result is True


def test_empty_header_raises():
    """verify() should raise 401 when the authorization header is an empty string."""
    auth = BearerAuth(token="secret-token-at-least-32-chars-long-12345")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify("")
    assert exc_info.value.status_code == 401


def test_missing_form_token_raises():
    """verify_token() should raise 401 when passed None."""
    auth = BearerAuth(token="secret-token-at-least-32-chars-long-12345")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify_token(None)
    assert exc_info.value.status_code == 401


def test_verify_token_valid():
    auth = BearerAuth(token="secret-token-at-least-32-chars-long-12345")
    assert auth.verify_token("secret-token-at-least-32-chars-long-12345") is True


def test_verify_token_invalid():
    auth = BearerAuth(token="secret-token-at-least-32-chars-long-12345")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify_token("wrong")
    assert exc_info.value.status_code == 401