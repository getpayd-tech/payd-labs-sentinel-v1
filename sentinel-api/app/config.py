from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # SQLite database (stored on Docker volume at /data)
    database_url: str = "sqlite+aiosqlite:////data/sentinel.db"

    # Redis
    redis_url: str = "redis://sentinel-redis:6379/0"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Payd Auth
    payd_auth_url: str = "https://auth.payd.money"
    payd_api_url: str = "https://api.payd.money/v1"

    # Managed PostgreSQL (for database admin features)
    pg_admin_host: str = ""
    pg_admin_port: int = 25060
    pg_admin_user: str = ""
    pg_admin_password: str = ""
    pg_admin_database: str = "defaultdb"
    pg_admin_sslmode: str = "require"

    # GHCR authentication for pulling private images during deploys
    ghcr_user: str = "getpayd-tech"
    ghcr_token: str = ""

    # Encryption key for env var storage (Fernet)
    encryption_key: str = ""

    # Comma-separated list of usernames allowed to log in (on top of is_admin)
    # If empty, any admin can log in
    allowed_usernames: str = ""

    # --- Self-host instance config (overridable via /setup wizard) -----------
    # Public URL of THIS Sentinel instance. Used in generated CI workflows
    # (webhook URL) and any UI text that references the instance URL.
    sentinel_url: str = "http://localhost:8000"

    # Docker container name for the Caddy reverse proxy on the host.
    caddy_container: str = "caddy-proxy"

    # External Docker network used by Caddy + deployed services.
    proxy_network: str = "proxy"

    # On-demand TLS catch-all upstream. If blank, no catch-all block is emitted
    # in the Caddyfile and unregistered domains get a clean 404 from Caddy.
    # Existing Payd Labs deployment should set this to "payd-labs-one-link:8000"
    # via the sentinel_config.json file so OneLink custom domains keep working.
    catchall_upstream: str = ""

    # Informational server IP shown in the UI's DNS instructions.
    server_ip: str = ""

    # Path to the persistent instance-config JSON (setup wizard output).
    config_file: str = "/data/sentinel_config.json"

    @property
    def allowed_username_list(self) -> list[str]:
        return [u.strip().lower() for u in self.allowed_usernames.split(",") if u.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
