"""Partition physical boxes and allocations atomically; owned PostgreSQL only."""
import asyncio

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import product_box as m
from app.models.production import ProductionPlan, PlanMachineAssignment
from app.services import product_box_service as boxes, product_production_service as production
from app.services import product_process_service as processes, product_split_service as service
from app.services.qr_transaction_service import QrError
from .service_fixtures import create_service_fixture, seed_service_fixture
from .test_production import actor, selected, save, complete
from .test_process_trace import ready, advance


async def target_fixture(db, owner=104, target_qty=100):
    db.add(ProductionPlan(id=403, part_id=301, total_qty=target_qty, status="planned"))
    db.add_all([PlanMachineAssignment(id=504, plan_id=403, machine_id=601, assigned_qty=target_qty),
        PlanMachineAssignment(id=505, plan_id=403, machine_id=602, assigned_qty=target_qty)])
    await db.flush()
    db.add(m.ProductOrderContext(id=903, order_id=403, business_owner_id=owner, configured_by=102))
    db.add(m.ProductOrderProduct(id=804, order_id=403, part_id=301, product_code="B", target_qty=target_qty,
        route_revision_id=704, binding_allowed=True, configured_by=102))
    await db.flush()
    for identity, assignment, code in ((1005, 504, "CUT"), (1006, 505, "FINISH"), (1007, 504, "PACK")):
        db.add(m.MachineOrderProcessState(id=identity, assignment_id=assignment, order_product_id=804,
            route_revision_id=704, process_code=code, target_qty=target_qty))
    await db.flush()


async def prepared(db, qty=100, count=5):
    current, next_step = await ready(db, qty)
    await target_fixture(db)
    labels = await boxes.generate_batch(db, actor(102), count=count, idempotency_key="split-unused-labels")
    return current, labels["items"], next_step


async def split(db, current, child, qty=30, order_qty=None, stock_qty=0, who=103, key="split-request-001", **extra):
    box = current["box"] if "box" in current else current["parent"]
    allocation = current["allocation"] if "allocation" in current else current["parent_allocation"]
    data = dict(parent_id=int(box["id"]), child_qr_payload=child["qr_payload"], quantity=qty,
        order_qty=qty if order_qty is None else order_qty, stock_qty=stock_qty, expected_version=box["version"],
        allocation_version=allocation["version"], idempotency_key=key) | extra
    return await service.split_box(db, actor(who), **data)


@pytest.mark.asyncio
async def test_same_order_partition_replay_repeat_empty_and_material_identity(service_db):
    current, labels, _ = await prepared(service_db)
    result = await split(service_db, current, labels[0])
    assert result["parent"]["current_qty"] == 70 and result["child"]["current_qty"] == 30
    assert result["parent"]["qr_payload"] == current["box"]["qr_payload"]
    assert result["child"]["qr_payload"] == labels[0]["qr_payload"]
    assert result["child"]["order_id"] == 401 and result["child"]["current_process_code"] == "CUT"
    assert result["child_allocation"]["order_qty"] == 30
    assert result["child_allocation"]["origin_allocation_id"] == result["parent_allocation"]["id"]
    assert (await split(service_db, current, labels[0])) == result
    repeated = await split(service_db, result, labels[1], qty=20, key="split-repeat-other-label")
    assert repeated["parent"]["current_qty"] == 50
    empty = await split(service_db, repeated, labels[2], qty=50, key="split-zero-parent")
    assert empty["parent"]["current_qty"] == 0 and empty["parent"]["lifecycle_status"] == "empty"
    assert await service_db.scalar(select(func.sum(m.ProductBox.current_qty))) == 100
    assert await service_db.scalar(select(func.sum(m.ProductOutputAllocation.available_qty))) == 100
    assert set((await service_db.scalars(select(m.BoxProcessQuantity.material_batch_id))).all()) == {9502}
    with pytest.raises(QrError):
        await split(service_db, empty, labels[3], qty=1, key="empty-cannot-split")
    trace = await processes.trace_box(service_db, actor(103), box_id=int(result["child"]["id"]))
    assert trace["relations"][0]["parent_box_no"] == current["box"]["box_no"]
    assert trace["materials"][0]["batch_no"] == "TRACE-CHILD"


