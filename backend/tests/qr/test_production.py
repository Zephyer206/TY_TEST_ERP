"""Production contracts, written before their service, against owned PostgreSQL."""
import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import product_box as m
from app.models.audit import AuditLog
from app.models.machine import Machine
from app.models.production import PlanMachineAssignment, ProductionPlan
from app.models.user import User
from app.models.warehouse import Material, MaterialBatch
from app.services import product_box_service as boxes
from app.services import product_production_service as service
from app.services.qr_transaction_service import QrError
from .service_fixtures import ACTORS, create_service_fixture, seed_service_fixture


def actor(identity=101):
    dept, level, _ = ACTORS[identity]
    return SimpleNamespace(id=identity, dept=dept, role_level=level)


def machine_qr(identity=601):
    return f"MCN:{identity}:20261025120000:machine_no=TEST-M{identity}"


async def selected(db, identity=101, *, machine=601, assignment=501, product=801, process="CUT", key="select-production-01"):
    scan = await service.scan_machine(db, actor(identity), machine_qr=machine_qr(machine))
    return await service.select_production(db, actor(identity), scan_ticket=scan["scan_ticket"],
        assignment_id=assignment, order_product_id=product, process_code=process, idempotency_key=key)


async def bound(db, count=1, *, longer_route=False):
    if longer_route:
        db.add(m.ProductRouteRevision(id=704, route_code="PRODUCTION-TEST", revision=1, product_code="B",
            steps_json=[{"code": c, "name": c, "machine_ids": [601, 602]} for c in ("CUT", "FINISH")],
            first_output_process_code="CUT", is_published=True, created_by=102))
        await db.flush()
        await db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id == 801).values(route_revision_id=704))
        await db.execute(update(m.MachineOrderProcessState).where(m.MachineOrderProcessState.id == 1001).values(route_revision_id=704))
    batch = await boxes.generate_batch(db, actor(102), count=count, idempotency_key="production-box-labels")
    result = []
    for index, item in enumerate(batch["items"]):
        result.append((await boxes.bind_box(db, actor(103), qr_payload=item["qr_payload"],
            order_product_id=801, idempotency_key=f"production-box-bind-{index}"))["box"])
    return result


async def save(db, box, selection, qty=30, *, key="production-quantity-01"):
    return await service.save_quantity(db, actor(), box_id=int(box["id"]),
        context_id=int(selection["context"]["id"]), current_qty=qty, expected_version=box["version"],
        state_version=selection["state"]["version"], idempotency_key=key)


async def complete(db, context, *, confirm=True, key="production-complete-01"):
    scan = await service.scan_machine(db, actor(), machine_qr=machine_qr(), context_id=int(context["id"]))
    return await service.complete_production(db, actor(), machine_id=601, context_id=int(context["id"]),
        confirm_quantity_difference=confirm, expected_version=scan["state"]["version"], idempotency_key=key)


@pytest.mark.asyncio
async def test_machine_ticket_explicit_multi_order_and_independent_machine_contexts(service_db):
    service_db.add(PlanMachineAssignment(id=503, plan_id=402, machine_id=601, assigned_qty=100))
    await service_db.flush()
    service_db.add(m.MachineOrderProcessState(id=1003, assignment_id=503, order_product_id=803,
        route_revision_id=703, process_code="CUT", target_qty=100))
    await service_db.flush()
    scan = await service.scan_machine(service_db, actor(), machine_qr=machine_qr())
    assert {a["order_id"] for a in scan["assignments"]} == {401, 402}
    assert scan["context"] is None and not scan["completion_intent"] and scan["scan_ticket"]
    choice = await service.select_production(service_db, actor(), scan_ticket=scan["scan_ticket"],
        assignment_id=503, order_product_id=803, process_code="CUT", idempotency_key="select-second-order")
    assert choice["context"]["order_id"] == 402 and choice["state"]["production_status"] == "pending"
    second = await selected(service_db, machine=602, assignment=502, product=803, key="select-second-machine")
    assert second["context"]["id"] != choice["context"]["id"]
    assert (await service_db.get(m.MachineProductionContext, int(choice["context"]["id"]))).closed_at is None
    assert scan["actor"]["id"] == 101 and "qr.production" in scan["capabilities"]
    assert choice["state"]["plan_no"] == "PP-000402" and choice["state"]["part_name"]
    with pytest.raises(QrError) as denied:
        await service.select_production(service_db, actor(102), scan_ticket=scan["scan_ticket"],
            assignment_id=501, order_product_id=801, process_code="CUT", idempotency_key="steal-ticket-request")
    assert denied.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_read_only_supervisor_and_owner_select_without_production_authority(service_db):
    for identity in (102, 104):
        result = await selected(service_db, identity, key=f"readonly-select-{identity}")
        assert result["state"]["production_status"] == "pending"
        assert "quantity" not in result["state"]["allowed_actions"]
        assert "complete" not in result["state"]["allowed_actions"]
    with pytest.raises(QrError):
        await selected(service_db, 105, key="other-owner-select")
    assert (await service_db.get(m.MachineOrderProcessState, 1001)).production_status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ["MAT:601:20261025", "MCN:01:20261025120000", "MCN:601:20260230120000",
    "MCN:601:20261025120000:machine_no=WRONG", "MCN:2147483648:20261025120000"])
