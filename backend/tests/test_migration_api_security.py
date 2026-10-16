"""Regression checks for the legacy migration API exposure."""

from app.main import app


def test_legacy_migration_api_is_not_exposed_by_default() -> None:
    paths = app.openapi().get("paths", {})

    assert "/api/v1/migrations/run-all" not in paths
    assert "/api/v1/migrations/status" not in paths
