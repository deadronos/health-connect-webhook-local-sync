from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8787
    ingest_token: str = "replace_me"
    convex_self_hosted_url: str = "http://127.0.0.1:3210"
    convex_self_hosted_admin_key: str = ""
    enable_debug_routes: bool = True
    max_body_bytes: int = 262144
    openclaw_webhook_url: str = ""
    openclaw_webhook_token: str = ""

    @property
    def convex_site_url(self) -> str:
        """Site proxy URL for Convex HTTP actions."""
        return f"{self.convex_self_hosted_url}/api/site"