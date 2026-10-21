"""Application configuration using Pydantic Settings."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SECRET_KEY = "change-me-in-production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Cloud Stamping ERP"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # Legacy in-process migrations are disabled by default. Database changes
    # must normally run through the repository Alembic entry point.
    ENABLE_LEGACY_MIGRATION_API: bool = False

    # Temporary acceptance switch. When enabled, API dependencies use the
    # first LV4 user as the current administrator without requiring login.
    # Set AUTH_DISABLED=false before enabling a production deployment.
    AUTH_DISABLED: bool = True

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cloud_stamping",
        description="Async PostgreSQL connection string",
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and sessions",
    )

    # JWT Security
    SECRET_KEY: str = Field(
        default=DEFAULT_SECRET_KEY,
        description="Secret key for JWT token signing",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:9000",
    ]

    # File Storage (COS/S3 compatible)
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_BUCKET: str = ""
    COS_REGION: str = "ap-guangzhou"
    COS_ENDPOINT: str = ""

    # Upload directory
    UPLOAD_DIR: str = Field(default="uploads", description="Local upload directory for drawings and files")
    PPAP_STORAGE_ROOT: str = Field(default="", description="Private PPAP originals and preview cache; outside public uploads")
    PPAP_SOFFICE: str = Field(default="", description="Optional LibreOffice executable for local Excel preview")

    # Email (optional)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()


def validate_runtime_settings(config: Settings = settings) -> None:
    """Reject unsafe production settings before accepting traffic."""
    if config.ENVIRONMENT != "production":
        return

    if config.SECRET_KEY == DEFAULT_SECRET_KEY or len(config.SECRET_KEY) < 32:
        raise RuntimeError("Production SECRET_KEY must be a non-default value of at least 32 characters")

    if config.ENABLE_LEGACY_MIGRATION_API:
        raise RuntimeError("ENABLE_LEGACY_MIGRATION_API must remain disabled in production")

    if config.AUTH_DISABLED:
        raise RuntimeError("AUTH_DISABLED must be false in production")
