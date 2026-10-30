"""Authenticated conversion API, strict requests and mounted registry contracts."""
import pytest
from sqlalchemy import select
from app.models import product_box as m
from .test_pool_api import qr_api, headers
from .test_conversion import prepared


@pytest.mark.asyncio
async def test_http_create_confirm_partial_and_child_trace(qr_api,service_db):
    current,target,labels=await prepared(service_db);await service_db.commit()
    body=dict(box_id=current['box']['id'],target_order_product_id='802',expected_version=current['box']['version'],idempotency_key='http-conversion-create')
    assert (await qr_api.post('/api/v1/product-conversions',headers=headers(101),json=body)).status_code==403
    response=await qr_api.post('/api/v1/product-conversions',headers=headers(104),json=body)
    assert response.status_code==201;item=response.json()
    assert (await qr_api.post('/api/v1/product-conversions',headers=headers(104),json=body)).json()==item
    url=f"/api/v1/product-conversions/{item['id']}/confirm"
    request=dict(context_id=target['context']['id'],actual_qty=30,confirm=True,child_qr_payload=labels[0]['qr_payload'],
        expected_version=current['box']['version'],conversion_version=1,idempotency_key='http-conversion-confirm')
    assert (await qr_api.post(url,headers=headers(107),json=request)).status_code==403
    result=await qr_api.post(url,headers=headers(101),json=request)
    assert result.status_code==200,result.text
    data=result.json();assert data['source_box']['current_qty']==70 and data['converted_box']['current_qty']==30
    assert (await qr_api.post(url,headers=headers(101),json=request)).json()==data
    trace=await qr_api.get(f"/api/v1/product-boxes/{data['converted_box']['id']}/trace",headers=headers(104))
    assert trace.status_code==200 and trace.json()['conversions_total']==1
    assert (await qr_api.get(f"/api/v1/product-boxes/{data['source_box']['id']}/trace",headers=headers(105))).status_code==403


@pytest.mark.asyncio
@pytest.mark.parametrize('change',[{'trigger_type':'pre_authorized'},{'created_by':107},{'expected_version':True},
    {'proposed_qty':1.5},{'target_order_product_id':True},{'target_order_product_id':'0802'}])
async def test_http_forged_authorization_and_bad_creation_input_rejected(qr_api,change):
    body=dict(box_id='1',target_order_product_id='802',expected_version=1,idempotency_key='invalid-conversion-create')|change
    assert (await qr_api.post('/api/v1/product-conversions',headers=headers(104),json=body)).status_code==422


@pytest.mark.asyncio
@pytest.mark.parametrize('change',[{'actual_qty':0},{'actual_qty':True},{'actual_qty':'30'},{'confirm':'true'},{'operator_id':101}])
async def test_http_confirmation_is_strict(qr_api,change):
    request=dict(context_id='1',actual_qty=30,confirm=True,expected_version=1,conversion_version=1,
        idempotency_key='invalid-conversion-confirm')|change
    assert (await qr_api.post('/api/v1/product-conversions/1/confirm',headers=headers(101),json=request)).status_code==422


@pytest.mark.asyncio
async def test_http_pre_authorized_scan_cancel_and_repeated_scan_preserves_box(qr_api,service_db):
    current,target,labels=await prepared(service_db)
    from .test_production import selected
    choice=await selected(service_db,product=802,process='EXTRA',key='http-auto-context');await service_db.commit()
    body=dict(qr_payload=current['box']['qr_payload'],context_id=choice['context']['id'])
    scan=await qr_api.post('/api/v1/product-boxes/scan',headers=headers(101),json=body)
    assert scan.status_code==200,scan.text
    item=scan.json()['conversion']['pending'][0];assert item['trigger_type']=='pre_authorized'
    url=f"/api/v1/product-conversions/{item['id']}/cancel"
    cancelled=await qr_api.post(url,headers=headers(101),json=dict(context_id=choice['context']['id'],conversion_version=1,
        reason='实际尚未完成',idempotency_key='http-worker-cancel-conversion'))
    assert cancelled.status_code==200 and cancelled.json()['confirmation_status']=='cancelled'
    box=await service_db.get(m.ProductBox,int(current['box']['id']),populate_existing=True)
    assert box.product_code=='B' and box.current_qty==100
    assert (await qr_api.post('/api/v1/product-boxes/scan',headers=headers(105),json=body)).status_code==403
