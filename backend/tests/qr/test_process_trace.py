"""Ordered process and trace contracts against owned PostgreSQL."""
import asyncio

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import product_box as m
from app.models.production import PlanMachineAssignment
from app.models.warehouse import Material, MaterialBatch, BatchStatus, IQCResult
from app.services import product_box_service as boxes, product_production_service as production
from app.services import product_process_service as service
from app.services.qr_transaction_service import QrError
from .service_fixtures import create_service_fixture, seed_service_fixture
from .test_production import actor, selected, bound, save, complete


async def route_fixture(db, first_output="CUT"):
    db.add(m.ProductRouteRevision(id=704, route_code="TRACE-ROUTE", revision=1, product_code="B",
        steps_json=[{"code": c, "name": c, "machine_ids": [601, 602]} for c in ("CUT", "FINISH", "PACK")],
        first_output_process_code=first_output, is_published=True, created_by=102))
    db.add(PlanMachineAssignment(id=503, plan_id=401, machine_id=602, assigned_qty=100))
    await db.flush()
    await db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id == 801).values(route_revision_id=704))
    await db.execute(update(m.MachineOrderProcessState).where(m.MachineOrderProcessState.id == 1001).values(route_revision_id=704))
    db.add_all([m.MachineOrderProcessState(id=1003, assignment_id=503, order_product_id=801,
        route_revision_id=704, process_code="FINISH", target_qty=100),
        m.MachineOrderProcessState(id=1004, assignment_id=501, order_product_id=801,
        route_revision_id=704, process_code="PACK", target_qty=100)])
    db.add(Material(id=850, material_no="TRACE-MATERIAL", name="追溯冷轧钢", grade="SPCC"))
    await db.flush()
    db.add(MaterialBatch(id=9501, qr_uid="TRACE-MOTHER", material_id=850, batch_no="TRACE-MOTHER", qr_code="MAT:9501:20261026",
        gross_weight=100, current_weight=70, status=BatchStatus.AVAILABLE, iqc_result=IQCResult.PASSED))
    await db.flush()
    db.add(MaterialBatch(id=9502, qr_uid="TRACE-CHILD", material_id=850, batch_no="TRACE-CHILD", qr_code="MAT:9502:20261026",
        gross_weight=30, current_weight=30, parent_batch_id=9501, status=BatchStatus.AVAILABLE, iqc_result=IQCResult.PASSED))
    await db.flush()


async def ready(db, qty=30, first_output="CUT"):
    await route_fixture(db, first_output)
    box = (await bound(db))[0]
    selection = await selected(db)
    result = await production.save_quantity(db, actor(), box_id=int(box["id"]), context_id=int(selection["context"]["id"]),
        current_qty=qty, expected_version=box["version"], state_version=selection["state"]["version"],
        material_batch_id=9502, idempotency_key="trace-initial-quantity")
    target = await selected(db, machine=602, assignment=503, process="FINISH", key="trace-select-finish")
    return result, target


async def advance(db, current, target, key="trace-advance-finish", who=101):
    return await service.advance(db, actor(who), box_id=int(current["box"]["id"]),
        context_id=int(target["context"]["id"]), expected_version=current["box"]["version"],
        state_version=target["state"]["version"], idempotency_key=key)


@pytest.mark.asyncio
async def test_same_identity_completed_machine_can_advance_without_second_output(service_db):
    current, target = await ready(service_db)
    await complete(service_db, current["context"])
    result = await advance(service_db, current, target)
    assert result["box"]["qr_payload"] == current["box"]["qr_payload"]
    assert result["box"]["current_process_code"] == "FINISH" and result["box"]["next_process_code"] == "PACK"
    assert result["quantity"]["input_qty"] == result["quantity"]["current_qty"] == 30
    assert result["quantity"]["material_batch_id"] == 9502
    assert result["quantity"]["source_quantity_id"] == current["quantity"]["id"]
    assert (await advance(service_db, current, target)) == result
    result = await save(service_db, result["box"], result, 25, key="trace-finish-quantity")
    pack = await selected(service_db, process="PACK", key="trace-select-pack")
    packed = await advance(service_db, result, pack, key="trace-advance-pack")
    assert packed["quantity"]["input_qty"] == 25
    assert await service_db.scalar(select(func.count()).select_from(m.ProductOutputAllocation)) == 1
    assert packed["allocation"]["available_qty"] == 30
    events = (await service.events(service_db, actor(), box_id=int(result["box"]["id"]), page_size=100))["items"]
    handoffs = [e for e in events if e["event_type"] == "process_start"]
    assert len(handoffs) == 2 and handoffs[0]["before_snapshot"]["process_code"] == "FINISH"
    assert handoffs[1]["after_snapshot"]["input_qty"] == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["skip", "same", "other_user", "wrong_order", "stale_box", "stale_state", "zero", "source_paused", "target_paused"])
