"""Order selection and metadata API acceptance in owned PostgreSQL databases."""
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, update

from app.models import product_box as m
from app.models.audit import AuditLog
from app.models.production import ProductionPlan
from app.services import product_box_service as service
from app.services.qr_transaction_service import QrError
from .test_pool_api import headers, qr_api
from .service_fixtures import ACTORS


def actor(identity):
    dept, level, _ = ACTORS[identity]
    return SimpleNamespace(id=identity, dept=dept, role_level=level)


async def bound_box(db, *, extended_route=False):
    if extended_route:
        db.add(m.ProductRouteRevision(id=704, route_code="METADATA-ROUTE", revision=1,
            product_code="B", steps_json=[{"code": code, "name": code, "machine_ids": [601]}
                for code in ("CUT", "PRESS", "FINISH")], first_output_process_code="CUT",
            is_published=True, created_by=102))
        await db.flush()
        await db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id == 801)
                         .values(route_revision_id=704))
        await db.execute(update(m.MachineOrderProcessState).where(m.MachineOrderProcessState.id == 1001)
                         .values(route_revision_id=704))
    item = (await service.generate_batch(db, actor(102), count=1,
        idempotency_key="workspace-label-source"))["items"][0]
    return (await service.bind_box(db, actor(103), qr_payload=item["qr_payload"],
        order_product_id=801, idempotency_key="workspace-box-source"))["box"]


@pytest.mark.asyncio
async def test_pool_actor_and_capabilities_are_live_and_safe(qr_api, service_db, monkeypatch):
    monkeypatch.setattr(service.settings, "PRODUCT_QR_BATCH_LIMIT", 123)
    result = await qr_api.get("/api/v1/product-qr-pool", headers=headers(103))
    assert result.status_code == 200
    body = result.json()
    assert body["actor"] == {"id": 103, "dept": "warehouse", "role_level": 1}
    assert set(body["capabilities"]) == ACTORS[103][2]
    assert body["batch_limit"] == 123
    await service_db.execute(update(m.QrCapabilityGrant).where(
        m.QrCapabilityGrant.user_id == 103, m.QrCapabilityGrant.capability == "qr.metadata")
        .values(revoked_at=func.clock_timestamp(), revoked_by=107))
    await service_db.commit()
    refreshed = await qr_api.get("/api/v1/product-qr-pool", headers=headers(103))
    assert refreshed.status_code == 200 and "qr.metadata" not in refreshed.json()["capabilities"]
    assert set(body) == {"items", "total", "page", "page_size", "actor", "capabilities", "batch_limit"}


@pytest.mark.asyncio
async def test_qr_context_exposes_persisted_products_and_order_scope_without_writes(qr_api, service_db):
    before = await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent))
    result = await qr_api.get("/api/v1/production/plans/401/qr-context", headers=headers(103))
    assert result.status_code == 200
    body = result.json()
    assert body["version"] == 1 and body["business_owner_id"] == 104
    assert body["missing_configuration"] == []
    main, conversion = body["products"]
    assert main["id"] == "801" and main["part_name"] == "Synthetic part 301"
    assert main["can_bind"] and main["binding_allowed"]
    assert main["route"]["id"] == "701" and main["route"]["steps"][0]["code"] == "CUT"
    assert main["machine_process_targets"][0]["state_id"] == "1001"
    assert main["machine_process_targets"][0]["machine_id"] == 601
    assert conversion["id"] == "802" and conversion["conversion_source_id"] == "801"
    assert not conversion["can_bind"] and not conversion["binding_allowed"]
    assert (await qr_api.get("/api/v1/production/plans/401/qr-context", headers=headers(104))).status_code == 200
    denied = await qr_api.get("/api/v1/production/plans/401/qr-context", headers=headers(105))
    assert denied.status_code == 403 and denied.json()["code"] == "FORBIDDEN"
    assert (await qr_api.get("/api/v1/production/plans/999999/qr-context", headers=headers(103))).status_code == 404
    assert await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent)) == before
    assert await service_db.scalar(select(func.count()).select_from(m.QrIdempotencyRecord)) == 0
    assert await service_db.scalar(select(func.count()).select_from(AuditLog)) == 0


@pytest.mark.asyncio
async def test_legacy_unconfigured_plan_returns_missing_values_without_defaults(qr_api, service_db):
    service_db.add(ProductionPlan(id=403, part_id=None, total_qty=None, status="planned"))
    await service_db.commit()
    result = await qr_api.get("/api/v1/production/plans/403/qr-context", headers=headers(103))
    assert result.status_code == 200
    body = result.json()
    assert body["version"] == 0 and body["products"] == []
    assert body["business_owner_id"] is None and body["part_id"] is None and body["total_qty"] is None
    assert set(body["missing_configuration"]) == {"business_owner", "part", "products"}
    assert await service_db.scalar(select(func.count()).select_from(m.ProductOrderContext).where(
        m.ProductOrderContext.order_id == 403)) == 0