async def test_invalid_machine_scan_does_not_create_context(service_db, payload):
    with pytest.raises(QrError):
        await service.scan_machine(service_db, actor(), machine_qr=payload)
    assert await service_db.scalar(select(func.count()).select_from(m.MachineProductionContext)) == 0


@pytest.mark.asyncio
async def test_quantity_overwrites_and_replay_is_one_fact_and_default_allocation(service_db):
    box = (await bound(service_db))[0]
    selection = await selected(service_db)
    first = await save(service_db, box, selection)
    assert first["box"]["current_qty"] == first["quantity"]["current_qty"] == 30
    assert first["allocation"]["order_qty"] == 30 and first["allocation"]["stock_qty"] == 0
    assert first["quantity"]["source_quantity_id"] == first["quantity"]["id"]
    assert (await save(service_db, box, selection)) == first
    second = await save(service_db, first["box"], first, 25, key="production-quantity-02")
    assert second["box"]["current_qty"] == second["state"]["current_qty"] == 25
    assert second["quantity"]["id"] == first["quantity"]["id"]
    assert second["allocation"]["order_qty"] == 25 and second["state"]["production_status"] == "in_progress"
    assert second["state"]["boxes"][0]["quantity_id"] == second["quantity"]["id"]
    assert second["state"]["boxes"][0]["box_no"] == box["box_no"]
    assert await service_db.scalar(select(func.count()).select_from(m.BoxProcessQuantity)) == 1
    assert await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent).where(
        m.ProductFlowEvent.event_type == "qty_save")) == 2
    for kwargs in ({"expected_version": 1, "state_version": second["state"]["version"]},
                   {"expected_version": second["box"]["version"], "state_version": 1}):
        with pytest.raises(QrError) as caught:
            await service.save_quantity(service_db, actor(), box_id=int(box["id"]), context_id=int(selection["context"]["id"]),
                current_qty=40, idempotency_key=f"stale-{kwargs['expected_version']}-{kwargs['state_version']}", **kwargs)
        assert caught.value.code in {"STALE_BOX_VERSION", "STATE_CONFLICT"}


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [-1, True, 1.5, "30", 2147483648])
async def test_quantity_strict_integer_and_rollback(service_db, invalid):
    box = (await bound(service_db))[0]
    selection = await selected(service_db)
    with pytest.raises(QrError) as caught:
        await save(service_db, box, selection, invalid)
    assert caught.value.code == "INVALID_QUANTITY"
    assert (await service_db.get(m.ProductBox, int(box["id"]))).current_qty == 0
    assert await service_db.scalar(select(func.count()).select_from(m.BoxProcessQuantity)) == 0


