"""B/C changes require an actual worker confirmation; owned PostgreSQL only."""
import asyncio

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import product_box as m
from app.services import product_box_service as boxes, product_production_service as production
from app.services import product_conversion_service as service
from app.services.qr_transaction_service import QrError
from .service_fixtures import create_service_fixture, seed_service_fixture
from .test_production import actor, bound, selected, save


async def prepared(db, qty=100, authorized=True, material_batch_id=None):
    db.add(m.ProductRouteRevision(id=704, route_code='CONVERSION-C', revision=1, product_code='C',
        steps_json=[{'code':c,'machine_ids':[601,602]} for c in ['CUT','EXTRA']],
        first_output_process_code='CUT', is_published=True, created_by=102))
    await db.flush()
    await db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id==802).values(route_revision_id=704))
    if authorized:
        await db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id==801).values(conversion_authorization={
            'targets':[dict(target_order_product_id='802',source_route_revision_id='701',target_route_revision_id='704',
                difference_process_codes=['EXTRA'],authorized_by=102,authorized_at='2026-10-28T00:00:00+00:00')]}))
    db.add_all([m.MachineOrderProcessState(id=i,assignment_id=501,order_product_id=802,route_revision_id=704,
        process_code=code,target_qty=0) for i,code in [(1003,'CUT'),(1004,'EXTRA')]])
    await db.flush()
    box=(await bound(db))[0]; source=await selected(db)
    current=await production.save_quantity(db,actor(),box_id=int(box['id']),context_id=int(source['context']['id']),
        current_qty=qty,expected_version=box['version'],state_version=source['state']['version'],
        material_batch_id=material_batch_id,idempotency_key='conversion-initial-quantity')
    labels=(await boxes.generate_batch(db,actor(102),count=4,idempotency_key='conversion-child-labels'))['items']
    target=await selected(db,product=802,key='select-conversion-target')
    return current,target,labels


async def create(db,current,who=104,key='conversion-create-001',**extra):
    return await service.create_conversion(db,actor(who),box_id=int(current['box']['id']),
        target_order_product_id=802,expected_version=current['box']['version'],idempotency_key=key,**extra)


async def confirm(db,item,current,target,qty=100,child=None,who=101,key='conversion-confirm-001',**extra):
    return await service.confirm_conversion(db,actor(who),conversion_id=int(item['id']),
        context_id=int(target['context']['id']),actual_qty=qty,confirm=True,
        child_qr_payload=child,expected_version=current['box']['version'],conversion_version=item['version'],
        idempotency_key=key,**extra)


@pytest.mark.asyncio
async def test_full_b_to_c_and_back_keep_identity_and_single_output(service_db):
    current,target,labels=await prepared(service_db)
    item=await create(service_db,current)
    assert item['confirmation_status']=='pending_operator_confirmation' and item['actual_qty'] is None
    assert (await service_db.get(m.ProductBox,int(current['box']['id']))).product_code=='B'
    result=await confirm(service_db,item,current,target)
    assert result['converted_box']['product_code']=='C' and result['converted_box']['qr_payload']==current['box']['qr_payload']
    assert result['converted_box']['current_qty']==100 and result['relation'] is None
    assert await service_db.scalar(select(func.sum(m.ProductOutputAllocation.available_qty)))==100
    assert (await service_db.get(m.BoxProcessQuantity,int(current['quantity']['id']),populate_existing=True)).current_qty==0
    source_state=await production.state_info(service_db,actor(),await service_db.get(m.MachineOrderProcessState,1001))
    assert source_state['current_qty']==0
    assert (await confirm(service_db,item,current,target))==result
    back=await service.create_conversion(service_db,actor(102),box_id=int(current['box']['id']),
        target_order_product_id=801,expected_version=result['converted_box']['version'],idempotency_key='back-conversion-create')
    source=await selected(service_db,key='back-conversion-context')
    restored=await confirm(service_db,back,{'box':result['converted_box']},source,key='back-conversion-confirm')
    assert restored['converted_box']['product_code']=='B' and restored['converted_box']['qr_payload']==current['box']['qr_payload']
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBox))==1
    assert await service_db.scalar(select(func.count()).select_from(m.ProductOutputAllocation))==1
    c_state=await production.state_info(service_db,actor(),await service_db.get(m.MachineOrderProcessState,1003))
    assert c_state['current_qty']==0


