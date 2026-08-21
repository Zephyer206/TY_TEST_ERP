"""Focused tests for the customer-scoped single-part dossier history."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.api.gaibo_after_sales import _demote_current_routes, _get_requirement_change_history
from app.models.gaibo import GaiboCustomerRequirement, GaiboProcessRoute


@pytest.mark.asyncio
async def test_requirement_history_includes_owned_dossier_entities_only():
    requirement = GaiboCustomerRequirement(
        id=19,
        workspace_id=7,
        single_part_id=42,
        customer_part_number="C-19",
        ibi="IBI-19",
        tianyue_internal_composition="TY-19",
    )
    expected_history = [object(), object()]
    db = SimpleNamespace(scalars=AsyncMock(return_value=expected_history))

    result = await _get_requirement_change_history(db, requirement)

    assert result == expected_history
    statement = db.scalars.await_args.args[0]
    sql = " ".join(
        str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).split()
    )
    assert "gaibo_change_logs.workspace_id = 7" in sql
    assert "gaibo_change_logs.entity_type = 'requirement'" in sql
    assert "gaibo_change_logs.entity_id = 19" in sql
    assert "gaibo_change_logs.entity_type = 'single_part'" in sql
    assert "gaibo_change_logs.entity_id = 42" in sql
    assert "gaibo_drawings.requirement_id = 19" in sql
    assert "gaibo_process_routes.requirement_id = 19" in sql
    assert "gaibo_document_statuses.requirement_id = 19" in sql
    assert "ORDER BY gaibo_change_logs.created_at DESC, gaibo_change_logs.id DESC" in sql


class _RouteDb:
    def __init__(self, current_route):
        self.current_route = current_route
        self.added = []
        self.flushed = False

    async def scalars(self, _statement):
        return [self.current_route]

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        self.flushed = True


@pytest.mark.asyncio
async def test_demoting_current_route_happens_before_the_next_current_route_is_saved():
    current = GaiboProcessRoute(id=5, requirement_id=19, version="v1", status="released", is_current=True)
    db = _RouteDb(current)

    await _demote_current_routes(
        db,
        requirement_id=19,
        workspace_id=7,
        except_route_id=None,
        actor_user_id=3,
    )

    assert current.is_current is False
    assert db.flushed is True
    assert len(db.added) == 1
    assert db.added[0].action == "process_route_current_replaced"
    assert db.added[0].change_data["is_current"] == {"before": True, "after": False}
