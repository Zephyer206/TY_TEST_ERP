"""Authenticated route and JSON contracts for handoff and trace."""
import pytest

from .test_pool_api import headers, qr_api
from .test_process_trace import ready


@pytest.mark.asyncio
async def test_trace_and_advance_http_and_cursor_contract(qr_api, service_db):
    current, target = await ready(service_db)
    await service_db.commit()
    box_id = current["box"]["id"]
    body = dict(context_id=target["context"]["id"], expected_version=current["box"]["version"],
        state_version=target["state"]["version"], idempotency_key="trace-http-advance")
    response = await qr_api.post(f"/api/v1/product-boxes/{box_id}/advance", json=body, headers=headers(101))
    assert response.status_code == 200
    assert response.json()["quantity"]["material_batch_id"] == 9502
    trace = await qr_api.get(f"/api/v1/product-boxes/{box_id}/trace", headers=headers(104))
    assert trace.status_code == 200
    assert trace.json()["route"]["revision"] == 1 and trace.json()["materials"][0]["batch_no"] == "TRACE-CHILD"
    first = await qr_api.get(f"/api/v1/product-boxes/{box_id}/events", params={"page_size": 1}, headers=headers(101))
    assert first.status_code == 200 and isinstance(first.json()["items"][0]["id"], str)
    second = await qr_api.get(f"/api/v1/product-boxes/{box_id}/events", params={"before_id": first.json()["next_cursor"], "page_size": 1}, headers=headers(101))
    assert second.status_code == 200 and first.json()["items"][0]["id"] != second.json()["items"][0]["id"]
    for suffix in ("trace", "events"):
        denied = await qr_api.get(f"/api/v1/product-boxes/{box_id}/{suffix}", headers=headers(105))
        assert denied.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"operator_id": 107}, {"context_id": True}, {"state_version": 1.5}, {"expected_version": "1"}])
async def test_advance_http_forbids_coerced_versions_or_actor(qr_api, change):
    body = dict(context_id="1", expected_version=1, state_version=1, idempotency_key="trace-http-invalid") | change
    response = await qr_api.post("/api/v1/product-boxes/1/advance", json=body, headers=headers(101))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_material_quantity_http_accepts_only_existing_identity(qr_api, service_db):
    current, target = await ready(service_db)
    await service_db.commit()
    response = await qr_api.post(f"/api/v1/product-boxes/{current['box']['id']}/quantities", json=dict(
        context_id=current["context"]["id"], current_qty=25, material_batch_id=999999,
        expected_version=current["box"]["version"], state_version=current["state"]["version"], idempotency_key="trace-invalid-material"), headers=headers(101))
    assert response.status_code == 400
