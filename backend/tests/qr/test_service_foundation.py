"""Behavioral acceptance for domain permissions, requests and lock conflicts."""
import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import product_box as m
from app.services import qr_permission_service as permissions
from app.services.qr_transaction_service import QrError, check_version, transactional_write, lock_rows
from .service_fixtures import ACTORS


def actor(identity):
    dept, level, _ = ACTORS[identity]
    return SimpleNamespace(id=identity, dept=dept, role_level=level)


@pytest.mark.asyncio
@pytest.mark.parametrize("identity,action,order,allowed", [
    (102, "generate", None, True), (107, "generate", None, True),
    (106, "generate", None, False), (110, "generate", None, False), (109, "generate", None, False),
    (103, "print", None, True), (104, "print", None, False),
    (104, "supervise", 401, True), (104, "supervise", 402, False),
    (105, "supervise", 401, False), (102, "supervise", 401, True),
    (106, "supervise", 401, False), (101, "supervise", 401, False),
    (106, "configure", 401, True), (101, "configure", 401, False),
    (103, "warehouse_bind", 401, True), (101, "warehouse_bind", 401, False),
    (107, "admin", None, True), (102, "admin", None, False),
])
async def test_permissions_combine_department_level_capability_and_order(service_db, identity, action, order, allowed):
    if allowed:
        await permissions.require_action(service_db, actor(identity), action, order_id=order)
    else:
        with pytest.raises(QrError) as caught:
            await permissions.require_action(service_db, actor(identity), action, order_id=order)
        assert caught.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_sales_query_scope_is_the_explicit_owner_not_creator(service_db):
    assert await permissions.can_view_order(service_db, actor(104), 401)
    assert not await permissions.can_view_order(service_db, actor(104), 402)
    assert await permissions.can_view_order(service_db, actor(109), 402)
    assert await permissions.can_view_order(service_db, actor(108), 401)


@pytest.mark.asyncio
async def test_revoked_capability_takes_effect_for_next_request(service_db):
    await permissions.require_action(service_db, actor(102), "generate")
    await service_db.execute(m.QrCapabilityGrant.__table__.update().where(
        m.QrCapabilityGrant.user_id == 102, m.QrCapabilityGrant.capability == "qr.generate",
        m.QrCapabilityGrant.revoked_at.is_(None)).values(revoked_at=text("CURRENT_TIMESTAMP"), revoked_by=107))
    with pytest.raises(QrError, match="权限"):
        await permissions.require_action(service_db, actor(102), "generate")


@pytest.mark.asyncio
async def test_idempotency_replays_and_rejects_different_content(service_db):
    calls = []
    async def operation():
        calls.append(True)
        return {"id": "synthetic-result"}
    arguments = dict(db=service_db, actor_id=102, action="test", entity_key="scope:1",
                     request_key="same-request-0001", payload={"count": 2}, operation=operation, http_status=201)
    assert await transactional_write(**arguments) == await transactional_write(**arguments)
    assert len(calls) == 1
    with pytest.raises(QrError) as caught:
        await transactional_write(**(arguments | {"payload": {"count": 3}}))
    assert caught.value.code == "IDEMPOTENCY_CONFLICT"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_failed_operation_has_no_partial_result_or_request_record(service_db):
    async def operation():
        service_db.add(m.QrPrintJob(requested_by=102, template_code="a4_3x7_v1", request_type="initial"))
        await service_db.flush()
        raise QrError(409, "STATE_CONFLICT", "synthetic rollback")
    with pytest.raises(QrError):
        await transactional_write(service_db, 102, "test", "scope:2", "failed-request-01", {}, operation)
    assert await service_db.scalar(select(m.QrPrintJob.id)) is None
    assert await service_db.scalar(select(m.QrIdempotencyRecord.id)) is None


def test_stale_versions_are_explicit_and_do_not_silently_overwrite():
    check_version(2, 2)
    with pytest.raises(QrError) as caught:
        check_version(2, 1)
    assert caught.value.status_code == 409 and caught.value.code == "STALE_BOX_VERSION"


@pytest.mark.asyncio
async def test_only_admin_with_capability_can_change_grants_and_history_is_retained(service_db):
    with pytest.raises(QrError):
        await permissions.replace_capabilities(service_db, actor(102), 101, ["qr.print"], 1, "cap-denied-0001")
    result = await permissions.replace_capabilities(service_db, actor(107), 101,
        ["qr.production", "qr.trace", "qr.split"], 1, "cap-update-0001")
    assert result["version"] == 2 and "qr.split" in result["capabilities"]
    assert await permissions.replace_capabilities(service_db, actor(107), 101,
        ["qr.production", "qr.trace", "qr.split"], 1, "cap-update-0001") == result
    with pytest.raises(QrError) as caught:
        await permissions.replace_capabilities(service_db, actor(107), 101, [], 1, "cap-update-0002")
    assert caught.value.code == "STATE_CONFLICT"
    await permissions.replace_capabilities(service_db, actor(107), 101, ["qr.production"], 2, "cap-update-0003")
    history = (await service_db.execute(select(m.QrCapabilityGrant).where(
        m.QrCapabilityGrant.user_id == 101, m.QrCapabilityGrant.capability == "qr.trace"))).scalars().all()
    assert len(history) == 1 and history[0].revoked_at is not None
