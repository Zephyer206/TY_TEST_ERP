"""Actual authenticated split contracts and parent-scoped child preview."""
import pytest
from sqlalchemy import func, select

from app.models import product_box as m
from .test_pool_api import qr_api, headers
from .test_split import prepared


async def body_for(service_db):
    current, labels, _ = await prepared(service_db)
    await service_db.commit()
    return current, labels, dict(child_qr_payload=labels[0]["qr_payload"], quantity=30, order_qty=30, stock_qty=0,
        expected_version=current["box"]["version"], allocation_version=current["allocation"]["version"], idempotency_key="http-split-contract")


@pytest.mark.asyncio
async def test_http_partition_roundtrip_relation_and_replay(qr_api, service_db):
    current, labels, body = await body_for(service_db)
    url = f"/api/v1/product-boxes/{current['box']['id']}/split"
    response = await qr_api.post(url, json=body, headers=headers(103))
    assert response.status_code == 201
    result = response.json()
    assert result["parent"]["current_qty"] == 70 and result["child"]["current_qty"] == 30
    assert result["child_allocation"]["origin_allocation_id"] == result["parent_allocation"]["id"]
    assert (await qr_api.post(url, json=body, headers=headers(103))).json() == result
    trace = await qr_api.get(f"/api/v1/product-boxes/{result['child']['id']}/trace", headers=headers(103))
    assert trace.status_code == 200
    assert trace.json()["relations"][0]["parent_current_qty"] == 70
    assert trace.json()["split"]["allowed_actions"] == ["split"]
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBoxRelation)) == 1


@pytest.mark.asyncio
async def test_order_owner_scoped_preview_does_not_grant_general_pool_access(qr_api, service_db):
    current, labels, body = await body_for(service_db)
    preview = dict(qr_payload=labels[0]["qr_payload"], split_parent_id=current["box"]["id"])
    denied = await qr_api.post('/api/v1/product-boxes/scan', json={"qr_payload": labels[0]["qr_payload"]}, headers=headers(104))
    assert denied.status_code == 403
    allowed = await qr_api.post('/api/v1/product-boxes/scan', json=preview, headers=headers(104))
    assert allowed.status_code == 200 and allowed.json()["box"] is None and allowed.json()["allowed_actions"] == []
    wrong_owner = await qr_api.post('/api/v1/product-boxes/scan', json=preview, headers=headers(105))
    assert wrong_owner.status_code == 403
    body.update(target_order_product_id='804', target_state_id='1005', target_state_version=1)
    response = await qr_api.post(f"/api/v1/product-boxes/{current['box']['id']}/split", json=body, headers=headers(104))
    assert response.status_code == 201 and response.json()["child"]["order_id"] == 403
    used = await qr_api.post('/api/v1/product-boxes/scan', json=preview, headers=headers(104))
    assert used.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize('change', [{"quantity": True}, {"quantity": 1.5}, {"quantity": "30"}, {"quantity": 0},
    {"operator_id": 107}, {"allocation_version": False}, {"target_order_product_id": "804"}])
async def test_http_split_schema_rejects_invalid_or_self_authorized_fields(qr_api, change):
    body = dict(child_qr_payload='not-a-real-label', quantity=30, order_qty=30, stock_qty=0,
        expected_version=1, allocation_version=1, idempotency_key='http-invalid-split') | change
    response = await qr_api.post('/api/v1/product-boxes/1/split', json=body, headers=headers(103))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_metadata_identity_and_role_guards_remain_after_partition(qr_api, service_db):
    current, labels, body = await body_for(service_db)
    url = f"/api/v1/product-boxes/{current['box']['id']}/split"
    rejected = await qr_api.post(url, json=body, headers=headers(101))
    assert rejected.status_code == 403
    result = (await qr_api.post(url, json=body, headers=headers(103))).json()
    child = result['child']
    edit = await qr_api.patch(f"/api/v1/product-boxes/{child['id']}/metadata", headers=headers(103), json=dict(
        customer_part_no='SPLIT-LABEL-EDIT', expected_version=child['version'], idempotency_key='http-split-metadata'))
    assert edit.status_code == 200 and edit.json()['qr_payload'] == labels[0]['qr_payload']
    forged = await qr_api.patch(f"/api/v1/product-boxes/{child['id']}/metadata", headers=headers(103), json=dict(
        order_id=402, expected_version=2, idempotency_key='http-split-forged-order'))
    assert forged.status_code == 422