@pytest.mark.asyncio
async def test_partition_preserves_order_stock_and_cross_order_receives_order_quantity(service_db):
    current, labels, _ = await prepared(service_db)
    current["allocation"] = await production.allocate_output(service_db, actor(104), source_quantity_id=int(current["quantity"]["id"]),
        order_qty=60, stock_qty=40, expected_version=current["allocation"]["version"], idempotency_key="split-source-mix")
    result = await split(service_db, current, labels[0], qty=30, order_qty=20, stock_qty=10)
    assert (result["parent_allocation"]["order_qty"], result["parent_allocation"]["stock_qty"]) == (40, 30)
    assert (result["child_allocation"]["order_qty"], result["child_allocation"]["stock_qty"]) == (20, 10)
    cross = await split(service_db, result, labels[1], qty=20, order_qty=10, stock_qty=10, who=104,
        target_order_product_id=804, target_state_id=1005, target_state_version=1, key="split-cross-owner")
    assert cross["parent"]["order_id"] == 401 and cross["child"]["order_id"] == 403
    assert cross["parent"]["current_qty"] == 50 and cross["child"]["current_qty"] == 20
    assert (cross["child_allocation"]["order_qty"], cross["child_allocation"]["stock_qty"]) == (20, 0)
    assert cross["relation"]["source_snapshot"]["current_qty"] == 70
    assert await service_db.scalar(select(func.sum(m.ProductOutputAllocation.available_qty))) == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["zero", "negative", "over", "bool", "fraction", "string", "usage_sum", "usage_over",
    "stale_box", "stale_allocation", "bound_child", "outside_pool", "self_label", "worker", "closed_box"])
async def test_invalid_partition_is_atomic(service_db, failure):
    current, labels, _ = await prepared(service_db)
    kwargs, child = {}, labels[0]
    values = {"zero": 0, "negative": -1, "over": 101, "bool": True, "fraction": 1.5, "string": "30"}
    if failure in values:
        kwargs["qty"] = values[failure]
    elif failure == "usage_sum": kwargs.update(order_qty=20)
    elif failure == "usage_over": kwargs.update(order_qty=0, stock_qty=30)
    elif failure == "stale_box": kwargs["expected_version"] = 1
    elif failure == "stale_allocation": kwargs["allocation_version"] = 99
    elif failure == "bound_child":
        await boxes.bind_box(service_db, actor(103), qr_payload=child["qr_payload"], order_product_id=801, idempotency_key="already-bound-child")
    elif failure == "outside_pool": child = {"qr_payload": "PFB:v1:999999:PFB-20261027-999999"}
    elif failure == "self_label": child = current["box"]
    elif failure == "worker": kwargs["who"] = 101
    elif failure == "closed_box":
        await service_db.execute(update(m.ProductBox).where(m.ProductBox.id == int(current["box"]["id"])).values(lifecycle_status="closed"))
    before = await service_db.scalar(select(func.count()).select_from(m.ProductBox))
    with pytest.raises(QrError):
        await split(service_db, current, child, **kwargs)
    assert await service_db.scalar(select(m.ProductBox.current_qty).where(m.ProductBox.id == int(current["box"]["id"]))) == 100
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBox)) == before
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBoxRelation)) == 0
    assert await service_db.scalar(select(func.sum(m.ProductOutputAllocation.available_qty))) == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["warehouse", "other_owner", "hidden_target", "short_demand", "wrong_product", "stale_target", "completed_target"])
async def test_cross_order_scope_compatibility_and_demand_are_enforced(service_db, failure):
    current, labels, _ = await prepared(service_db)
    kwargs = dict(who=102, target_order_product_id=804, target_state_id=1005, target_state_version=1)
    if failure == "warehouse": kwargs["who"] = 103
    elif failure == "other_owner": kwargs["who"] = 105
    elif failure == "hidden_target":
        kwargs["who"] = 104
        await service_db.execute(update(m.ProductOrderContext).where(m.ProductOrderContext.order_id == 403).values(business_owner_id=105))
    elif failure == "short_demand":
        await service_db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id == 804).values(target_qty=20))
    elif failure == "wrong_product": kwargs.update(target_order_product_id=803, target_state_id=1002)
    elif failure == "stale_target": kwargs["target_state_version"] = 99
    elif failure == "completed_target":
        await service_db.execute(update(m.MachineOrderProcessState).where(m.MachineOrderProcessState.id == 1005).values(
            production_status="completed", completed_by=101, completed_at=func.clock_timestamp()))
    with pytest.raises(QrError):
        await split(service_db, current, labels[0], **kwargs)
    assert await service_db.scalar(select(m.ProductBox.current_qty).where(m.ProductBox.id == int(current["box"]["id"]))) == 100
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBoxRelation)) == 0


