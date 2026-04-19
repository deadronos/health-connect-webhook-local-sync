import pytest
from fastapi import HTTPException
from app.auth import BearerAuth

def test_missing_token_raises():
    auth = BearerAuth(token="secret")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify(None)
    assert exc_info.value.status_code == 401

def test_wrong_token_raises():
    auth = BearerAuth(token="secret")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify("Bearer wrong")
    assert exc_info.value.status_code == 401

def test_correct_token_passes():
    auth = BearerAuth(token="secret")
    result = auth.verify("Bearer secret")
    assert result is True

def test_empty_header_raises():
    auth = BearerAuth(token="secret")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify("")
    assert exc_info.value.status_code == 401


def test_missing_form_token_raises():
    auth = BearerAuth(token="secret")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify_token(None)
    assert exc_info.value.status_code == 401