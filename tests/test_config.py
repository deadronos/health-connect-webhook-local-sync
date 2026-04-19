from app.config import Settings

def test_settings_loads_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("INGEST_TOKEN", "test-token")
    monkeypatch.setenv("CONVEX_SELF_HOSTED_URL", "http://localhost:3210")
    monkeypatch.setenv("CONVEX_SELF_HOSTED_ADMIN_KEY", "test-key")
    monkeypatch.setenv("ENABLE_ANALYTICS_ROUTES", "false")
    settings = Settings()
    assert settings.ingest_token == "test-token"
    assert settings.convex_self_hosted_url == "http://localhost:3210"
    assert settings.enable_analytics_routes is False

def test_convex_site_url_property():
    settings = Settings()
    settings.ingest_token = "test"
    settings.convex_self_hosted_url = "http://127.0.0.1:3210"
    settings.convex_self_hosted_admin_key = "key"
    assert settings.convex_site_url == "http://127.0.0.1:3210/api/site"