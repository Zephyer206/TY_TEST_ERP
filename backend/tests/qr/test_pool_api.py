"""Exercise mounted HTTP routes with JWT identities and isolated PostgreSQL."""
import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import func, select

from app.api.product_boxes import router, qr_error_handler
from app.api.warehouse import router as warehouse_router
from app.core.config import settings
from app.core.security import create_access_token
from app.database import get_db
from app.main import validation_exception_handler
from app.models import product_box as m
from app.services.qr_transaction_service import QrError


def headers(identity):
    return {"Authorization": "Bearer " + create_access_token({"sub": str(identity)})}


@pytest_asyncio.fixture
async def qr_api(service_db, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DISABLED", False)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(warehouse_router, prefix="/api/v1")
    app.add_exception_handler(QrError, qr_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    async def isolated_db():
        try:
            yield service_db
            await service_db.commit()
        except Exception:
            await service_db.rollback()
            raise
    app.dependency_overrides[get_db] = isolated_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://qr-isolated.test") as client:
        yield client


@pytest.mark.asyncio
async def test_http_authentication_is_required_and_acceptance_bypass_is_rejected(qr_api, monkeypatch):
    assert (await qr_api.get("/api/v1/product-qr-pool")).status_code == 401
    assert (await qr_api.get("/api/v1/product-qr-pool", headers={"Authorization": "Bearer invalid"})).status_code == 401
    monkeypatch.setattr(settings, "AUTH_DISABLED", True)
    denied = await qr_api.get("/api/v1/product-qr-pool", headers=headers(107))
    assert denied.status_code == 503 and denied.json()["code"] == "STATE_CONFLICT"


@pytest.mark.asyncio
async def test_http_generate_bind_scan_and_idempotency(qr_api, service_db):
    body = {"count": 2, "idempotency_key": "http-generate-0001"}
    generated = await qr_api.post("/api/v1/product-qr-pool/batches", headers=headers(102), json=body)
    assert generated.status_code == 201
    assert (await qr_api.post("/api/v1/product-qr-pool/batches", headers=headers(102), json=body)).json() == generated.json()
    item = generated.json()["items"][0]
    assert isinstance(item["id"], str)
    request = {"qr_payload": item["qr_payload"], "order_product_id": "801", "idempotency_key": "http-binding-0001"}
    bound = await qr_api.post("/api/v1/product-boxes/bind", headers=headers(103), json=request)
    assert bound.status_code == 201 and bound.json()["box"]["bound_by"] == 103
    assert (await qr_api.post("/api/v1/product-boxes/bind", headers=headers(103), json=request)).json() == bound.json()
    scanned = await qr_api.post("/api/v1/product-boxes/scan", headers=headers(104), json={"qr_payload": item["qr_payload"]})
    assert scanned.status_code == 200 and "bind" not in scanned.json()["allowed_actions"]
    hidden = await qr_api.post("/api/v1/product-boxes/scan", headers=headers(105), json={"qr_payload": item["qr_payload"]})
    assert hidden.status_code == 403 and hidden.json()["code"] == "FORBIDDEN"
    own_list = await qr_api.get("/api/v1/product-qr-pool", headers=headers(104))
    other_list = await qr_api.get("/api/v1/product-qr-pool", headers=headers(105))
    assert own_list.json()["total"] == 1 and other_list.json()["total"] == 0
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBox)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [{"count": True}, {"count": 1.5}, {"count": "1"},
                                    {"count": 1, "operator_id": 107}])
async def test_http_strict_input_rejects_coercion_and_client_operator(qr_api, invalid):
    response = await qr_api.post("/api/v1/product-qr-pool/batches", headers=headers(102),
        json=invalid | {"idempotency_key": "http-invalid-input"})
    assert response.status_code == 422 and "errors" in response.json()


@pytest.mark.asyncio
async def test_http_batch_limit_and_role_rejection(qr_api):
    denied = await qr_api.post("/api/v1/product-qr-pool/batches", headers=headers(106),
        json={"count": 1, "idempotency_key": "wrong-dept-http-01"})
    assert denied.status_code == 403
    oversized = await qr_api.post("/api/v1/product-qr-pool/batches", headers=headers(102),
        json={"count": 501, "idempotency_key": "oversized-http-01"})
    assert oversized.status_code == 400 and oversized.json()["code"] == "INVALID_QUANTITY"


@pytest.mark.asyncio
async def test_http_print_data_is_not_print_confirmation(qr_api):
    generated = await qr_api.post("/api/v1/product-qr-pool/batches", headers=headers(102),
        json={"count": 1, "idempotency_key": "http-print-source"})
    item = generated.json()["items"][0]
    job = await qr_api.post("/api/v1/product-qr-pool/print-data", headers=headers(103),
        json={"item_ids": [item["id"]], "idempotency_key": "http-print-data-01"})
    assert job.status_code == 201 and job.json()["items"][0]["print_count"] == 0
    confirmed = await qr_api.post("/api/v1/product-qr-pool/print-confirmations", headers=headers(103),
        json={"print_job_id": job.json()["print_job_id"], "confirmed_item_ids": [item["id"]],
              "idempotency_key": "http-confirm-0001"})
    assert confirmed.status_code == 200 and confirmed.json()["items"][0]["print_count"] == 1
    reprint = await qr_api.post(f'/api/v1/product-qr-pool/{item["id"]}/reprint', headers=headers(103),
        json={"idempotency_key": "http-reprint-0001"})
    assert reprint.status_code == 201 and reprint.json()["items"][0]["qr_payload"] == item["qr_payload"]


