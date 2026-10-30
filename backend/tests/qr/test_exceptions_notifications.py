"""Spec decisions, scoped blocking and durable in-app delivery on owned PostgreSQL."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app.models import product_box as m
from app.models.production import ProductionPlan
from app.models.warehouse import MaterialBatch
from app.services import coil_exception_service as service, notification_service as notifications
from app.services import product_production_service as production
from app.services.qr_transaction_service import QrError
from .test_production import actor, bound, selected
from .test_process_trace import route_fixture


async def prepared(db, *, matched=False):
    await route_fixture(db)
    await db.execute(update(ProductionPlan).where(ProductionPlan.id == 401).values(
        material_name_snapshot="追溯冷轧钢", twp_thickness=0.8, twp_width=1000))
    await db.execute(update(MaterialBatch).where(MaterialBatch.id.in_([9501, 9502])).values(
        thickness=0.8, width=1000))
    if not matched:
        await db.execute(update(MaterialBatch).where(MaterialBatch.id == 9502).values(width=900))
    box = (await bound(db))[0]
    choice = await selected(db)
    return box, choice


async def check(db, box, choice, *, proceed=True, key="exception-create-test", who=101):
    return await service.create_exception(db, actor(who), context_id=int(choice["context"]["id"]),
        material_batch_id=9502, product_box_id=int(box["id"]), continue_production=proceed, idempotency_key=key)


async def confirm(db, item, resolution="pause", *, who=102, key="exception-confirm-test"):
    return await service.confirm_exception(db, actor(who), exception_id=int(item["id"]), resolution=resolution,
        remark=None, expected_version=item["version"], idempotency_key=key)


@pytest.mark.asyncio
@pytest.mark.parametrize("matched", [True, False])
async def test_preview_compares_server_snapshots_without_recording_production(service_db, matched):
    box, choice = await prepared(service_db, matched=matched)
    result = await check(service_db, box, choice, proceed=False)
    assert result["matches"] is matched and result["requires_confirmation"] is not matched
    assert result["expected_spec"]["width"] == "1000.000"
    assert result["actual_spec"]["width"] == ("1000.000" if matched else "900.000")
    assert await service_db.scalar(select(func.count()).select_from(m.CoilSpecException)) == 0
    assert await service_db.scalar(select(func.count()).select_from(m.NotificationOutbox)) == 0


@pytest.mark.asyncio
async def test_mismatch_continue_records_two_groups_and_allows_pending_production(service_db):
    box, choice = await prepared(service_db)
    preview = await check(service_db, box, choice, proceed=False, key="exception-preview-first")
    assert preview["requires_confirmation"]
    with pytest.raises(QrError):
        await production.save_quantity(service_db, actor(), box_id=int(box["id"]), context_id=int(choice["context"]["id"]),
            current_qty=12, material_batch_id=9502, expected_version=box["version"],
            state_version=choice["state"]["version"], idempotency_key="missing-exception-decision")
    result = await check(service_db, box, choice)
    assert result["exception"]["status"] == "pending_confirmation" and result["production_allowed"]
    assert {x["group_type"] for x in result["exception"]["recipient_groups"]} == {"supervisor", "business_owner"}
    assert await service_db.scalar(select(func.count()).select_from(m.NotificationOutbox)) == 2
    repeated = await check(service_db, box, choice, key="same-active-exception")
    assert repeated["exception"]["id"] == result["exception"]["id"]
    assert await service_db.scalar(select(func.count()).select_from(m.CoilSpecException)) == 1
    state = await service_db.get(m.MachineOrderProcessState, 1001, populate_existing=True)
    saved = await production.save_quantity(service_db, actor(), box_id=int(box["id"]), context_id=int(choice["context"]["id"]),
        current_qty=12, material_batch_id=9502, expected_version=box["version"], state_version=state.version,
        idempotency_key="pending-exception-quantity")
    assert saved["box"]["current_qty"] == 12


@pytest.mark.asyncio
@pytest.mark.parametrize("resolution", ["accept_continue", "pause", "reconfirm_coil"])
async def test_owner_confirmation_is_one_decision_and_pause_is_state_scoped(service_db, resolution):
    box, choice = await prepared(service_db)
    item = (await check(service_db, box, choice))["exception"]
    decided = await confirm(service_db, item, resolution, who=104)
    assert decided["confirmed_by"] == 104 and decided["remark"] is None
    assert decided["status"] == "confirmed" and decided["resolution"] == resolution
    assert await production.paused(service_db, 1001) is (resolution != "accept_continue")
    assert not await production.paused(service_db, 1002)
    with pytest.raises(QrError):
        await confirm(service_db, item, "pause", who=102, key="second-person-decision")
    assert await service_db.scalar(select(func.count()).select_from(m.QrNotification)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("who", [101, 103, 105, 107, 108])
async def test_confirmation_requires_current_supervisor_or_order_owner(service_db, who):
    box, choice = await prepared(service_db)
    item = (await check(service_db, box, choice))["exception"]
    with pytest.raises(QrError):
        await confirm(service_db, item, who=who)
    assert (await service_db.get(m.CoilSpecException, int(item["id"]))).status == "pending_confirmation"


@pytest.mark.asyncio
async def test_pause_resume_requires_matching_recheck_and_preserves_resolution(service_db):
    box, choice = await prepared(service_db)
    item = await confirm(service_db, (await check(service_db, box, choice))["exception"])
    with pytest.raises(QrError):
        await service.resume_exception(service_db, actor(102), exception_id=int(item["id"]),
            rechecked_material_batch_id=9502, reason="Rechecked", expected_version=item["version"], idempotency_key="resume-wrong-spec")
    resumed = await service.resume_exception(service_db, actor(104), exception_id=int(item["id"]),
        rechecked_material_batch_id=9501, reason="Matched mother coil verified", expected_version=item["version"],
        idempotency_key="resume-right-spec")
    assert resumed["resolution"] == "pause" and resumed["released_by"] == 104
    assert resumed["rechecked_material_batch_id"] == 9501 and not await production.paused(service_db, 1001)


@pytest.mark.asyncio
async def test_missing_recipient_groups_are_retained_and_backfilled_once(service_db):
    box, choice = await prepared(service_db)
    await service_db.execute(update(m.ProductOrderContext).where(m.ProductOrderContext.order_id == 401).values(business_owner_id=None))
    await service_db.execute(update(m.QrCapabilityGrant).where(m.QrCapabilityGrant.capability == "qr.supervise").values(
        revoked_at=func.clock_timestamp(), revoked_by=107))
    result = await check(service_db, box, choice)
    assert {x["resolution_status"] for x in result["exception"]["recipient_groups"]} == {"pending_configuration"}
    assert await service_db.scalar(select(func.count()).select_from(m.NotificationOutbox)) == 0
    await service_db.execute(update(m.ProductOrderContext).where(m.ProductOrderContext.order_id == 401).values(business_owner_id=104))
    service_db.add(m.QrCapabilityGrant(user_id=102, capability="qr.supervise", granted_by=107))
    await service_db.flush()
    await notifications.backfill_recipients(service_db)
    await notifications.backfill_recipients(service_db)
    assert await service_db.scalar(select(func.count()).select_from(m.NotificationOutbox)) == 2
    assert await service_db.scalar(select(func.count()).select_from(m.ExceptionRecipientGroup)) == 2


@pytest.mark.asyncio
async def test_delivery_retries_five_times_keeps_safe_history_and_manual_batch(service_db):
    box, choice = await prepared(service_db)
    item = (await check(service_db, box, choice))["exception"]
    row = await service_db.scalar(select(m.NotificationOutbox).order_by(m.NotificationOutbox.id).limit(1))
    # Isolate one due recipient while leaving the other pending for its own run.
    now = await service_db.scalar(select(func.clock_timestamp()))
    await service_db.execute(update(m.NotificationOutbox).where(m.NotificationOutbox.id != row.id).values(next_retry_at=now+timedelta(days=2)))
    async def fail(db, outbox):
        raise RuntimeError("Private transport detail must not be stored")
    for number, minutes in enumerate([1, 5, 15, 30, None], 1):
        await notifications.dispatch_due(service_db, now=now, sink=fail)
        await service_db.refresh(row)
        assert row.attempts == number and row.last_error == "INAPP_DELIVERY_FAILED"
        if minutes is not None:
            assert row.status == "pending" and row.next_retry_at == now+timedelta(minutes=minutes)
            now = row.next_retry_at
        else:
            assert row.status == "failed"
    await notifications.dispatch_due(service_db, now=now+timedelta(days=1), sink=fail)
    assert await service_db.scalar(select(func.count()).select_from(m.QrNotificationAttempt)) == 5
    assert (await service_db.get(m.CoilSpecException, int(item["id"]))).status == "pending_confirmation"
    with pytest.raises(QrError):
        await notifications.retry_delivery(service_db, actor(102), delivery_id=row.id, expected_version=row.version,
            idempotency_key="wrong-admin-retry")
    await notifications.retry_delivery(service_db, actor(107), delivery_id=row.id, expected_version=row.version,
        idempotency_key="authorized-manual-retry")
    await notifications.dispatch_due(service_db)
    await service_db.refresh(row)
    assert row.status == "sent" and row.retry_batch == 1 and row.attempts == 1
    assert await service_db.scalar(select(func.count()).select_from(m.QrNotificationAttempt)) == 6
    assert await service_db.scalar(select(func.count()).select_from(m.QrNotification)) == 1
    await notifications.dispatch_due(service_db)
    assert await service_db.scalar(select(func.count()).select_from(m.QrNotification)) == 1


@pytest.mark.asyncio
async def test_delivery_success_does_not_confirm_exception_and_is_recipient_scoped(service_db):
    box, choice = await prepared(service_db)
    item = (await check(service_db, box, choice))["exception"]
    await notifications.dispatch_due(service_db)
    owner = await notifications.list_notifications(service_db, actor(104))
    assert owner["total"] == 1 and owner["items"][0]["delivery_status"] == "sent"
    assert owner["items"][0]["exception"]["status"] == "pending_confirmation"
    assert (await notifications.list_notifications(service_db, actor(105)))["total"] == 0
    assert (await service_db.get(m.CoilSpecException, int(item["id"]))).confirmed_by is None


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"twp_width": None}, {"twp_thickness": 0}, {"material_name_snapshot": None}])
async def test_missing_order_spec_is_configuration_error_not_a_match(service_db, change):
    box, choice = await prepared(service_db)
    await service_db.execute(update(ProductionPlan).where(ProductionPlan.id == 401).values(**change))
    with pytest.raises(QrError):
        await check(service_db, box, choice)
    assert await service_db.scalar(select(func.count()).select_from(m.CoilSpecException)) == 0


@pytest.mark.asyncio
async def test_multiple_blocks_release_individually(service_db):
    from app.models.warehouse import BatchStatus, IQCResult
    box, choice = await prepared(service_db)
    first = await confirm(service_db, (await check(service_db, box, choice))["exception"])
    service_db.add(MaterialBatch(id=9503, qr_uid="SECOND-MISMATCH", material_id=850, batch_no="SECOND-MISMATCH",
        qr_code="MAT:9503:20261027", thickness=0.8, width=850, gross_weight=10, current_weight=10,
        status=BatchStatus.AVAILABLE, iqc_result=IQCResult.PASSED))
    await service_db.flush()
    second = (await service.create_exception(service_db, actor(), context_id=int(choice["context"]["id"]),
        material_batch_id=9503, continue_production=True, idempotency_key="second-block-create"))["exception"]
    second = await confirm(service_db, second, who=104, key="second-block-confirm")
    for index, item in enumerate([first, second]):
        await service.resume_exception(service_db, actor(102), exception_id=int(item["id"]),
            rechecked_material_batch_id=9501, reason="Rechecked matching coil", expected_version=item["version"],
            idempotency_key=f"multiple-block-resume-{index}")
        assert await production.paused(service_db, 1001) is (index == 0)


@pytest.mark.asyncio
async def test_delivery_rechecks_authority_and_requires_a_durable_task(service_db):
    box, choice = await prepared(service_db)
    await check(service_db, box, choice)
    await service_db.execute(update(m.QrCapabilityGrant).where(m.QrCapabilityGrant.user_id == 102,
        m.QrCapabilityGrant.capability == "qr.supervise").values(revoked_at=func.clock_timestamp(), revoked_by=107))
    async def no_task(db, row):
        return None
    await notifications.dispatch_due(service_db, sink=no_task)
    rows = list((await service_db.scalars(select(m.NotificationOutbox).order_by(m.NotificationOutbox.recipient_user_id))).all())
    assert [r.last_error for r in rows] == ["RECIPIENT_NO_LONGER_AUTHORIZED", "INAPP_DELIVERY_FAILED"]
    assert await service_db.scalar(select(func.count()).select_from(m.QrNotification)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["confirm", "dispatch"])
async def test_concurrent_decisions_and_workers_are_exactly_once(qr_database_factory, kind):
    import asyncio
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from .service_fixtures import create_service_fixture, seed_service_fixture
    with qr_database_factory() as engine:
        with engine.begin() as connection:
            create_service_fixture(connection); seed_service_fixture(connection)
        async_engine = create_async_engine(engine.url.set(drivername="postgresql+asyncpg"), echo=False, poolclass=NullPool)
        sessions = async_sessionmaker(async_engine, expire_on_commit=False)
        try:
            async with sessions() as db:
                box, choice = await prepared(db)
                item = (await check(db, box, choice))["exception"]
                await db.commit()
            async def execute(index):
                async with sessions() as db:
                    try:
                        result = (await confirm(db, item, who=[102, 104][index], key=f"competing-coil-{index}")) if kind == "confirm" else await notifications.dispatch_due(db)
                        await db.commit(); return result
                    except QrError as error:
                        await db.rollback(); return error
            results = await asyncio.gather(execute(0), execute(1))
            async with sessions() as db:
                if kind == "confirm":
                    assert sum(isinstance(r, dict) for r in results) == 1
                    assert await db.scalar(select(func.count()).select_from(m.QrIdempotencyRecord).where(m.QrIdempotencyRecord.action == "coil-confirm")) == 1
                else:
                    assert sum(r["sent"] for r in results) == 2
                    assert await db.scalar(select(func.count()).select_from(m.QrNotification)) == 2
                    assert await db.scalar(select(func.count()).select_from(m.QrNotificationAttempt)) == 2
        finally:
            await async_engine.dispose()


@pytest.mark.asyncio
async def test_incomplete_historical_snapshot_cannot_vacuously_match_on_resume(service_db):
    box, choice = await prepared(service_db)
    item = await confirm(service_db, (await check(service_db, box, choice))["exception"])
    await service_db.execute(update(m.CoilSpecException).where(m.CoilSpecException.id == int(item["id"])).values(expected_spec={}))
    with pytest.raises(QrError):
        await service.resume_exception(service_db, actor(102), exception_id=int(item["id"]),
            rechecked_material_batch_id=9501, reason="Missing history must not pass", expected_version=item["version"],
            idempotency_key="resume-missing-history")
    assert await production.paused(service_db, 1001)
    info = await service.exception_info(service_db, actor(102), await service_db.get(m.CoilSpecException, int(item["id"])))
    assert info["spec_incomplete"] and info["expected_spec"]["width"] is None


@pytest.mark.asyncio
async def test_spec_comparison_does_not_silently_round_away_a_difference(service_db):
    box, choice = await prepared(service_db, matched=True)
    await service_db.execute(update(MaterialBatch).where(MaterialBatch.id == 9502).values(thickness=0.8004))
    result = await check(service_db, box, choice, proceed=False)
    assert not result["matches"] and result["actual_spec"]["thickness"] == "0.8004"
