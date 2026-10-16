"""Regression checks for production configuration guardrails."""

import pytest

from app.core.config import Settings, validate_runtime_settings


def test_development_settings_allow_local_defaults() -> None:
    validate_runtime_settings(Settings(ENVIRONMENT="development"))


def test_production_rejects_default_secret_key() -> None:
    config = Settings(ENVIRONMENT="production")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_runtime_settings(config)


def test_production_rejects_legacy_migration_api() -> None:
    config = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="x" * 32,
        ENABLE_LEGACY_MIGRATION_API=True,
    )

    with pytest.raises(RuntimeError, match="LEGACY_MIGRATION_API"):
        validate_runtime_settings(config)
