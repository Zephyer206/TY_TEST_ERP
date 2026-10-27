"""Shared transaction primitives for the product-box domain.

The caller commits once. Permission locks precede the request lock; business
rows follow demand, state, box, pool, allocation order with sorted identifiers.
No credentials, arbitrary request bodies or unknown scan strings are logged.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditAction, AuditLog
from app.models import product_box as m


class QrError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status_code, self.code, self.message, self.details = status_code, code, message, details

    def body(self) -> dict:
        body = {"code": self.code, "message": self.message}
        if self.details is not None:
            body["details"] = self.details
        return body


async def advisory_lock(db: AsyncSession, scope: str, key: Any) -> None:
    content = json.dumps([scope, key], ensure_ascii=True, separators=(",", ":"))
    lock_id = int.from_bytes(hashlib.sha256(content.encode()).digest()[:8], "big", signed=True)
    await db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})


async def lock_permission_users(db: AsyncSession, *user_ids: int) -> None:
    for identity in sorted(set(user_ids)):
        await advisory_lock(db, "qr-permission-user", identity)


def check_version(actual: int, expected: int, *, code: str = "STALE_BOX_VERSION") -> None:
    if isinstance(expected, bool) or not isinstance(expected, int) or actual != expected:
        raise QrError(409, code, "数据已更新，请重新读取后确认", {"current_version": actual})


async def lock_rows(db: AsyncSession, **groups: list[int]) -> dict[str, dict[int, Any]]:
    order = {
        "order_products": m.ProductOrderProduct, "states": m.MachineOrderProcessState,
        "boxes": m.ProductBox, "pool": m.ProductQrPoolItem, "allocations": m.ProductOutputAllocation,
    }
    if set(groups) - set(order):
        raise ValueError("Unknown QR lock group")
    result = {}
    for name, model in order.items():
        identifiers = sorted(set(groups.get(name, [])))
        if identifiers:
            rows = (await db.execute(select(model).where(model.id.in_(identifiers))
                    .order_by(model.id).with_for_update().execution_options(populate_existing=True))).scalars().all()
            result[name] = {row.id: row for row in rows}
            if len(rows) != len(identifiers):
                raise QrError(404, "ENTITY_NOT_FOUND", "关联记录不存在")
    return result


async def write_audit(db: AsyncSession, actor_id: int, action: AuditAction,
                      entity_key: str, *, before: dict | None = None, after: dict | None = None) -> None:
    # Legacy AuditLog.entity_id is int4. Keep new bigint identities in the
    # structured key, without narrowing them or changing unrelated audit schema.
    db.add(AuditLog(action=action, entity_type="product_qr", entity_id=None, user_id=actor_id,
                    old_values=before, new_values=after, changes_summary=entity_key[:500],
                    extra_data={"entity_key": entity_key}, status="success",
                    created_at=func.timezone("UTC", func.clock_timestamp())))
    await db.flush()


async def transactional_write(
    db: AsyncSession, actor_id: int, action: str, entity_key: str, request_key: str,
    payload: dict, operation: Callable[[], Awaitable[dict]], http_status: int = 200,
) -> dict:
    if not isinstance(request_key, str) or not 8 <= len(request_key) <= 120:
        raise QrError(400, "INVALID_IDEMPOTENCY_KEY", "请求标识长度须为8～120个字符")
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    await advisory_lock(db, "qr-request", [actor_id, action, entity_key, request_key])
    record = (await db.execute(select(m.QrIdempotencyRecord).where(
        m.QrIdempotencyRecord.operator_id == actor_id, m.QrIdempotencyRecord.action == action,
        m.QrIdempotencyRecord.entity_key == entity_key, m.QrIdempotencyRecord.request_key == request_key,
    ))).scalar_one_or_none()
    if record:
        if record.request_digest != digest:
            raise QrError(409, "IDEMPOTENCY_CONFLICT", "同一请求标识已用于其他内容")
        return record.response_json
    try:
        async with db.begin_nested():
            await db.execute(text("SET CONSTRAINTS pfb_pool_binding, pfb_box_binding DEFERRED"))
            response = await operation()
            # Validate JSON before recording a success that cannot be replayed.
            response = json.loads(json.dumps(response, ensure_ascii=True, allow_nan=False))
            db.add(m.QrIdempotencyRecord(operator_id=actor_id, action=action, entity_key=entity_key,
                request_key=request_key, request_digest=digest, response_json=response, http_status=http_status))
            await db.flush()
            # Validate deferred binding before returning a successful HTTP body.
            await db.execute(text("SET CONSTRAINTS pfb_pool_binding, pfb_box_binding IMMEDIATE"))
            await db.execute(text("SET CONSTRAINTS pfb_pool_binding, pfb_box_binding DEFERRED"))
        return response
    except IntegrityError:
        raise QrError(409, "STATE_CONFLICT", "关联数据发生冲突，请重新读取后确认") from None
