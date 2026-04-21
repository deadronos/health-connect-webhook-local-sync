"""Tests for Settings configuration loading from environment variables."""

from app.config import Settings


def test_settings_loads_from_env(tmp_path, monkeypatch):
    """Settings should load values from environment variables when provided."""
    monkeypatch.setenv("INGEST_TOKEN", "test-token")
    monkeypatch.setenv("CONVEX_SELF_HOSTED_URL", "http://localhost:3210")
    monkeypatch.setenv("CONVEX_SELF_HOSTED_ADMIN_KEY", "test-key")
    monkeypatch.setenv("ENABLE_ANALYTICS_ROUTES", "false")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("SESSION_COOKIE_NAME", "hc-session")
    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "7200")
    settings = Settings()
    assert settings.ingest_token == "test-token"
    assert settings.convex_self_hosted_url == "http://localhost:3210"
    assert settings.enable_analytics_routes is False
    assert settings.session_secret == "test-session-secret"
    assert settings.session_cookie_name == "hc-session"
    assert settings.session_max_age_seconds == 7200


def test_convex_site_url_property():
    """convex_site_url should append /api/site to the convex_self_hosted_url."""
    settings = Settings()
    settings.ingest_token = "test"
    settings.convex_self_hosted_url = "http://127.0.0.1:3210"
    settings.convex_self_hosted_admin_key = "key"
    assert settings.convex_site_url == "http://127.0.0.1:3210/api/site"


def test_session_https_only_property_changes_with_env():
    """session_https_only should be False in development/test and True in production."""
    settings = Settings()
    settings.app_env = "development"
    assert settings.session_https_only is False

    settings.app_env = "test"
    assert settings.session_https_only is False

    settings.app_env = "production"
    assert settings.session_https_only is True