@pytest.mark.asyncio
async def test_remainder_and_child_advance_but_source_cannot_be_reinflated(service_db):
    current, labels, target = await prepared(service_db)
    result = await split(service_db, current, labels[0])
    for box in (result["parent"], result["child"]):
        with pytest.raises(QrError):
            await save(service_db, box, current, 100, key=f"split-forbid-qty-{box['id']}")
    for index, box in enumerate((result["parent"], result["child"])):
        destination = await selected(service_db, machine=602, assignment=503, process="FINISH", key=f"split-next-select-{index}")
        entered = await advance(service_db, {"box": box}, destination, key=f"split-next-advance-{index}")
        assert entered["quantity"]["input_qty"] == box["current_qty"]
        with pytest.raises(QrError):
            await split(service_db, entered, labels[index + 1], qty=1, key=f"no-split-downstream-{index}")
    assert await service_db.scalar(select(func.sum(m.ProductOutputAllocation.available_qty))) == 100


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_child_binding_quantity_and_allocation(service_db, monkeypatch):
    current, labels, _ = await prepared(service_db)
    async def fail(*args, **kwargs): raise RuntimeError("Synthetic split audit failure")
    monkeypatch.setattr(service, "write_audit", fail)
    with pytest.raises(RuntimeError): await split(service_db, current, labels[0])
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBox)) == 1
    assert await service_db.scalar(select(m.ProductQrPoolItem.pool_status).where(m.ProductQrPoolItem.id == int(labels[0]["id"]))) == "unused"
    assert await service_db.scalar(select(func.sum(m.ProductOutputAllocation.available_qty))) == 100


@pytest.mark.asyncio
async def test_completed_source_partition_invalidates_completion_and_direct_correction(service_db):
    current, labels, _ = await prepared(service_db)
    completed = await complete(service_db, current["context"])
    result = await split(service_db, current, labels[0])
    assert result["parent"]["current_qty"] == 70
    with pytest.raises(QrError):
        await production.correct_quantity(service_db, actor(102), box_id=int(result["parent"]["id"]), state_id=1001,
            current_qty=100, reason="Cannot rewrite partition", expected_version=result["parent"]["version"],
            state_version=completed["state"]["version"]+1, idempotency_key="split-historical-recount")


@pytest.mark.asyncio
async def test_concurrent_partitions_only_one_can_spend_parent_balance(qr_database_factory):
    with qr_database_factory() as engine:
        with engine.begin() as connection:
            create_service_fixture(connection); seed_service_fixture(connection)
        async_engine = create_async_engine(engine.url.set(drivername="postgresql+asyncpg"), echo=False, poolclass=NullPool)
        sessions = async_sessionmaker(async_engine, expire_on_commit=False)
        try:
            async with sessions() as db:
                current, labels, _ = await prepared(db)
                db.add(m.QrCapabilityGrant(user_id=102, capability="qr.split", granted_by=107))
                await db.commit()
            async def execute(index, who):
                async with sessions() as db:
                    try:
                        result = await split(db, current, labels[index], qty=70, who=who, key=f"split-concurrent-{index}")
                        await db.commit(); return result
                    except QrError as error:
                        await db.rollback(); return error
            results = await asyncio.gather(execute(0, 103), execute(1, 102))
            assert sum(isinstance(row, dict) for row in results) == 1
            async with sessions() as db:
                assert await db.scalar(select(func.sum(m.ProductBox.current_qty))) == 100
                assert await db.scalar(select(func.count()).select_from(m.ProductBoxRelation)) == 1
                assert await db.scalar(select(func.sum(m.ProductOutputAllocation.available_qty))) == 100
        finally:
            await async_engine.dispose()