@pytest.mark.asyncio
async def test_explicit_historical_route_selection_keeps_existing_box_producible(service_db):
    box = (await bound(service_db))[0]
    service_db.add(m.ProductRouteRevision(id=704, route_code="PRODUCTION-REVISION", revision=2,
        product_code="B", steps_json=[{"code": "CUT", "machine_ids": [601]}],
        first_output_process_code="CUT", is_published=True, created_by=102))
    await service_db.flush()
    await service_db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id == 801).values(route_revision_id=704))
    scan = await service.scan_machine(service_db, actor(), machine_qr=machine_qr())
    selected_old = await service.select_production(service_db, actor(), scan_ticket=scan["scan_ticket"],
        assignment_id=501, order_product_id=801, process_code="CUT", state_id=1001, idempotency_key="old-route-selection")
    assert "bind" not in selected_old["state"]["allowed_actions"]
    result = await save(service_db, box, selected_old, 25)
    assert result["box"]["route_revision_id"] == "701" and result["box"]["current_qty"] == 25


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["expired", "other_user", "closed_assignment", "closed_plan", "wrong_route"])
async def test_invalid_live_context_cannot_save(service_db, failure):
    box = (await bound(service_db))[0]
    selection = await selected(service_db)
    context_id = int(selection["context"]["id"])
    if failure == "expired":
        await service_db.execute(update(m.MachineProductionContext).where(m.MachineProductionContext.id == context_id).values(
            scanned_at=func.clock_timestamp()+text("interval '-31 minutes'"), expires_at=func.clock_timestamp()+text("interval '-1 minute'")))
    elif failure == "other_user":
        await service_db.execute(update(m.MachineProductionContext).where(m.MachineProductionContext.id == context_id).values(user_id=102))
    elif failure == "closed_assignment":
        await service_db.execute(update(PlanMachineAssignment).where(PlanMachineAssignment.id == 501).values(is_active=False))
    elif failure == "closed_plan":
        await service_db.execute(update(ProductionPlan).where(ProductionPlan.id == 401).values(status="closed"))
    else:
        await service_db.execute(update(m.ProductBox).where(m.ProductBox.id == int(box["id"])).values(route_revision_id=703))
    with pytest.raises(QrError):
        await save(service_db, box, selection)
    assert await service_db.scalar(select(func.count()).select_from(m.BoxProcessQuantity)) == 0


@pytest.mark.asyncio
async def test_complete_requires_fresh_rescan_difference_confirmation_and_closes_only_selected_state(service_db):
    box = (await bound(service_db))[0]
    choice = await selected(service_db)
    saved = await save(service_db, box, choice)
    other = await selected(service_db, machine=602, assignment=502, product=803, key="other-machine-context")
    context_id = int(choice["context"]["id"])
    with pytest.raises(QrError):
        await service.complete_production(service_db, actor(), machine_id=601, context_id=context_id,
            confirm_quantity_difference=True, expected_version=saved["state"]["version"], idempotency_key="complete-without-rescan")
    with pytest.raises(QrError) as difference:
        await complete(service_db, choice["context"], confirm=False)
    assert difference.value.details["confirmation_required"] is True
    assert (await service_db.get(m.MachineOrderProcessState, 1001)).production_status == "in_progress"
    result = await complete(service_db, choice["context"])
    assert result["state"]["production_status"] == "completed" and result["state"]["current_qty"] == 30
    assert result["state"]["difference_qty"] == -70 and result["context"]["closed_at"]
    assert (await service_db.get(m.MachineProductionContext, int(other["context"]["id"]))).closed_at is None
    assert (await service_db.get(m.MachineOrderProcessState, 1002)).production_status == "pending"
    assert (await service_db.get(ProductionPlan, 401)).status == "planned"
    assert (await service_db.get(m.ProductBox, int(box["id"]))).lifecycle_status == "active"
    replay = await service.complete_production(service_db, actor(), machine_id=601, context_id=context_id,
        confirm_quantity_difference=True, expected_version=saved["state"]["version"], idempotency_key="production-complete-01")
    assert replay == result
    with pytest.raises(QrError):
        await save(service_db, saved["box"], saved, 20, key="worker-after-completion")


@pytest.mark.asyncio
async def test_quantity_write_invalidates_prior_completion_intent(service_db):
    box = (await bound(service_db))[0]
    choice = await selected(service_db)
    first = await save(service_db, box, choice)
    await service.scan_machine(service_db, actor(), machine_qr=machine_qr(), context_id=int(choice["context"]["id"]))
    second = await save(service_db, first["box"], first, 25, key="change-after-intent")
    assert second["context"]["completion_scan_at"] is None
    with pytest.raises(QrError):
        await service.complete_production(service_db, actor(), machine_id=601, context_id=int(choice["context"]["id"]),
            confirm_quantity_difference=True, expected_version=second["state"]["version"], idempotency_key="old-intent-complete")