@pytest.mark.asyncio
async def test_context_missing_targets_and_owner_disable_binding(qr_api, service_db):
    await service_db.execute(update(m.ProductOrderContext).where(m.ProductOrderContext.order_id == 401)
        .values(business_owner_id=None))
    await service_db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id == 801)
        .values(target_qty=0))
    await service_db.execute(update(m.MachineOrderProcessState).where(m.MachineOrderProcessState.id == 1001)
        .values(process_code="UNCONFIGURED"))
    await service_db.commit()
    result = await qr_api.get("/api/v1/production/plans/401/qr-context", headers=headers(103))
    assert result.status_code == 200
    main = result.json()["products"][0]
    assert set(main["missing_configuration"]) == {"business_owner", "target_qty", "machine_process_targets"}
    assert not main["can_bind"]


@pytest.mark.asyncio
async def test_metadata_changes_snapshots_only_and_keeps_immutable_audit(qr_api, service_db):
    original = await bound_box(service_db, extended_route=True)
    await service_db.commit()
    request = {"customer_name_snapshot": "Updated customer label", "customer_part_no": "PART-LABEL-2",
        "next_process_code": "PRESS", "expected_version": 1, "idempotency_key": "metadata-owner-request"}
    response = await qr_api.patch(f'/api/v1/product-boxes/{original["id"]}/metadata',
        headers=headers(104), json=request)
    assert response.status_code == 200
    changed = response.json()
    assert changed["version"] == 2 and changed["next_process_code"] == "PRESS"
    assert changed["customer_name_snapshot"] == request["customer_name_snapshot"]
    assert changed["customer_part_no"] == request["customer_part_no"]
    for field in ("id", "qr_pool_item_id", "qr_payload", "box_no", "order_id", "order_product_id", "part_id",
                  "product_code", "route_revision_id", "customer_id", "current_process_code", "current_qty", "bound_by"):
        assert changed[field] == original[field]
    event = await service_db.scalar(select(m.ProductFlowEvent).where(m.ProductFlowEvent.event_type == "metadata_edit"))
    assert event.operator_id == 104 and event.before_qty == event.after_qty == 0 and event.box_version == 2
    assert event.before_snapshot["customer_part_no"] == original["customer_part_no"]
    assert event.after_snapshot["customer_part_no"] == request["customer_part_no"]
    audits = (await service_db.scalars(select(AuditLog).where(
        AuditLog.changes_summary == f'box:{original["id"]}:metadata'))).all()
    assert len(audits) == 1 and audits[0].user_id == 104
    replay = await qr_api.patch(f'/api/v1/product-boxes/{original["id"]}/metadata', headers=headers(104), json=request)
    assert replay.status_code == 200 and replay.json() == changed
    assert await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent).where(
        m.ProductFlowEvent.event_type == "metadata_edit")) == 1
    conflict = await qr_api.patch(f'/api/v1/product-boxes/{original["id"]}/metadata', headers=headers(104),
        json=request | {"customer_part_no": "DIFFERENT"})
    assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    stale = await qr_api.patch(f'/api/v1/product-boxes/{original["id"]}/metadata', headers=headers(104),
        json=request | {"idempotency_key": "metadata-stale-request"})
    assert stale.status_code == 409 and stale.json()["code"] == "STALE_BOX_VERSION"
    assert stale.json()["details"]["current_version"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", [101, 105, 107, 108])
async def test_metadata_department_capability_and_owner_rejections_leave_box_unchanged(qr_api, service_db, identity):
    original = await bound_box(service_db)
    await service_db.commit()
    result = await qr_api.patch(f'/api/v1/product-boxes/{original["id"]}/metadata', headers=headers(identity),
        json={"customer_part_no": "FORBIDDEN", "expected_version": 1, "idempotency_key": "metadata-denied-request"})
    assert result.status_code == 403 and result.json()["code"] == "FORBIDDEN"
    box = await service_db.get(m.ProductBox, int(original["id"]), populate_existing=True)
    assert box.version == 1 and box.customer_part_no == original["customer_part_no"]
    assert await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent).where(
        m.ProductFlowEvent.event_type == "metadata_edit")) == 0