@pytest.mark.asyncio
async def test_partial_conversion_preserves_parent_usage_and_child_lineage(service_db):
    current,target,labels=await prepared(service_db)
    item=await create(service_db,current)
    result=await confirm(service_db,item,current,target,qty=30,child=labels[0]['qr_payload'])
    assert result['source_box']['product_code']=='B' and result['source_box']['current_qty']==70
    assert result['converted_box']['product_code']=='C' and result['converted_box']['current_qty']==30
    assert result['converted_box']['order_id']==401 and result['relation']['relation_type']=='partial_conversion'
    allocations=(await service_db.scalars(select(m.ProductOutputAllocation).order_by(m.ProductOutputAllocation.id))).all()
    assert [a.available_qty for a in allocations]==[70,30] and sum(a.order_qty for a in allocations)==100
    assert {a.order_product_id for a in allocations}=={801} and allocations[1].origin_allocation_id==allocations[0].id
    assert await service_db.scalar(select(func.sum(m.ProductBox.current_qty)))==100
    from app.services.product_process_service import trace_box
    for box in (result['source_box'],result['converted_box']):
        trace=await trace_box(service_db,actor(104),box_id=int(box['id']))
        assert trace['conversions_total']==1 and trace['relations_total']==1


@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['zero','negative','over','bool','fraction','missing_child','outside_child','bound_child',
    'stale_box','stale_conversion','wrong_context','admin','owner','false_confirmation','paused','closed_assignment'])
async def test_confirmation_rejections_are_atomic(service_db,failure):
    current,target,labels=await prepared(service_db);item=await create(service_db,current)
    kwargs=dict(qty=30,child=labels[0]['qr_payload'])
    if failure in ['zero','negative','over','bool','fraction']:kwargs['qty']={'zero':0,'negative':-1,'over':101,'bool':True,'fraction':1.5}[failure]
    elif failure=='missing_child':kwargs['child']=None
    elif failure=='outside_child':kwargs['child']='PFB:v1:999999:PFB-20261028-999999'
    elif failure=='bound_child':kwargs['child']=current['box']['qr_payload']
    elif failure=='stale_box':current['box']['version']=99
    elif failure=='stale_conversion':item['version']=99
    elif failure=='wrong_context':target=current
    elif failure in ['admin','owner']:kwargs['who']=107 if failure=='admin' else 104
    elif failure=='false_confirmation':
        with pytest.raises(QrError):
            await service.confirm_conversion(service_db,actor(),conversion_id=int(item['id']),context_id=int(target['context']['id']),
                actual_qty=30,confirm=False,child_qr_payload=kwargs['child'],expected_version=current['box']['version'],
                conversion_version=item['version'],idempotency_key='false-conversion-confirm')
        return
    elif failure=='paused':
        from app.models.warehouse import MaterialBatch
        service_db.add(MaterialBatch(id=1,qr_uid='CONVERT-MAT',gross_weight=1,current_weight=1))
        await service_db.flush()
        service_db.add(m.CoilSpecException(order_id=401,state_id=1001,material_batch_id=1,expected_spec={},actual_spec={},
            active_dedupe_key='conversion-source-paused',status='confirmed',resolution='pause',created_by=101,
            confirmed_by=102,confirmed_at=func.clock_timestamp()))
        await service_db.flush()
    elif failure=='closed_assignment':
        from app.models.production import PlanMachineAssignment
        await service_db.execute(update(PlanMachineAssignment).where(PlanMachineAssignment.id==501).values(is_active=False))
    with pytest.raises(QrError):await confirm(service_db,item,current,target,**kwargs)
    box=await service_db.get(m.ProductBox,int(current['box']['id']),populate_existing=True)
    assert box.product_code=='B' and box.current_qty==100
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBox))==1
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBoxRelation))==0
    assert (await service_db.get(m.ProductConversionRecord,int(item['id']),populate_existing=True)).actual_qty is None