@pytest.mark.asyncio
async def test_manual_order_stock_allocation_owner_scope_and_atomic_quantity_conflict(service_db):
    await service_db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id == 801).values(target_qty=70))
    box = (await bound(service_db))[0]
    choice = await selected(service_db)
    saved = await save(service_db, box, choice, 80)
    allocation = saved["allocation"]
    assert (allocation["order_qty"], allocation["stock_qty"]) == (70, 10)
    adjusted = await service.allocate_output(service_db, actor(104), source_quantity_id=int(saved["quantity"]["id"]),
        order_qty=60, stock_qty=20, expected_version=allocation["version"], idempotency_key="manual-owner-allocation")
    assert adjusted["manually_adjusted"] and adjusted["order_qty"] == 60 and not adjusted["has_downstream"]
    assert "allocate" in adjusted["allowed_actions"]
    for identity in (101, 103, 105, 107):
        with pytest.raises(QrError) as denied:
            await service.allocate_output(service_db, actor(identity), source_quantity_id=int(saved["quantity"]["id"]),
                order_qty=50, stock_qty=30, expected_version=adjusted["version"], idempotency_key=f"wrong-allocation-{identity}")
        assert denied.value.code == "FORBIDDEN"
    with pytest.raises(QrError):
        await save(service_db, saved["box"], saved, 50, key="quantity-conflicts-manual")
    current = await service_db.get(m.ProductBox, int(box["id"]), populate_existing=True)
    assert current.current_qty == 80 and current.version == saved["box"]["version"]
    assert (await service_db.get(m.ProductOutputAllocation, int(adjusted["id"]))).order_qty == 60


@pytest.mark.asyncio
async def test_supervisor_correction_requires_reason_completed_state_and_preserves_downstream(service_db):
    box = (await bound(service_db, longer_route=True))[0]
    choice = await selected(service_db)
    saved = await save(service_db, box, choice)
    completed = await complete(service_db, choice["context"])
    # A persisted later step represents the downstream fact owned by the future
    # advancement workflow; historical correction must never rewrite it.
    service_db.add(m.MachineOrderProcessState(id=1004, assignment_id=501, order_product_id=801,
        route_revision_id=704, process_code="FINISH", target_qty=100))
    await service_db.flush()
    downstream = m.BoxProcessQuantity(state_id=1004, box_id=int(box["id"]), current_qty=25,
        input_qty=30, source_quantity_id=int(saved["quantity"]["id"]), updated_by=101)
    service_db.add(downstream)
    await service_db.execute(update(m.ProductBox).where(m.ProductBox.id == int(box["id"])).values(
        current_process_code="FINISH", current_qty=25))
    await service_db.flush()
    request = dict(box_id=int(box["id"]), state_id=1001, current_qty=20,
        expected_version=saved["box"]["version"], state_version=completed["state"]["version"])
    with pytest.raises(QrError):
        await service.correct_quantity(service_db, actor(102), reason="  ", idempotency_key="empty-correction-reason", **request)
    for identity in (101, 104, 107):
        with pytest.raises(QrError):
            await service.correct_quantity(service_db, actor(identity), reason="Recount", idempotency_key=f"wrong-corrector-{identity}", **request)
    result = await service.correct_quantity(service_db, actor(102), reason="Recount historical output",
        idempotency_key="supervisor-correction-01", **request)
    assert result["quantity"]["current_qty"] == 20 and result["state"]["production_status"] == "completed"
    assert result["box"]["current_qty"] == 25 and result["box"]["current_process_code"] == "FINISH"
    assert (await service_db.get(m.BoxProcessQuantity, downstream.id)).current_qty == 25
    assert result["allocation"]["available_qty"] == 30 and result["allocation"]["has_downstream"]
    assert result["allocation"]["allowed_actions"] == []
    event = await service_db.scalar(select(m.ProductFlowEvent).where(m.ProductFlowEvent.event_type == "quantity_correction"))
    assert event.before_qty == 30 and event.after_qty == 20 and event.remark == "Recount historical output"


