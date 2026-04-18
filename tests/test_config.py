from app.config import Settings

def test_settings_loads_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("INGEST_TOKEN", "test-token")
    monkeypatch.setenv("CONVEX_SELF_HOSTED_URL", "http://localhost:3210")
    monkeypatch.setenv("CONVEX_SELF_HOSTED_ADMIN_KEY", "test-key")
    settings = Settings()
    assert settings.ingest_token == "test-token"
    assert settings.convex_self_hosted_url == "http://localhost:3210"

def test_convex_site_url_property():
    settings = Settings()
    settings.ingest_token = "test"
    settings.convex_self_hosted_url = "http://127.0.0.1:3210"
    settings.convex_self_hosted_admin_key = "key"
    assert settings.convex_site_url == "http://127.0.0.1:3210/api/site"