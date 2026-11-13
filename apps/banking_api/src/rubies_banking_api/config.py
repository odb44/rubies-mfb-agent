"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Rubies MFB Banking API"
    app_version: str = "0.1.0"
    environment: str = "development"
    agent_service_token: str = Field(default="", repr=False)

    database_url: str = "postgresql+psycopg://rubies:rubies_dev@localhost:5432/rubies_mfb"

    jwt_secret_key: str = Field(default="", repr=False)
    jwt_issuer: str = "rubies-mfb"
    jwt_audience: str = "rubies-mfb-api"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_jwt_configuration(self) -> None:
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters.")

        if not self.jwt_issuer.strip():
            raise ValueError("JWT_ISSUER must not be empty.")

        if not self.jwt_audience.strip():
            raise ValueError("JWT_AUDIENCE must not be empty.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
