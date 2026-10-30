"""Authenticated HTTP contracts for comparisons, decisions and in-app outbox."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import product_box as m
from app.services import notification_service as notifications
from .test_pool_api import qr_api, headers
from .test_exceptions_notifications import prepared


async def body_for(db):
    box, choice = await prepared(db)
    await db.commit()
    return dict(context_id=choice["context"]["id"], product_box_id=box["id"], material_batch_id=9502,
        continue_production=True, idempotency_key="http-coil-record")


@pytest.mark.asyncio
async def test_http_preview_record_confirm_and_deliver_are_independent(qr_api, service_db):
    body = await body_for(service_db)
    preview = await qr_api.post('/api/v1/coil-spec-exceptions', json=body | dict(
        continue_production=False, idempotency_key="http-coil-preview"), headers=headers(101))
    assert preview.status_code == 200 and preview.json()["requires_confirmation"]
    result = await qr_api.post('/api/v1/coil-spec-exceptions', json=body, headers=headers(101))
    assert result.status_code == 200
    item = result.json()["exception"]
    assert item["status"] == "pending_confirmation" and item["delivery_summary"] == dict(pending=2, sent=0, failed=0)
    assert (await qr_api.post('/api/v1/coil-spec-exceptions', json=body, headers=headers(101))).json() == result.json()
    request = dict(resolution="accept_continue", remark=None, expected_version=item["version"], idempotency_key="http-owner-confirm")
    url = f"/api/v1/coil-spec-exceptions/{item['id']}/confirm"
    assert (await qr_api.post(url, json=request, headers=headers(105))).status_code == 403
    confirmed = await qr_api.post(url, json=request, headers=headers(104))
    assert confirmed.status_code == 200 and confirmed.json()["confirmed_by"] == 104
    assert (await qr_api.post(url, json=request | dict(idempotency_key="http-losing-confirm"), headers=headers(102))).status_code == 409
    pending = await qr_api.get('/api/v1/notifications?delivery_status=pending', headers=headers(104))
    assert pending.status_code == 200 and pending.json()["total"] == 1
    assert not pending.json()["can_manage_deliveries"]
    assert (await qr_api.get('/api/v1/notifications', headers=headers(105))).json()["total"] == 0
    await notifications.dispatch_due(service_db)
    await service_db.commit()
    sent = await qr_api.get('/api/v1/notifications?unread_only=true&delivery_status=sent', headers=headers(104))
    assert sent.json()["total"] == 1 and sent.json()["items"][0]["exception"]["resolution"] == "accept_continue"
    assert (await qr_api.get('/api/v1/qr-admin/notification-deliveries', headers=headers(102))).status_code == 403
    queue = await qr_api.get('/api/v1/qr-admin/notification-deliveries', headers=headers(107))
    assert queue.status_code == 200 and queue.json()["can_manage_deliveries"] and queue.json()["total"] == 2
    assert len(queue.json()["items"][0]["attempt_history"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"operator_id": 107}, {"expected_spec": {}}, {"actual_spec": {}},
    {"continue_production": "true"}, {"material_batch_id": True}, {"material_batch_id": 9502.5}])
async def test_http_rejects_forged_actors_specs_and_coercion(qr_api, change):
    body = dict(context_id="1", material_batch_id=9502, continue_production=True, idempotency_key="http-invalid-coil") | change
    response = await qr_api.post('/api/v1/coil-spec-exceptions', json=body, headers=headers(101))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_http_pause_resume_preserves_original_resolution(qr_api, service_db):
    body = await body_for(service_db)
    item = (await qr_api.post('/api/v1/coil-spec-exceptions', json=body, headers=headers(101))).json()["exception"]
    paused = await qr_api.post(f"/api/v1/coil-spec-exceptions/{item['id']}/confirm", headers=headers(102), json=dict(
        resolution="reconfirm_coil", remark="", expected_version=1, idempotency_key="http-reconfirm-coil"))
    assert paused.status_code == 200 and paused.json()["blocked"]
    url = f"/api/v1/coil-spec-exceptions/{item['id']}/resume"
    request = dict(rechecked_material_batch_id=9501, reason="Actual matching coil rechecked", expected_version=2,
        idempotency_key="http-coil-resume")
    assert (await qr_api.post(url, headers=headers(104), json=request | dict(reason="  "))).status_code == 422
    assert (await qr_api.post(url, headers=headers(104), json=request | dict(rechecked_material_batch_id=9502))).status_code == 409
    resumed = await qr_api.post(url, headers=headers(104), json=request)
    assert resumed.status_code == 200 and resumed.json()["resolution"] == "reconfirm_coil"
    assert resumed.json()["released_by"] == 104 and not resumed.json()["blocked"]


@pytest.mark.asyncio
async def test_http_manual_retry_keeps_failed_attempt_history(qr_api, service_db):
    body = await body_for(service_db)
    await qr_api.post('/api/v1/coil-spec-exceptions', json=body, headers=headers(101))
    now = await service_db.scalar(select(func.clock_timestamp()))
    async def fail(db, row):
        raise RuntimeError("Synthetic failure")
    for minutes in [0, 1, 6, 21, 51]:
        await notifications.dispatch_due(service_db, now=now+timedelta(minutes=minutes), sink=fail)
    await service_db.commit()
    row = await service_db.scalar(select(m.NotificationOutbox).order_by(m.NotificationOutbox.id).limit(1))
    url = f"/api/v1/qr-admin/notification-deliveries/{row.id}/retry"
    body = dict(expected_version=row.version, idempotency_key="http-admin-retry-batch")
    assert (await qr_api.post(url, json=body, headers=headers(102))).status_code == 403
    retry = await qr_api.post(url, json=body, headers=headers(107))
    assert retry.status_code == 200 and retry.json()["retry_batch"] == 1 and retry.json()["delivery_status"] == "pending"
    assert len(retry.json()["attempt_history"]) == 5
    assert (await qr_api.post(url, json=body, headers=headers(107))).json() == retry.json()
    await notifications.dispatch_due(service_db)
    await service_db.commit()
    queue = (await qr_api.get('/api/v1/qr-admin/notification-deliveries', headers=headers(107))).json()
    retried = next(x for x in queue["items"] if x["id"] == str(row.id))
    assert retried["delivery_status"] == "sent" and len(retried["attempt_history"]) == 6


@pytest.mark.asyncio
async def test_http_context_and_filter_scope_guards(qr_api, service_db):
    body = await body_for(service_db)
    assert (await qr_api.post('/api/v1/coil-spec-exceptions', json=body, headers=headers(102))).status_code == 403
    assert (await qr_api.post('/api/v1/coil-spec-exceptions', json=body, headers=headers(105))).status_code == 403
    assert (await qr_api.get('/api/v1/notifications?delivery_status=unknown', headers=headers(104))).status_code == 422