@pytest.mark.asyncio
async def test_metadata_replay_requires_current_capability_and_lifecycle(qr_api, service_db):
    original = await bound_box(service_db)
    await service_db.commit()
    request = {"customer_part_no": None, "next_process_code": None,
               "expected_version": 1, "idempotency_key": "metadata-revocation-request"}
    path = f'/api/v1/product-boxes/{original["id"]}/metadata'
    saved = await qr_api.patch(path, headers=headers(103), json=request)
    assert saved.status_code == 200 and saved.json()["next_process_code"] is None
    await service_db.execute(update(m.QrCapabilityGrant).where(
        m.QrCapabilityGrant.user_id == 103, m.QrCapabilityGrant.capability == "qr.metadata")
        .values(revoked_at=func.clock_timestamp(), revoked_by=107))
    await service_db.commit()
    assert (await qr_api.patch(path, headers=headers(103), json=request)).status_code == 403
    await service_db.execute(update(m.ProductBox).where(m.ProductBox.id == int(original["id"]))
        .values(lifecycle_status="closed"))
    await service_db.commit()
    denied = await qr_api.patch(path, headers=headers(104), json=request | {"expected_version": 2})
    assert denied.status_code == 409 and denied.json()["code"] == "STATE_CONFLICT"


@pytest.mark.asyncio
async def test_metadata_next_step_is_limited_to_bound_route_and_never_advances(qr_api, service_db):
    original = await bound_box(service_db, extended_route=True)
    await service_db.execute(update(m.ProductBox).where(m.ProductBox.id == int(original["id"]))
        .values(current_process_code="PRESS", next_process_code="FINISH"))
    await service_db.commit()
    path = f'/api/v1/product-boxes/{original["id"]}/metadata'
    for index, code in enumerate(("CUT", "PRESS", "NOT-IN-ROUTE")):
        rejected = await qr_api.patch(path, headers=headers(103), json={"next_process_code": code,
            "expected_version": 1, "idempotency_key": f"metadata-invalid-step-{index}"})
        assert rejected.status_code == 400 and rejected.json()["code"] == "STATE_CONFLICT"
    valid = await qr_api.patch(path, headers=headers(103), json={"next_process_code": "FINISH",
        "expected_version": 1, "idempotency_key": "metadata-valid-next-step"})
    assert valid.status_code == 200 and valid.json()["current_process_code"] == "PRESS"
    assert valid.json()["current_qty"] == 0 and valid.json()["route_revision_id"] == "704"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [
    {}, {"order_id": 402}, {"qr_payload": "PFB:v1:999:PFB-20261023-000999"},
    {"part_id": 302}, {"product_code": "C"}, {"current_qty": 100},
    {"customer_part_no": "X" * 151}, {"next_process_code": ""}, {"customer_part_no": 5},
])
async def test_metadata_schema_rejects_identity_fields_and_empty_or_invalid_patch(qr_api, service_db, invalid):
    original = await bound_box(service_db)
    await service_db.commit()
    result = await qr_api.patch(f'/api/v1/product-boxes/{original["id"]}/metadata', headers=headers(103),
        json={"expected_version": 1, "idempotency_key": "metadata-invalid-schema"} | invalid)
    assert result.status_code == 422


@pytest.mark.asyncio
async def test_metadata_rolls_back_box_event_and_request_when_audit_fails(service_db, monkeypatch):
    original = await bound_box(service_db)
    async def fail_audit(*args, **kwargs):
        await service_db.flush()
        raise QrError(409, "STATE_CONFLICT", "Synthetic audit failure")
    monkeypatch.setattr(service, "write_audit", fail_audit)
    with pytest.raises(QrError):
        await service.edit_metadata(service_db, actor(103), box_id=int(original["id"]),
            changes={"customer_part_no": "MUST-ROLL-BACK"}, expected_version=1,
            idempotency_key="metadata-rollback-request")
    box = await service_db.get(m.ProductBox, int(original["id"]), populate_existing=True)
    assert box.version == 1 and box.customer_part_no == original["customer_part_no"]
    assert await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent).where(
        m.ProductFlowEvent.event_type == "metadata_edit")) == 0
    assert await service_db.scalar(select(func.count()).select_from(m.QrIdempotencyRecord).where(
        m.QrIdempotencyRecord.action == "metadata")) == 0


@pytest.mark.asyncio
async def test_internal_metadata_call_cannot_edit_identity(service_db):
    original = await bound_box(service_db)
    with pytest.raises(QrError):
        await service.edit_metadata(service_db, actor(103), box_id=int(original["id"]),
            changes={"order_id": 402}, expected_version=1, idempotency_key="metadata-internal-forbidden")
    assert (await service_db.get(m.ProductBox, int(original["id"]))).order_id == 401
