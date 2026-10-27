"""Actual authenticated production routes and typed response contracts."""
import pytest

from .test_pool_api import headers, qr_api
from .test_order_configuration import configuration, new_order


async def post(client, path, body, who=101, status=200):
    response = await client.post('/api/v1' + path, json=body, headers=headers(who))
    assert response.status_code == status
    return response.json()


async def select(client, who=101):
    scan = await post(client, '/machines/scan-production', {'machine_qr': 'MCN:601:20261025120000:machine_no=TEST-M601'}, who)
    assert scan['actor']['id'] == who and scan['assignments'][0]['plan_no']
    return await post(client, '/machines/production-contexts', dict(scan_ticket=scan['scan_ticket'],
        assignment_id=501, order_product_id='801', process_code='CUT', idempotency_key='api-select-production'), who, 201)


@pytest.mark.asyncio
async def test_configuration_http_roundtrip_and_field_whitelist(qr_api, service_db):
    await new_order(service_db)
    await service_db.commit()
    data = configuration()
    response = await qr_api.put('/api/v1/production/plans/403/qr-context', json=data, headers=headers(102))
    assert response.status_code == 200
    assert response.json()['version'] == 1 and response.json()['products'][0]['can_bind']
    data['operator_id'] = 107
    rejected = await qr_api.put('/api/v1/production/plans/403/qr-context', json=data, headers=headers(102))
    assert rejected.status_code == 422


@pytest.mark.asyncio
async def test_quantity_completion_correction_and_allocation_http(qr_api):
    generated = await post(qr_api, '/product-qr-pool/batches', {'count': 1, 'idempotency_key': 'api-production-label'}, 102, 201)
    bound = await post(qr_api, '/product-boxes/bind', {'qr_payload': generated['items'][0]['qr_payload'],
        'order_product_id': '801', 'idempotency_key': 'api-production-bind'}, 103, 201)
    selected = await select(qr_api)
    body = dict(context_id=selected['context']['id'], current_qty=30, expected_version=1,
        state_version=selected['state']['version'], idempotency_key='api-production-quantity')
    saved = await post(qr_api, f"/product-boxes/{bound['box']['id']}/quantities", body)
    assert saved['box']['current_qty'] == 30 and saved['quantity']['source_quantity_id'] == saved['quantity']['id']
    allocation = await post(qr_api, '/production/output-allocations', dict(source_quantity_id=saved['quantity']['id'],
        order_qty=20, stock_qty=10, expected_version=saved['allocation']['version'], idempotency_key='api-production-allocation'), 104)
    assert allocation['manually_adjusted'] and allocation['stock_qty'] == 10
    scan = await post(qr_api, '/machines/scan-production', {'machine_qr': 'MCN:601:20261025120000:machine_no=TEST-M601',
        'context_id': selected['context']['id']})
    assert scan['completion_intent'] and scan['scan_ticket'] is None
    completed = await post(qr_api, '/machines/601/production-complete', dict(context_id=selected['context']['id'],
        confirm_quantity_difference=True, expected_version=scan['state']['version'], idempotency_key='api-production-complete'))
    assert completed['state']['production_status'] == 'completed'
    result = await post(qr_api, f"/product-boxes/{bound['box']['id']}/quantity-corrections", dict(state_id=completed['state']['id'],
        current_qty=30, reason='Verified recount', expected_version=saved['box']['version'], state_version=completed['state']['version'],
        idempotency_key='api-production-correction'), 102)
    assert result['state']['production_status'] == 'completed'


@pytest.mark.asyncio
@pytest.mark.parametrize('value', [True, 1.5, '30', -1])
async def test_http_quantity_schema_rejects_coercion(qr_api, value):
    response = await qr_api.post('/api/v1/product-boxes/1/quantities', headers=headers(101), json=dict(
        context_id='1', current_qty=value, expected_version=1, state_version=1, idempotency_key='invalid-api-quantity'))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_supervisor_read_context_is_not_worker_authority(qr_api):
    selected = await select(qr_api, 102)
    assert 'quantity' not in selected['state']['allowed_actions']
    response = await qr_api.post('/api/v1/product-boxes/1/quantities', headers=headers(102), json=dict(
        context_id=selected['context']['id'], current_qty=30, expected_version=1,
        state_version=selected['state']['version'], idempotency_key='supervisor-not-worker'))
    assert response.status_code == 403
