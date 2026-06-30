from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    debug: bool = True

    database_url: str

    @field_validator("database_url")
    @classmethod
    def _force_asyncpg_driver(cls, value: str) -> str:
        # Managed Postgres providers (Render, Heroku, etc.) hand back a plain
        # postgres:// or postgresql:// URL. SQLAlchemy defaults that scheme to
        # the psycopg2 driver, which we don't install - we're asyncpg-only.
        # Rewriting here means deploy targets work without hand-editing
        # whatever DATABASE_URL the platform injects.
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    google_client_id: str = ""

    # Full contents of a GCP service account JSON key, pasted as one env var
    # (not a file path) - works on platforms like Render with no persistent
    # filesystem to drop a key file into. Used for Cloud Speech-to-Text.
    google_application_credentials_json: str = ""

    yarngpt_api_key: str = ""
    yarngpt_api_base_url: str = ""

    media_root: str = "static"
    media_url: str = "/media"
    base_url: str = "http://localhost:8000"

    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
