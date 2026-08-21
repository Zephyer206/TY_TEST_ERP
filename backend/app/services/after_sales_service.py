"""Shared business rules for the customer-first gaibo after-sales archive.

Routes should keep HTTP concerns (status codes and response mapping) here and
delegate mutations to these small helpers.  Keeping validation and audit
construction in one place prevents one editor from silently bypassing the
history trail used by the dossier.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gaibo import GaiboChangeLog, GaiboProcessRoute


class GaiboValidationError(ValueError):
    """A business validation failure suitable for a 400 response."""


def audit_value(value: Any) -> Any:
    """Return a JSON-safe representation for before/after values."""
    if value is None or isinstance(value, (str, int, float, bool, Decimal)):
        return str(value) if isinstance(value, Decimal) else value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def changed_values(entity: Any, updates: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Apply changed fields and return the exact audit payload.

    ``updates`` must already be validated by Pydantic.  Empty updates are a
    no-op and intentionally do not create a history row.
    """
    changed: list[str] = []
    data: dict[str, dict[str, Any]] = {}
    for field, next_value in updates.items():
        previous_value = getattr(entity, field)
        if previous_value == next_value:
            continue
        setattr(entity, field, next_value)
        changed.append(field)
        data[field] = {"before": audit_value(previous_value), "after": audit_value(next_value)}
    return changed, data


def add_change_log(
    db: AsyncSession,
    *,
    workspace_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    changed_fields: Iterable[str],
    change_data: dict[str, dict[str, Any]],
    actor_user_id: int | None,
    summary: str | None = None,
) -> GaiboChangeLog | None:
    fields = list(changed_fields)
    if not fields:
        return None
    log = GaiboChangeLog(
        workspace_id=workspace_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changed_fields=fields,
        change_data=change_data,
        summary=summary or f"{action}: {', '.join(fields)}",
        actor_user_id=actor_user_id,
    )
    db.add(log)
    return log


def creation_change_data(values: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {field: {"before": None, "after": audit_value(value)} for field, value in values.items()}


def normalize_currency(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise GaiboValidationError("币种必须为 3 位字母代码")
    return normalized


def require_text(value: str | None, label: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise GaiboValidationError(f"{label}不能为空")
    return normalized


def validate_package_item_reference(requirement_id: int | None, unlinked_customer_part_number: str | None) -> None:
    if requirement_id is None and not (unlinked_customer_part_number or "").strip():
        raise GaiboValidationError("组成项必须关联客户件号或填写未建档件号")
    if requirement_id is not None and (unlinked_customer_part_number or "").strip():
        raise GaiboValidationError("已关联组成项不能同时填写未建档件号")


async def mark_route_current(db: AsyncSession, requirement_id: int, route_id: int) -> None:
    """Make one route current and clear older versions in one transaction."""
    await db.execute(
        update(GaiboProcessRoute)
        .where(GaiboProcessRoute.requirement_id == requirement_id, GaiboProcessRoute.id != route_id)
        .values(is_current=False)
    )

