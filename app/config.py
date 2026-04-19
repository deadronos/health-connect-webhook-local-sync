"""Application configuration loaded from environment variables via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from a .env file.

    Attributes:
        app_env: Deployment environment (development, test, production).
        app_host: Host address to bind the server to.
        app_port: Port number to bind the server to.
        ingest_token: Bearer token required for the /ingest endpoint.
        convex_self_hosted_url: Base URL of the self-hosted Convex deployment.
        convex_self_hosted_admin_key: Admin authentication key for Convex.
        enable_debug_routes: Whether the /debug routes are enabled.
        enable_analytics_routes: Whether analytics and dashboard routes are enabled.
        session_secret: Secret key used to sign session cookies.
        session_cookie_name: Name of the session cookie.
        session_max_age_seconds: Session cookie expiry time in seconds.
        max_body_bytes: Maximum allowed request body size in bytes.
        openclaw_webhook_url: Optional OpenClaw webhook URL for forwarding.
        openclaw_webhook_token: Token for authenticating to the OpenClaw webhook.
    """

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
        """Site proxy URL for Convex HTTP actions.

        Returns:
            The Convex deployment URL with /api/site appended.
        """
        return f"{self.convex_self_hosted_url}/api/site"

    @property
    def session_https_only(self) -> bool:
        """Whether sessions should only be sent over HTTPS.

        Returns:
            True in production/staging environments, False in development and test.
        """
        return self.app_env not in {"development", "test"}
