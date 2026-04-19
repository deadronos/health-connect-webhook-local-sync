from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8787
    ingest_token: str = "replace_me"
    convex_self_hosted_url: str = "http://127.0.0.1:3210"
    convex_self_hosted_admin_key: str = ""
    enable_debug_routes: bool = True
    enable_analytics_routes: bool = True
    session_secret: str = "replace-me-session-secret"
    session_cookie_name: str = "hc_dashboard_session"
    session_max_age_seconds: int = 86400
    max_body_bytes: int = 262144
    openclaw_webhook_url: str = ""
    openclaw_webhook_token: str = ""

    @property
    def convex_site_url(self) -> str:
        """Site proxy URL for Convex HTTP actions."""
        return f"{self.convex_self_hosted_url}/api/site"

    @property
    def session_https_only(self) -> bool:
        return self.app_env not in {"development", "test"}