@pytest.mark.asyncio
async def test_revoked_production_cannot_replay_successful_quantity(service_db):
    box = (await bound(service_db))[0]
    choice = await selected(service_db)
    await save(service_db, box, choice)
    await service_db.execute(update(m.QrCapabilityGrant).where(m.QrCapabilityGrant.user_id == 101,
        m.QrCapabilityGrant.capability == "qr.production").values(revoked_by=107, revoked_at=func.clock_timestamp()))
    with pytest.raises(QrError) as denied:
        await save(service_db, box, choice)
    assert denied.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_pause_blocks_quantity_and_completion_without_mutating_facts(service_db):
    box = (await bound(service_db))[0]
    choice = await selected(service_db)
    service_db.add(Material(id=8001, material_no="PRODUCTION-PAUSE", name="Synthetic coil", grade="QA"))
    await service_db.flush()
    service_db.add(MaterialBatch(id=9001, qr_uid="production-pause", material_id=8001, gross_weight=10, current_weight=10))
    await service_db.flush()
    service_db.add(m.CoilSpecException(order_id=401, state_id=1001, material_batch_id=9001,
        expected_spec={}, actual_spec={}, active_dedupe_key="p"*64, status="confirmed", resolution="pause",
        created_by=101, confirmed_by=102, confirmed_at=func.clock_timestamp()))
    await service_db.flush()
    with pytest.raises(QrError) as paused:
        await save(service_db, box, choice)
    assert paused.value.code == "STATE_CONFLICT"
    with pytest.raises(QrError):
        await complete(service_db, choice["context"])
    assert await service_db.scalar(select(func.count()).select_from(m.BoxProcessQuantity)) == 0


@pytest.mark.asyncio
async def test_quantity_and_allocation_roll_back_if_audit_fails(service_db, monkeypatch):
    box = (await bound(service_db))[0]
    choice = await selected(service_db)
    async def fail(*args, **kwargs):
        await service_db.flush()
        raise QrError(409, "STATE_CONFLICT", "Synthetic rollback")
    monkeypatch.setattr(service, "write_audit", fail)
    with pytest.raises(QrError):
        await save(service_db, box, choice)
    assert (await service_db.get(m.ProductBox, int(box["id"]), populate_existing=True)).current_qty == 0
    assert (await service_db.get(m.MachineOrderProcessState, 1001, populate_existing=True)).production_status == "pending"
    assert await service_db.scalar(select(func.count()).select_from(m.BoxProcessQuantity)) == 0
    assert await service_db.scalar(select(func.count()).select_from(m.ProductOutputAllocation)) == 0


@pytest.mark.asyncio
async def test_concurrent_first_outputs_cannot_overallocate_remaining_demand(qr_database_factory):
    with qr_database_factory() as sync_engine:
        with sync_engine.begin() as connection:
            create_service_fixture(connection)
            seed_service_fixture(connection)
            connection.execute(User.__table__.insert().values(id=111, username="production-synthetic-111",
                password="synthetic-unusable-hash", dept="prod", role_level=1))
            connection.execute(m.QrCapabilityGrant.__table__.insert().values(user_id=111, capability="qr.production", granted_by=107))
        engine = create_async_engine(sync_engine.url.set(drivername="postgresql+asyncpg"), echo=False, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                pair = await bound(db, 2)
                first = await selected(db)
                scan = await service.scan_machine(db, SimpleNamespace(id=111, dept="prod", role_level=1), machine_qr=machine_qr())
                second = await service.select_production(db, SimpleNamespace(id=111, dept="prod", role_level=1),
                    scan_ticket=scan["scan_ticket"], assignment_id=501, order_product_id=801, process_code="CUT",
                    idempotency_key="second-operator-select")
                await db.commit()
            async def attempt(index, context, who):
                async with AsyncSession(engine, expire_on_commit=False) as db:
                    try:
                        user = await db.get(User, who)
                        # State versions serialize both writes; refresh the
                        # version after acquiring the shared demand lock.
                        from app.services.qr_transaction_service import lock_rows
                        await lock_rows(db, order_products=[801])
                        state = await db.get(m.MachineOrderProcessState, 1001, populate_existing=True)
                        result = await service.save_quantity(db, user, box_id=int(pair[index]["id"]),
                            context_id=int(context["context"]["id"]), current_qty=80, expected_version=1,
                            state_version=state.version, idempotency_key=f"parallel-output-{index}")
                        await db.commit()
                        return result
                    except Exception:
                        await db.rollback()
                        raise
            results = await asyncio.wait_for(asyncio.gather(attempt(0, first, 101), attempt(1, second, 111)), timeout=30)
            assert sorted(r["allocation"]["order_qty"] for r in results) == [20, 80]
            assert sum(r["allocation"]["stock_qty"] for r in results) == 60
            async with AsyncSession(engine) as db:
                assert await db.scalar(select(func.sum(m.ProductOutputAllocation.order_qty))) == 100
        finally:
            await engine.dispose()
