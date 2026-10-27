"""Order QR configuration acceptance using protected synthetic PostgreSQL only."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import product_box as m
from app.models.audit import AuditLog
from app.models.part import Part
from app.models.production import PlanMachineAssignment, ProductionPlan
from app.models.user import User
from app.services import product_box_service as boxes
from app.services import product_order_service as service
from app.services.qr_transaction_service import QrError
from .service_fixtures import ACTORS, create_service_fixture, seed_service_fixture


def actor(identity=102):
    dept, level, _ = ACTORS[identity]
    return SimpleNamespace(id=identity, dept=dept, role_level=level)


def configuration():
    return {
        "business_owner_id": 104,
        "products": [{"key": "main", "part_id": 301, "product_code": "B", "target_qty": 100,
            "binding_allowed": True, "route": {"route_code": "CFG-B", "revision": 1,
                "steps": [{"code": code, "name": code, "machine_ids": [601]} for code in ("CUT", "PACK")],
                "first_output_process_code": "CUT"}}],
        "machine_process_targets": [{"product_key": "main", "assignment_id": 503,
            "process_code": code, "target_qty": 100} for code in ("CUT", "PACK")],
        "expected_version": 0, "idempotency_key": "configure-test-0001",
    }


async def new_order(db, *, paired=False):
    db.add(ProductionPlan(id=403, part_id=301, total_qty=777, status="planned",
        is_left_right_pair=paired, paired_part_id=302 if paired else None))
    await db.flush()
    db.add(PlanMachineAssignment(id=503, plan_id=403, machine_id=601, assigned_qty=100))
    await db.flush()


async def save(db, data=None, who=102):
    return await service.save_order_qr_context(db, actor(who), order_id=403, **(data or configuration()))


def update_request(data, result, *, version=1, key="configure-test-0002"):
    updated = deepcopy(data)
    for product, stored in zip(updated["products"], result["products"]):
        product["id"] = stored["id"]
    updated.update(expected_version=version, idempotency_key=key)
    return updated


@pytest.mark.asyncio
async def test_create_configuration_publishes_complete_routes_without_changing_legacy_plan(service_db):
    await new_order(service_db)
    result = await save(service_db)
    assert result["version"] == 1 and result["business_owner_id"] == 104
    assert result["missing_configuration"] == [] and result["products"][0]["can_bind"]
    assert result["products"][0]["target_qty"] == 100
    assert result["products"][0]["route"]["is_published"]
    assert len(result["products"][0]["machine_process_targets"]) == 2
    plan = await service_db.get(ProductionPlan, 403, populate_existing=True)
    assert plan.total_qty == 777 and plan.status == "planned"
    assert (await service_db.get(PlanMachineAssignment, 503)).assigned_qty == 100
    assert await service_db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.changes_summary == "order-configuration:403")) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("who,allowed", [(102, True), (106, True), (107, True),
    (101, False), (103, False), (104, False), (109, False), (110, False)])
async def test_configuration_requires_department_level_and_explicit_capability(service_db, who, allowed):
    await new_order(service_db)
    if allowed:
        assert (await save(service_db, who=who))["version"] == 1
    else:
        with pytest.raises(QrError) as caught:
            await save(service_db, who=who)
        assert caught.value.code == "FORBIDDEN"
        assert await service_db.scalar(select(m.ProductOrderContext.id).where(m.ProductOrderContext.order_id == 403)) is None


@pytest.mark.asyncio
async def test_configuration_replay_conflict_stale_and_revocation_are_distinct(service_db):
    await new_order(service_db)
    data = configuration()
    first = await save(service_db, data)
    assert await save(service_db, data) == first
    changed = deepcopy(data)
    changed["business_owner_id"] = 105
    with pytest.raises(QrError) as conflict:
        await save(service_db, changed)
    assert conflict.value.code == "IDEMPOTENCY_CONFLICT"
    stale = update_request(data, first, version=0)
    with pytest.raises(QrError) as conflict:
        await save(service_db, stale)
    assert conflict.value.code == "STATE_CONFLICT"
    await service_db.execute(m.QrCapabilityGrant.__table__.update().where(
        m.QrCapabilityGrant.user_id == 102, m.QrCapabilityGrant.capability == "qr.configure").values(
            revoked_at=text("CURRENT_TIMESTAMP"), revoked_by=107))
    with pytest.raises(QrError) as denied:
        await save(service_db, data)
    assert denied.value.code == "FORBIDDEN"


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", [101, 103, 106, 999999])
async def test_owner_must_be_an_existing_sales_lv2_or_higher(service_db, owner):
    await new_order(service_db)
    data = configuration()
    data["business_owner_id"] = owner
    with pytest.raises(QrError):
        await save(service_db, data)
    assert await service_db.scalar(select(m.ProductOrderContext.id).where(m.ProductOrderContext.order_id == 403)) is None
    assert await service_db.scalar(select(m.ProductRouteRevision.id).where(m.ProductRouteRevision.route_code == "CFG-B")) is None


@pytest.mark.asyncio
async def test_paired_order_requires_each_actual_part_and_explicit_independent_targets(service_db):
    await new_order(service_db, paired=True)
    data = configuration()
    with pytest.raises(QrError):
        await save(service_db, data)
    data["products"][0]["target_qty"] = 80
    for target in data["machine_process_targets"]:
        target["target_qty"] = 80
    right = deepcopy(data["products"][0])
    right.update(key="right", part_id=302, target_qty=70)
    right["route"]["route_code"] = "CFG-RIGHT"
    data["products"].append(right)
    data["machine_process_targets"] += [{"product_key": "right", "assignment_id": 503,
        "process_code": step, "target_qty": 70} for step in ("CUT", "PACK")]
    result = await save(service_db, data)
    assert sorted(product["target_qty"] for product in result["products"]) == [70, 80]
    assert (await service_db.get(ProductionPlan, 403)).total_qty == 777


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["wrong_part", "product_a", "zero_direct", "fraction", "bool",
    "missing_step", "duplicate_step", "wrong_first", "unrestricted_step", "wrong_machine",
    "wrong_assignment", "inactive_assignment", "missing_target", "wrong_share", "excess_share",
    "duplicate_target", "unknown_target_product", "noncanonical_id", "fake_author", "deleted_part"])
async def test_invalid_configuration_is_atomic_without_partial_route_or_context(service_db, case):
    await new_order(service_db)
    data = configuration()
    product, route = data["products"][0], data["products"][0]["route"]
    if case == "wrong_part": product["part_id"] = 302
    elif case == "product_a": product["product_code"] = "A"
    elif case == "zero_direct": product["target_qty"] = 0
    elif case == "fraction": product["target_qty"] = 1.5
    elif case == "bool": product["target_qty"] = True
    elif case == "missing_step": route["steps"] = []
    elif case == "duplicate_step": route["steps"].append(deepcopy(route["steps"][0]))
    elif case == "wrong_first": route["first_output_process_code"] = "MISSING"
    elif case == "unrestricted_step": route["steps"][0].pop("machine_ids")
    elif case == "wrong_machine": route["steps"][0]["machine_ids"] = [602]
    elif case == "wrong_assignment": data["machine_process_targets"][0]["assignment_id"] = 502
    elif case == "inactive_assignment": (await service_db.get(PlanMachineAssignment, 503)).is_active = False
    elif case == "missing_target": data["machine_process_targets"].pop()
    elif case == "wrong_share": data["machine_process_targets"][0]["target_qty"] = 99
    elif case == "excess_share": data["machine_process_targets"][0]["target_qty"] = 101
    elif case == "duplicate_target": data["machine_process_targets"].append(deepcopy(data["machine_process_targets"][0]))
    elif case == "unknown_target_product": data["machine_process_targets"][0]["product_key"] = "unknown"
    elif case == "noncanonical_id": product["id"] = "01"
    elif case == "fake_author": product["pre_authorized_conversions"] = [{"target_key": "main", "difference_process_codes": ["PACK"], "authorized_by": 107}]
    elif case == "deleted_part": (await service_db.get(Part, 301)).is_deleted = True
    await service_db.flush()
    before_routes = await service_db.scalar(select(func.count()).select_from(m.ProductRouteRevision))
    with pytest.raises(QrError):
        await save(service_db, data)
    assert await service_db.scalar(select(func.count()).select_from(m.ProductRouteRevision)) == before_routes
    assert await service_db.scalar(select(m.ProductOrderContext.id).where(m.ProductOrderContext.order_id == 403)) is None
    assert await service_db.scalar(select(m.QrIdempotencyRecord.id).where(m.QrIdempotencyRecord.action == "order-configuration")) is None


@pytest.mark.asyncio
async def test_machine_type_constraints_match_machine_type_field(service_db):
    from app.models.machine import Machine
    await new_order(service_db)
    (await service_db.get(Machine, 601)).machine_type = "stamping"
    data = configuration()
    for step in data["products"][0]["route"]["steps"]:
        step.pop("machine_ids")
        step["machine_types"] = ["stamping"]
    assert (await save(service_db, data))["products"][0]["can_bind"]


@pytest.mark.asyncio
async def test_published_route_identity_cannot_be_overwritten(service_db):
    await new_order(service_db)
    data = configuration()
    created = await save(service_db, data)
    updated = update_request(data, created)
    updated["products"][0]["route"]["steps"][0]["name"] = "Changed published content"
    with pytest.raises(QrError) as caught:
        await save(service_db, updated)
    assert caught.value.code == "STATE_CONFLICT"
    assert (await service_db.get(m.ProductOrderContext, int(await service_db.scalar(select(m.ProductOrderContext.id).where(m.ProductOrderContext.order_id == 403))))).version == 1


async def bind_created_product(db, result):
    item = (await boxes.generate_batch(db, actor(102), count=1, idempotency_key="config-bind-pool-001"))["items"][0]
    return (await boxes.bind_box(db, actor(103), qr_payload=item["qr_payload"],
        order_product_id=int(result["products"][0]["id"]), idempotency_key="config-bind-box-0001"))["box"]


@pytest.mark.asyncio
async def test_revision_change_applies_to_new_boxes_and_preserves_old_route_states_and_identity(service_db):
    await new_order(service_db)
    data = configuration()
    created = await save(service_db, data)
    box = await bind_created_product(service_db, created)
    old_route = int(box["route_revision_id"])
    old_states = set((await service_db.scalars(select(m.MachineOrderProcessState.id).where(
        m.MachineOrderProcessState.order_product_id == int(created["products"][0]["id"])))) .all())
    updated = update_request(data, created)
    updated["products"][0]["route"]["revision"] = 2
    updated["products"][0]["route"]["steps"].append({"code": "FINISH", "machine_ids": [601]})
    updated["machine_process_targets"].append({"product_key": "main", "assignment_id": 503, "process_code": "FINISH", "target_qty": 100})
    result = await save(service_db, updated)
    assert result["version"] == 2 and int(result["products"][0]["route_revision_id"]) != old_route
    stored_box = await service_db.get(m.ProductBox, int(box["id"]), populate_existing=True)
    assert stored_box.route_revision_id == old_route and stored_box.order_id == 403 and stored_box.part_id == 301
    assert await service_db.scalar(select(func.count()).select_from(m.MachineOrderProcessState).where(m.MachineOrderProcessState.id.in_(old_states))) == 2
    assert (await service_db.get(m.ProductRouteRevision, old_route)).revision == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["omit", "identity"])
async def test_configuration_never_silently_removes_a_product_or_replaces_bound_identity(service_db, case):
    await new_order(service_db)
    data = configuration()
    created = await save(service_db, data)
    await bind_created_product(service_db, created)
    updated = update_request(data, created)
    if case == "omit": updated["products"] = []
    else: updated["products"][0]["part_id"] = 302
    with pytest.raises(QrError):
        await save(service_db, updated)
    assert (await service_db.get(m.ProductOrderProduct, int(created["products"][0]["id"]), populate_existing=True)).part_id == 301


@pytest.mark.asyncio
async def test_product_demand_cannot_shrink_below_effective_allocated_order_quantity(service_db):
    await new_order(service_db)
    data = configuration()
    created = await save(service_db, data)
    box = await bind_created_product(service_db, created)
    product_id = int(created["products"][0]["id"])
    state = await service_db.scalar(select(m.MachineOrderProcessState).where(
        m.MachineOrderProcessState.order_product_id == product_id, m.MachineOrderProcessState.process_code == "CUT"))
    quantity = m.BoxProcessQuantity(state_id=state.id, box_id=int(box["id"]), current_qty=60, updated_by=102)
    service_db.add(quantity)
    await service_db.flush()
    service_db.add(m.ProductOutputAllocation(source_quantity_id=quantity.id, box_id=int(box["id"]),
        order_id=403, order_product_id=product_id, available_qty=60, order_qty=60, stock_qty=0,
        remaining_order_qty_snapshot=100, assigned_by=102))
    await service_db.flush()
    updated = update_request(data, created)
    updated["products"][0]["target_qty"] = 50
    for target in updated["machine_process_targets"]: target["target_qty"] = 50
    with pytest.raises(QrError) as caught:
        await save(service_db, updated)
    assert caught.value.code == "STATE_CONFLICT"
    assert (await service_db.get(m.ProductOrderProduct, product_id, populate_existing=True)).target_qty == 100


@pytest.mark.asyncio
async def test_conversion_target_has_no_direct_demand_and_authorization_is_server_derived(service_db):
    await new_order(service_db)
    data = configuration()
    converted = deepcopy(data["products"][0])
    converted.update(key="convert", part_id=302, product_code="C", target_qty=0,
        binding_allowed=False, conversion_source_key="main")
    converted["route"].update(route_code="CFG-C")
    converted["route"]["steps"].append({"code": "FINISH", "machine_ids": [601]})
    data["products"].append(converted)
    data["products"][0]["pre_authorized_conversions"] = [{"target_key": "convert", "difference_process_codes": ["FINISH"]}]
    data["machine_process_targets"] += [{"product_key": "convert", "assignment_id": 503, "process_code": step, "target_qty": 0} for step in ("CUT", "PACK", "FINISH")]
    result = await save(service_db, data)
    main = next(product for product in result["products"] if product["binding_allowed"])
    target = next(product for product in result["products"] if not product["binding_allowed"])
    assert target["target_qty"] == 0 and not target["can_bind"] and target["conversion_source_id"] == main["id"]
    stored = await service_db.get(m.ProductOrderProduct, int(main["id"]))
    authorization = stored.conversion_authorization["targets"][0]
    assert authorization["target_order_product_id"] == target["id"]
    assert authorization["source_route_revision_id"] == main["route_revision_id"]
    assert authorization["target_route_revision_id"] == target["route_revision_id"]
    assert authorization["difference_process_codes"] == ["FINISH"]
    assert authorization["authorized_by"] == 102 and authorization["authorized_at"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["same_product", "wrong_difference", "not_source", "positive_target"])
async def test_invalid_preauthorization_rejects_all_configuration(service_db, case):
    await new_order(service_db)
    data = configuration()
    converted = deepcopy(data["products"][0])
    converted.update(key="convert", part_id=302, product_code="C", target_qty=0,
        binding_allowed=False, conversion_source_key="main")
    converted["route"]["route_code"] = "CFG-C"
    converted["route"]["steps"].append({"code": "FINISH", "machine_ids": [601]})
    data["products"].append(converted)
    data["products"][0]["pre_authorized_conversions"] = [{"target_key": "convert", "difference_process_codes": ["FINISH"]}]
    data["machine_process_targets"] += [{"product_key": "convert", "assignment_id": 503, "process_code": step, "target_qty": 0} for step in ("CUT", "PACK", "FINISH")]
    if case == "same_product": converted["product_code"] = "B"
    elif case == "wrong_difference": data["products"][0]["pre_authorized_conversions"][0]["difference_process_codes"] = ["CUT"]
    elif case == "not_source": converted["conversion_source_key"] = "missing"
    elif case == "positive_target": converted["target_qty"] = 10
    with pytest.raises(QrError):
        await save(service_db, data)
    assert await service_db.scalar(select(m.ProductOrderContext.id).where(m.ProductOrderContext.order_id == 403)) is None


@pytest.mark.asyncio
async def test_two_real_transactions_cannot_both_replace_version_zero(qr_database_factory):
    with qr_database_factory() as engine:
        with engine.begin() as connection:
            create_service_fixture(connection)
            seed_service_fixture(connection)
            connection.execute(ProductionPlan.__table__.insert().values(id=403, part_id=301, total_qty=777, status="planned"))
            connection.execute(PlanMachineAssignment.__table__.insert().values(id=503, plan_id=403, machine_id=601, assigned_qty=100))
        async_engine = create_async_engine(engine.url.set(drivername="postgresql+asyncpg"), poolclass=NullPool, echo=False)
        async def worker(who):
            async with AsyncSession(async_engine, expire_on_commit=False) as db:
                data = configuration()
                data["idempotency_key"] = f"concurrent-config-{who}"
                try:
                    result = await save(db, data, who)
                    await db.commit()
                    return result["version"]
                except QrError as error:
                    await db.rollback()
                    return error.code
        try:
            results = await asyncio.wait_for(asyncio.gather(worker(102), worker(106)), timeout=20)
            assert sorted(map(str, results)) == ["1", "STATE_CONFLICT"]
            async with AsyncSession(async_engine) as db:
                assert await db.scalar(select(func.count()).select_from(m.ProductOrderContext).where(m.ProductOrderContext.order_id == 403)) == 1
                assert await db.scalar(select(func.count()).select_from(m.ProductOrderProduct).where(m.ProductOrderProduct.order_id == 403)) == 1
        finally:
            await async_engine.dispose()