async def test_advance_rejects_without_mutating_facts(service_db, failure):
    current, target = await ready(service_db, 0 if failure == "zero" else 30)
    if failure == "skip":
        target = await selected(service_db, process="PACK", key="trace-skip-pack")
    elif failure == "same":
        target = current
    elif failure == "wrong_order":
        target = await selected(service_db, machine=602, assignment=502, product=803, key="trace-wrong-order")
    elif failure == "stale_box":
        current["box"]["version"] = 1
    elif failure == "stale_state":
        target["state"]["version"] = 99
    elif failure.endswith("paused"):
        service_db.add(m.CoilSpecException(order_id=401, state_id=1001 if failure == "source_paused" else 1003,
            material_batch_id=9502, expected_spec={}, actual_spec={}, active_dedupe_key=failure,
            status="confirmed", resolution="pause", created_by=101, confirmed_by=102,
            confirmed_at=func.clock_timestamp()))
        await service_db.flush()
    before = await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent))
    with pytest.raises(QrError):
        await advance(service_db, current, target, who=102 if failure == "other_user" else 101)
    await service_db.refresh(await service_db.get(m.ProductBox, int(current["box"]["id"])))
    assert (await service_db.get(m.ProductBox, int(current["box"]["id"]))).current_process_code == "CUT"
    assert await service_db.scalar(select(func.count()).select_from(m.BoxProcessQuantity)) == 1
    assert await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent)) == before


@pytest.mark.asyncio
async def test_trace_material_ancestry_order_scope_latest_event_and_pagination(service_db):
    current, target = await ready(service_db)
    await advance(service_db, current, target)
    trace = await service.trace_box(service_db, actor(104), box_id=int(current["box"]["id"]))
    assert trace["order"]["plan_no"] == "PP-000401" and trace["route"]["revision"] == 1
    assert [b["batch_no"] for b in trace["materials"]] == ["TRACE-CHILD", "TRACE-MOTHER"]
    assert trace["missing_material_source"] is False and len(trace["quantities"]) == 2
    assert trace["latest_event"]["event_type"] == "process_start"
    scan = await boxes.scan_box(service_db, actor(), qr_payload=current["box"]["qr_payload"])
    assert scan["latest_event"]["event_type"] == "process_start" and scan["allowed_actions"] == ["trace"]
    first = await service.events(service_db, actor(), box_id=int(current["box"]["id"]), page_size=1)
    second = await service.events(service_db, actor(), box_id=int(current["box"]["id"]), page_size=1, before_id=int(first["next_cursor"]))
    assert first["items"][0]["id"] != second["items"][0]["id"]
    for operation in (service.trace_box, service.events):
        with pytest.raises(QrError) as caught:
            await operation(service_db, actor(105), box_id=int(current["box"]["id"]))
        assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_later_first_output_and_material_identity_are_preserved(service_db):
    current, target = await ready(service_db, first_output="FINISH")
    assert current["allocation"] is None
    entered = await advance(service_db, current, target)
    saved = await save(service_db, entered["box"], entered, 27, key="trace-later-first-output")
    assert saved["quantity"]["source_quantity_id"] == saved["quantity"]["id"]
    assert saved["allocation"]["available_qty"] == 27
    with pytest.raises(QrError):
        await production.save_quantity(service_db, actor(), box_id=int(saved["box"]["id"]),
            context_id=int(target["context"]["id"]), current_qty=28, material_batch_id=9501,
            expected_version=saved["box"]["version"], state_version=saved["state"]["version"], idempotency_key="trace-change-source")