@pytest.mark.asyncio
async def test_cancel_unconfirmed_and_duplicate_pending_do_not_mutate(service_db):
    current,target,labels=await prepared(service_db);item=await create(service_db,current)
    assert (await create(service_db,current,key='second-create-same-condition'))['id']==item['id']
    result=await service.cancel_conversion(service_db,actor(104),conversion_id=int(item['id']),conversion_version=1,
        reason='',idempotency_key='conversion-cancel-001')
    assert result['confirmation_status']=='cancelled' and result['cancelled_by']==104
    with pytest.raises(QrError):await confirm(service_db,item,current,target)
    assert (await service_db.get(m.ProductBox,int(current['box']['id']))).current_qty==100
    assert (await service_db.get(m.ProductBox,int(current['box']['id']))).product_code=='B'


@pytest.mark.asyncio
async def test_difference_scan_pre_authorization_creates_only_pending(service_db):
    current,target,labels=await prepared(service_db)
    extra=await selected(service_db,product=802,process='EXTRA',key='difference-context')
    result=await boxes.scan_box(service_db,actor(),qr_payload=current['box']['qr_payload'],context_id=int(extra['context']['id']))
    item=result['conversion']['pending'][0]
    assert item['trigger_type']=='pre_authorized' and item['proposed_qty']==100 and item['target_process_code']=='EXTRA'
    assert result['box']['product_code']=='B' and result['box']['current_qty']==100
    repeated=await boxes.scan_box(service_db,actor(),qr_payload=current['box']['qr_payload'],context_id=int(extra['context']['id']))
    assert repeated['conversion']['pending'][0]['id']==item['id']
    confirmed=await confirm(service_db,item,current,extra,qty=30,child=labels[0]['qr_payload'])
    assert confirmed['converted_box']['current_process_code']=='EXTRA'


@pytest.mark.asyncio
async def test_unapproved_difference_scan_and_unrelated_target_cannot_convert(service_db):
    current,target,labels=await prepared(service_db,authorized=False)
    extra=await selected(service_db,product=802,process='EXTRA',key='unauthorized-difference-context')
    with pytest.raises(QrError):
        await boxes.scan_box(service_db,actor(),qr_payload=current['box']['qr_payload'],context_id=int(extra['context']['id']))
    with pytest.raises(QrError):
        await service.create_conversion(service_db,actor(104),box_id=int(current['box']['id']),target_order_product_id=803,
            expected_version=current['box']['version'],idempotency_key='forbid-cross-order-conversion')
    with pytest.raises(QrError):await create(service_db,current,who=101)
    with pytest.raises(QrError):await create(service_db,current,who=105)
    assert await service_db.scalar(select(func.count()).select_from(m.ProductConversionRecord))==0


@pytest.mark.asyncio
async def test_partial_reverse_and_mixed_uses_remain_conserved(service_db):
    current,target,labels=await prepared(service_db)
    allocation=current['allocation']
    await production.allocate_output(service_db,actor(104),source_quantity_id=int(allocation['source_quantity_id']),
        order_qty=60,stock_qty=40,expected_version=allocation['version'],idempotency_key='conversion-mixed-uses')
    item=await create(service_db,current)
    converted=await confirm(service_db,item,current,target,qty=70,child=labels[0]['qr_payload'])
    child=converted['converted_box']
    back=await service.create_conversion(service_db,actor(104),box_id=int(child['id']),target_order_product_id=801,
        expected_version=child['version'],idempotency_key='partial-reverse-create')
    source=await selected(service_db,key='partial-reverse-context')
    result=await confirm(service_db,back,{'box':child},source,qty=20,child=labels[1]['qr_payload'],key='partial-reverse-confirm')
    assert result['source_box']['product_code']=='C' and result['source_box']['current_qty']==50
    assert result['converted_box']['product_code']=='B' and result['converted_box']['current_qty']==20
    rows=(await service_db.scalars(select(m.ProductOutputAllocation))).all()
    assert sum(x.available_qty for x in rows)==100 and sum(x.order_qty for x in rows)==60 and sum(x.stock_qty for x in rows)==40
    assert await service_db.scalar(select(func.sum(m.ProductBox.current_qty)))==100