@pytest.mark.asyncio
async def test_http_capability_admin_uses_version_and_no_user_can_supply_role(qr_api):
    request = {"capabilities": ["qr.production", "qr.trace", "qr.split"],
               "expected_version": 1, "idempotency_key": "http-capability-01"}
    assert (await qr_api.put("/api/v1/qr-admin/capabilities/101", headers=headers(102), json=request)).status_code == 403
    update = await qr_api.put("/api/v1/qr-admin/capabilities/101", headers=headers(107), json=request)
    assert update.status_code == 200 and update.json()["version"] == 2
    listed = await qr_api.get("/api/v1/qr-admin/capabilities?user_id=101", headers=headers(107))
    assert listed.status_code == 200 and listed.json()["items"][0]["capabilities"] == sorted(request["capabilities"])


@pytest.mark.asyncio
async def test_material_catalogue_eager_supplier_and_opt_in_historical_materials(qr_api, service_db):
    from app.models.warehouse import Supplier, Material
    supplier = Supplier(supplier_no="CATALOGUE-QA", name="Synthetic supplier")
    service_db.add(supplier)
    await service_db.flush()
    service_db.add_all([
        Material(material_no="CATALOGUE-ACTIVE", name="Active steel", grade="SPCC", supplier_id=supplier.id),
        Material(material_no="CATALOGUE-HISTORY", name="Retired steel", grade="SPCC", supplier_id=supplier.id, is_active=False),
    ])
    await service_db.commit()
    current = await qr_api.get("/api/v1/warehouse/materials", headers=headers(101))
    assert current.status_code == 200 and [item["name"] for item in current.json()] == ["Active steel"]
    history = await qr_api.get("/api/v1/warehouse/materials?include_inactive=true", headers=headers(101))
    assert history.status_code == 200 and len(history.json()) == 2
    assert all(item["supplier_name"] == "Synthetic supplier" for item in history.json())


@pytest.mark.asyncio
async def test_legacy_material_http_inbound_split_scan_and_old_date_reprint(qr_api, service_db):
    from app.models.warehouse import Material, MaterialBatch, MaterialBatchChild
    from app.services.qr_service import generate_qr_base64
    source = Material(material_no="HTTP-REGRESSION", name="Synthetic steel", grade="SPCC")
    service_db.add(source)
    await service_db.flush()
    source_id = source.id
    await service_db.commit()
    body = {"material_id": source_id, "gross_weight": 100}
    assert (await qr_api.post("/api/v1/warehouse/material-batches", headers=headers(101), json=body)).status_code == 403
    inbound = await qr_api.post("/api/v1/warehouse/material-batches", headers=headers(102), json=body)
    assert inbound.status_code == 201
    identity = inbound.json()["id"]
    denied_iqc = await qr_api.put(f"/api/v1/warehouse/material-batches/{identity}/iqc", headers=headers(101), json={"result": "passed"})
    assert denied_iqc.status_code == 403
    iqc = await qr_api.put(f"/api/v1/warehouse/material-batches/{identity}/iqc", headers=headers(102), json={"result": "passed"})
    assert iqc.status_code == 200
    children = await qr_api.post(f"/api/v1/warehouse/material-batches/{identity}/split", headers=headers(102),
        json={"splits": [{"weight": 30}, {"weight": 20}]})
    assert children.status_code == 200 and len(children.json()) == 2
    listed = await qr_api.get(f"/api/v1/warehouse/material-batches/{identity}/children", headers=headers(101))
    assert listed.status_code == 200 and {c["id"] for c in listed.json()} == {c["id"] for c in children.json()}
    assert all(c["parent_batch_id"] == identity and c["qr_image_base64"] for c in listed.json())
    # A legacy row can share an ID with its parent: it is a different sequence.
    service_db.add(MaterialBatchChild(id=identity, parent_batch_id=identity,
        child_batch_no="LEGACY-HTTP-CHILD", child_qr_code="MAT:900000:20010101", current_weight=5))
    await service_db.commit()
    listed = await qr_api.get(f"/api/v1/warehouse/material-batches/{identity}/children", headers=headers(101))
    assert listed.status_code == 200 and len(listed.json()) == 3
    assert next(c for c in listed.json() if c["batch_no"] == "LEGACY-HTTP-CHILD")["qr_code"] == "MAT:900000:20010101"
    for path in (f"/api/v1/warehouse/material-batches/{identity}",
                 f'/api/v1/warehouse/material-batches/by-no/{inbound.json()["batch_no"]}',
                 f"/api/v1/warehouse/material-batches/{identity}/trace"):
        detail = await qr_api.get(path, headers=headers(101))
        assert detail.status_code == 200
        body = detail.json()["batch"] if path.endswith("/trace") else detail.json()
        assert len(body["children"]) == 3
        assert {c["child_qr_code"] for c in body["children"]} == {c["qr_code"] for c in listed.json()}
    child = children.json()[0]
    trace = await qr_api.get(f'/api/v1/warehouse/material-batches/scan/child/{child["id"]}', headers=headers(102))
    assert trace.status_code == 200 and trace.json()["parent_batch"]["id"] == identity
    assert len(trace.json()["sibling_batches"]) == 1
    stored = f"MAT:{identity}:20010101"
    await service_db.execute(MaterialBatch.__table__.update().where(MaterialBatch.id == identity).values(qr_code=stored))
    await service_db.commit()
    for method, path in (("GET", f"/api/v1/warehouse/material-batches/scan/{identity}"),
                         ("POST", f"/api/v1/warehouse/material-batches/{identity}/reprint-qr")):
        response = await qr_api.request(method, path, headers=headers(102))
        assert response.status_code == 200
        assert response.json()["qr_image_base64"] == generate_qr_base64(stored)