@pytest.mark.asyncio
async def test_open_completion_intent_is_cleared_by_partition(service_db):
    from .test_production import machine_qr
    current, labels, _ = await prepared(service_db)
    context_id = int(current["context"]["id"])
    await production.scan_machine(service_db, actor(), machine_qr=machine_qr(), context_id=context_id)
    await split(service_db, current, labels[0])
    assert (await service_db.get(m.MachineProductionContext, context_id, populate_existing=True)).completion_scan_at is None
    state = await service_db.get(m.MachineOrderProcessState, 1001)
    with pytest.raises(QrError):
        await production.complete_production(service_db, actor(), machine_id=601, context_id=context_id,
            confirm_quantity_difference=False, expected_version=state.version, idempotency_key="split-stale-completion-intent")


@pytest.mark.asyncio
async def test_downstream_recount_after_partition_changes_only_current_process(service_db):
    from .test_production import machine_qr
    current, labels, _ = await prepared(service_db)
    partition = await split(service_db, current, labels[0])
    target = await selected(service_db, machine=602, assignment=503, process="FINISH", key="partition-finish-context")
    entered = await advance(service_db, {"box": partition["parent"]}, target)
    context_id = int(target["context"]["id"])
    scan = await production.scan_machine(service_db, actor(), machine_qr=machine_qr(602), context_id=context_id)
    completed = await production.complete_production(service_db, actor(), machine_id=602, context_id=context_id,
        confirm_quantity_difference=True, expected_version=scan["state"]["version"], idempotency_key="partition-finish-complete")
    corrected = await production.correct_quantity(service_db, actor(102), box_id=int(entered["box"]["id"]), state_id=1003,
        current_qty=65, reason="Current process recount", expected_version=entered["box"]["version"],
        state_version=completed["state"]["version"], idempotency_key="partition-later-recount")
    assert corrected["box"]["current_qty"] == 65
    assert corrected["allocation"]["available_qty"] == 70
    assert await service_db.scalar(select(m.ProductBox.current_qty).where(m.ProductBox.id == int(partition["child"]["id"]))) == 30


@pytest.mark.asyncio
async def test_concurrent_transfers_to_different_states_share_target_demand_lock(qr_database_factory):
    with qr_database_factory() as engine:
        with engine.begin() as connection:
            create_service_fixture(connection); seed_service_fixture(connection)
        async_engine = create_async_engine(engine.url.set(drivername="postgresql+asyncpg"), echo=False, poolclass=NullPool)
        sessions = async_sessionmaker(async_engine, expire_on_commit=False)
        try:
            async with sessions() as db:
                first, labels, _ = await prepared(db, qty=50)
                second_box = (await boxes.bind_box(db, actor(103), qr_payload=labels[0]["qr_payload"], order_product_id=801,
                    idempotency_key="split-second-source-bind"))["box"]
                context = await selected(db, key="split-second-source-select")
                second = await save(db, second_box, context, 50, key="split-second-source-qty")
                await db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id == 804).values(target_qty=40))
                await db.execute(update(m.MachineOrderProcessState).where(m.MachineOrderProcessState.order_product_id == 804).values(target_qty=40))
                await db.execute(update(m.MachineOrderProcessState).where(m.MachineOrderProcessState.id == 1005).values(target_qty=20))
                db.add(m.MachineOrderProcessState(id=1008, assignment_id=505, order_product_id=804,
                    route_revision_id=704, process_code="CUT", target_qty=20))
                await db.commit()
            async def transfer(index, who, state):
                async with sessions() as db:
                    try:
                        result = await split(db, (first, second)[index], labels[index+1], qty=30, who=who,
                            target_order_product_id=804, target_state_id=state, target_state_version=1, key=f"concurrent-transfer-{index}")
                        await db.commit(); return result
                    except QrError as error:
                        await db.rollback(); return error
            results = await asyncio.gather(transfer(0, 102, 1005), transfer(1, 104, 1008))
            assert sum(isinstance(row, dict) for row in results) == 1
            assert next(row for row in results if isinstance(row, QrError)).message == "目标订单剩余需求不足，整笔拆分未保存"
            async with sessions() as db:
                assert await db.scalar(select(func.sum(m.ProductOutputAllocation.order_qty)).where(m.ProductOutputAllocation.order_product_id == 804)) == 30
                assert await db.scalar(select(func.sum(m.ProductBox.current_qty))) == 100
        finally:
            await async_engine.dispose()
