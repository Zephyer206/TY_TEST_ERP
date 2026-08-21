"""Focused query tests for installation-package change history."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.api.gaibo_after_sales import _get_package_change_history
from app.models.gaibo import GaiboInstallationPackage


@pytest.mark.asyncio
async def test_package_history_only_queries_entities_owned_by_the_package():
    package = GaiboInstallationPackage(id=41, workspace_id=7, package_number="FMG-041")
    expected_history = [object(), object()]
    db = SimpleNamespace(scalars=AsyncMock(return_value=expected_history))

    result = await _get_package_change_history(db, package)

    assert result == expected_history
    statement = db.scalars.await_args.args[0]
    sql = " ".join(
        str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).split()
    )
    assert "gaibo_change_logs.workspace_id = 7" in sql
    assert "gaibo_change_logs.entity_type = 'package'" in sql
    assert "gaibo_change_logs.entity_id = 41" in sql
    assert "gaibo_change_logs.entity_type = 'package_item'" in sql
    assert "gaibo_package_items.package_id = 41" in sql
    assert "gaibo_change_logs.entity_type = 'document'" in sql
    assert "gaibo_document_statuses.package_id = 41" in sql
    assert "gaibo_customer_requirements" not in sql
    assert "ORDER BY gaibo_change_logs.created_at DESC, gaibo_change_logs.id DESC" in sql
