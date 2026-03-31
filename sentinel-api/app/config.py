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

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 7

    # Managed PostgreSQL (for database admin features)
    pg_admin_host: str = ""
    pg_admin_port: int = 25060
    pg_admin_user: str = ""
    pg_admin_password: str = ""
    pg_admin_database: str = "defaultdb"
    pg_admin_sslmode: str = "require"

    # Encryption key for env var storage (Fernet)
    encryption_key: str = ""

    # Default admin credentials (set on first boot)
    default_admin_username: str = "admin"
    default_admin_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