@pytest.mark.asyncio
async def test_conversion_entry_locked_but_next_process_works_without_new_output(service_db):
    current,target,labels=await prepared(service_db)
    item=await create(service_db,current)
    result=await confirm(service_db,item,current,target,qty=30,child=labels[0]['qr_payload'])
    for box,selection in [(result['source_box'],current),(result['converted_box'],target)]:
        state=await production.state_info(service_db,actor(),await service_db.get(m.MachineOrderProcessState,int(selection['state']['id'])))
        assert next(row for row in state['boxes'] if row['box_id']==box['id'])['quantity_locked']
        with pytest.raises(QrError):
            await production.save_quantity(service_db,actor(),box_id=int(box['id']),context_id=int(selection['context']['id']),
                current_qty=100,expected_version=box['version'],state_version=state['version'],idempotency_key='reject-conversion-reinflate-'+box['id'])
    extra=await selected(service_db,product=802,process='EXTRA',key='converted-next-context')
    from app.services.product_process_service import advance
    moved=await advance(service_db,actor(),box_id=int(result['converted_box']['id']),context_id=int(extra['context']['id']),
        expected_version=result['converted_box']['version'],state_version=extra['state']['version'],idempotency_key='converted-next-step')
    assert moved['box']['current_qty']==30 and moved['quantity']['input_qty']==30
    assert await service_db.scalar(select(func.sum(m.ProductOutputAllocation.available_qty)))==100
    recounted=await save(service_db,moved['box'],moved,25,key='converted-next-recount')
    assert recounted['box']['current_qty']==25 and recounted['allocation']['available_qty']==30
    # Publishing a new target route must not strand a converted, fixed-route box.
    service_db.add(m.ProductRouteRevision(id=705,route_code='CONVERSION-C',revision=2,product_code='C',
        steps_json=[{'code':c,'machine_ids':[601,602]} for c in ['CUT','EXTRA','PACK']],
        first_output_process_code='CUT',is_published=True,created_by=102))
    await service_db.flush()
    await service_db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id==802).values(route_revision_id=705))
    from .test_production import machine_qr
    scan=await production.scan_machine(service_db,actor(),machine_qr=machine_qr())
    old=await production.select_production(service_db,actor(),scan_ticket=scan['scan_ticket'],assignment_id=501,
        order_product_id=802,process_code='EXTRA',state_id=1004,idempotency_key='converted-old-route-context')
    assert old['state']['route_revision_id']=='704'


@pytest.mark.asyncio
async def test_revoked_pre_authorization_cannot_confirm_pending(service_db):
    current,target,labels=await prepared(service_db)
    extra=await selected(service_db,product=802,process='EXTRA',key='revoked-auto-context')
    scan=await boxes.scan_box(service_db,actor(),qr_payload=current['box']['qr_payload'],context_id=int(extra['context']['id']))
    item=scan['conversion']['pending'][0]
    await service_db.execute(update(m.ProductOrderProduct).where(m.ProductOrderProduct.id==801).values(conversion_authorization={}))
    with pytest.raises(QrError):await confirm(service_db,item,current,extra)
    assert (await service_db.get(m.ProductBox,int(current['box']['id']))).product_code=='B'


@pytest.mark.asyncio
async def test_confirm_cancel_race_has_one_terminal_outcome(qr_database_factory):
    with qr_database_factory() as engine:
        with engine.begin() as connection:create_service_fixture(connection);seed_service_fixture(connection)
        ae=create_async_engine(engine.url.set(drivername='postgresql+asyncpg'),echo=False,poolclass=NullPool)
        sessions=async_sessionmaker(ae,expire_on_commit=False,autoflush=False)
        try:
            async with sessions() as db:
                current,target,labels=await prepared(db);item=await create(db,current);await db.commit()
            async def action(which):
                async with sessions() as db:
                    try:
                        value=await confirm(db,item,current,target) if which=='confirm' else await service.cancel_conversion(
                            db,actor(104),conversion_id=int(item['id']),conversion_version=1,reason=None,idempotency_key='race-cancel-conversion')
                        await db.commit();return value
                    except QrError:await db.rollback();return None
            results=await asyncio.gather(action('confirm'),action('cancel'))
            assert sum(x is not None for x in results)==1
            async with sessions() as db:
                record=await db.get(m.ProductConversionRecord,int(item['id']));box=await db.get(m.ProductBox,int(current['box']['id']))
                assert record.confirmation_status in ['confirmed','cancelled']
                assert box.current_qty==100 and box.product_code==('C' if record.confirmation_status=='confirmed' else 'B')
        finally:await ae.dispose()