@pytest.mark.asyncio
async def test_advance_audit_failure_rolls_back_and_other_machine_cannot_duplicate_source(service_db, monkeypatch):
    current, target = await ready(service_db)
    async def fail(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")
    monkeypatch.setattr(service, "write_audit", fail)
    with pytest.raises(RuntimeError):
        await advance(service_db, current, target)
    assert await service_db.scalar(select(func.count()).select_from(m.BoxProcessQuantity)) == 1
    service_db.add(m.MachineOrderProcessState(id=1005, assignment_id=503, order_product_id=801,
        route_revision_id=704, process_code="CUT", target_qty=0))
    await service_db.flush()
    other = await selected(service_db, machine=602, assignment=503, process="CUT", key="trace-other-cut")
    with pytest.raises(QrError):
        await save(service_db, current["box"], other, 30, key="trace-duplicate-first-output")
    assert await service_db.scalar(select(func.count()).select_from(m.ProductOutputAllocation)) == 1


@pytest.mark.asyncio
async def test_concurrent_advances_create_one_handoff(qr_database_factory):
    with qr_database_factory() as engine:
        with engine.begin() as connection:
            create_service_fixture(connection)
            seed_service_fixture(connection)
        async_engine = create_async_engine(engine.url.set(drivername="postgresql+asyncpg"), echo=False, poolclass=NullPool)
        sessions = async_sessionmaker(async_engine, expire_on_commit=False)
        try:
            async with sessions() as db:
                current, target = await ready(db)
                await db.commit()
            async def write(index):
                async with sessions() as db:
                    try:
                        result = await advance(db, current, target, key=f"trace-concurrent-{index}")
                        await db.commit()
                        return result
                    except QrError as error:
                        await db.rollback()
                        return error
            results = await asyncio.gather(write(1), write(2))
            assert sum(isinstance(result, dict) for result in results) == 1
            async with sessions() as db:
                assert await db.scalar(select(func.count()).select_from(m.BoxProcessQuantity)) == 2
                assert await db.scalar(select(func.count()).select_from(m.ProductOutputAllocation)) == 1
        finally:
            await async_engine.dispose()


@pytest.mark.asyncio
async def test_incomplete_legacy_material_lineage_is_reported_honestly(service_db):
    current, _ = await ready(service_db)
    await service_db.execute(update(MaterialBatch).where(MaterialBatch.id == 9501).values(parent_batch_id=9502))
    trace = await service.trace_box(service_db, actor(), box_id=int(current["box"]["id"]))
    assert trace["material_lineage_incomplete"] and len(trace["materials"]) == 2
    await service_db.execute(update(MaterialBatch).where(MaterialBatch.id == 9501).values(parent_batch_id=999999,
        material_id=None, material_name="历史物料", current_weight=None))
    trace = await service.trace_box(service_db, actor(), box_id=int(current["box"]["id"]))
    assert trace["material_lineage_incomplete"]
    assert trace["materials"][1]["material_name"] == "历史物料" and trace["materials"][1]["current_weight"] is None
    await service_db.execute(update(m.BoxProcessQuantity).values(material_batch_id=None))
    trace = await service.trace_box(service_db, actor(), box_id=int(current["box"]["id"]))
    assert trace["missing_material_source"] and trace["materials"] == []


@pytest.mark.asyncio
async def test_historical_recount_does_not_rewrite_entered_process_or_allocation(service_db):
    current, target = await ready(service_db)
    completed = await complete(service_db, current["context"])
    entered = await advance(service_db, current, target)
    corrected = await production.correct_quantity(service_db, actor(102), box_id=int(current["box"]["id"]),
        state_id=1001, current_qty=20, reason="Historical physical recount", expected_version=entered["box"]["version"],
        state_version=completed["state"]["version"], idempotency_key="trace-history-recount")
    assert corrected["box"]["current_qty"] == 30 and corrected["allocation"]["available_qty"] == 30
    trace = await service.trace_box(service_db, actor(), box_id=int(current["box"]["id"]))
    assert [row["current_qty"] for row in trace["quantities"]] == [20, 30]
    assert trace["quantities"][1]["input_qty"] == 30
