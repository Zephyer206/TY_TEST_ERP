"""Integration acceptance in an owned disposable PostgreSQL database only."""
import asyncio
from decimal import Decimal
from types import SimpleNamespace
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.database import Base, get_db
from app.api.deps import get_current_user
from app.api.costing import router as costing_router
from app.api.part_treatments import router as treatments_router
from app.api.quote_groups import router as quotation_router
from app.models import Customer, User, Part, PartCustomerAlias, Tooling, ToolingPart, PartToolingSpec
from app.models.material_dict import MaterialDict
from app.models.price import TreatmentDict
from app.models.costing import CostingTask, CostingItem, CostingRevision
from backend.tests.qr.conftest import owned_database_factory


@pytest.fixture(scope='module')
def database():
    generator=owned_database_factory();factory=next(generator)
    try:
        with factory() as engine:
            with engine.begin() as c:
                names=['users','customers','parts','finished_goods_inventory','part_customer_aliases','tooling',
                    'tooling_parts','part_tooling_specs','material_dict','treatment_dict','quote_groups',
                    'quote_group_items','audit_logs','costing_tasks','costing_items','costing_revisions']
                c.execute(text('CREATE TABLE customer_inquiries (id integer PRIMARY KEY)'))
                for name in names: Base.metadata.tables[name].create(c,checkfirst=True)
                c.execute(User.__table__.insert().values(id=1,username='acceptance',password='unused-test-marker',dept='tech',role_level=2))
                c.execute(Customer.__table__.insert(),[dict(id=1,name='核算验收客户'),dict(id=2,name='其他客户')])
                c.execute(Part.__table__.insert().values(id=1,internal_name='验收零件',material_name='QA-STEEL',net_weight=12,customer_id=1))
                c.execute(PartCustomerAlias.__table__.insert(),[dict(id=1,part_id=1,customer_id=1,customer_part_no='QA-001',is_active=True,data_quality_status='approved'),dict(id=2,part_id=1,customer_id=2,customer_part_no='OTHER',is_active=True,data_quality_status='approved')])
                c.execute(Tooling.__table__.insert(),[dict(id=1,tooling_number='QA-DIE',mold_type='连续模',is_continuous=True),dict(id=2,tooling_number='QA-SIMPLE',mold_type='简易模',is_continuous=False)])
                c.execute(ToolingPart.__table__.insert(),[dict(part_id=1,tooling_id=1),dict(part_id=1,tooling_id=2)])
                c.execute(PartToolingSpec.__table__.insert().values(id=1,part_id=1,tooling_id=1,thickness=1,width=100,pitch=20,spec_twph='1*100*20'))
                c.execute(MaterialDict.__table__.insert().values(id=1,code='QA-STEEL',name='QA-STEEL',density=10,default_price=10,scrap_price=2))
            yield engine
    finally: generator.close()


@pytest_asyncio.fixture
async def client(database):
    engine=create_async_engine(database.url.set(drivername='postgresql+asyncpg'),echo=False,poolclass=NullPool)
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    app=FastAPI();app.include_router(costing_router);app.include_router(treatments_router);app.include_router(quotation_router)
    actor=SimpleNamespace(id=1,username='acceptance',role_level=2)
    async def session():
        async with sessions() as db: yield db
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_current_user]=lambda:actor
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as cli:
        cli.actor=actor
        yield cli
    await engine.dispose()


async def new_item(client):
    task=(await client.post('/costing/tasks',json={'name':'验收任务','customer_id':1})).json()
    r=await client.post(f"/costing/tasks/{task['id']}/items",json={'alias_id':1,'part_id':1,'tooling_id':1,'spec_id':1})
    assert r.status_code==200,r.text
    return task,r.json()


def calculation():
    return dict(price_source='catalog',material_id=1,source_note='验收来源',calculation=dict(material=dict(pieces_per_blank=1),treatment_status='none'))


@pytest.mark.asyncio
async def test_identity_eligibility_and_item_retry(client):
    task,item=await new_item(client)
    route=f"/costing/tasks/{task['id']}/items"
    same=await client.post(route,json={'alias_id':1,'part_id':1,'tooling_id':1,'spec_id':1})
    assert same.json()['id']==item['id']
    assert (await client.post(route,json={'alias_id':2,'part_id':1,'tooling_id':1,'spec_id':1})).status_code==422
    assert (await client.post(route,json={'alias_id':1,'part_id':1,'tooling_id':2})).status_code==422
    assert (await client.post(route,json={'alias_id':1,'part_id':1,'tooling_id':1,'spec_id':999})).status_code==422


@pytest.mark.asyncio
async def test_part_writeback_audit_conflict_retry_and_permission(client):
    old=(await client.get('/parts/1/surface-treatment')).json()['surface_treatment']
    payload={'expected_revision':old['revision'],'source':'验收核算补录','surface_treatment':{'status':'required','items':[{'item_key':'plate','name':'电镀','requirements':'验收标准'*160,'source':'验收图纸'}]}}
    saved=await client.patch('/parts/1/surface-treatment',json=payload)
    assert saved.status_code==200,saved.text
    revision=saved.json()['surface_treatment']['revision']
    assert (await client.patch('/parts/1/surface-treatment',json=payload)).json()['surface_treatment']['revision']==revision
    payload['surface_treatment']['items'][0]['name']='喷涂'
    assert (await client.patch('/parts/1/surface-treatment',json=payload)).status_code==409
    assert (await client.get('/parts/1/surface-treatment')).json()['surface_treatment']['items'][0]['name']=='电镀'
    client.actor.role_level=1
    assert (await client.patch('/parts/1/surface-treatment',json=payload)).status_code==403


@pytest.mark.asyncio
async def test_versions_are_immutable_source_changes_are_conflicts_and_export_safe(client):
    state=(await client.get('/parts/1/surface-treatment')).json()['surface_treatment']
    assert (await client.patch('/parts/1/surface-treatment',json={'expected_revision':state['revision'],'surface_treatment':{'status':'none','items':[]}})).status_code==200
    task,item=await new_item(client);route=f"/costing/items/{item['id']}"
    payload=calculation()
    preview=(await client.post(route+'/preview',json=payload)).json()
    assert preview['result']['total']=='0.184000',preview
    save={**payload,'expected_source_token':preview['source_token'],'expected_version':0,'request_id':'test-request-0001'}
    result=await client.post(route+'/revisions',json=save)
    assert result.status_code==200,result.text
    again=await client.post(route+'/revisions',json=save)
    assert again.json()['id']==result.json()['id']
    state=(await client.get('/parts/1/surface-treatment')).json()['surface_treatment']
    await client.patch('/parts/1/surface-treatment',json={'expected_revision':state['revision'],'surface_treatment':{'status':'pending','items':[]}})
    save.update(expected_version=1,request_id='test-request-0002')
    assert (await client.post(route+'/revisions',json=save)).status_code==409
    history=(await client.get(route+'/revisions')).json()
    assert len(history)==1 and history[0]['result']['total']=='0.184000'
    exported=await client.get(f"/costing/tasks/{task['id']}/export")
    assert exported.status_code==200 and '0.184000' in exported.text and '未选用' in exported.text


@pytest.mark.asyncio
async def test_concurrent_revision_saves_do_not_lose_versions(client):
    state=(await client.get('/parts/1/surface-treatment')).json()['surface_treatment']
    await client.patch('/parts/1/surface-treatment',json={'expected_revision':state['revision'],'surface_treatment':{'status':'none','items':[]}})
    task,item=await new_item(client);route=f"/costing/items/{item['id']}"
    payload=calculation();preview=(await client.post(route+'/preview',json=payload)).json()
    requests=[{**payload,'expected_source_token':preview['source_token'],'expected_version':0,'request_id':f'concurrent-00{i}'} for i in [1,2]]
    responses=await asyncio.gather(*(client.post(route+'/revisions',json=r) for r in requests))
    assert sorted(r.status_code for r in responses)==[200,409]


@pytest.mark.asyncio
async def test_quote_and_costing_share_rates_and_utilization_without_changing_old_snapshots(client,database):
    from app.models.quote_group import QuoteGroup,QuoteGroupItem
    with database.begin() as c:
        c.execute(text('INSERT INTO customer_inquiries (id) VALUES (91)'))
        c.execute(QuoteGroup.__table__.insert().values(id=91,group_no='QA-QUOTE-91',inquiry_id=91,customer_id=1,
            project_name='共用计价验收',material_density=10,material_unit_price=10,material_scrap_price=2))
        c.execute(QuoteGroupItem.__table__.insert().values(id=91,quote_group_id=91,customer_part_no='QA-001',
            part_name='验收零件',thickness=1,width=100,pitch=20,utilization=60,product_price=1))
        c.execute(TreatmentDict.__table__.insert().values(id=91,name='共用净重收费',calc_mode='net_weight',default_rate=15,unit='元/kg'))
    response=await client.patch('/quote-groups/91',json={'surface_rule_id':91})
    assert response.status_code==200,response.text
    group=response.json()
    assert Decimal(group['surface_treatment_fee'])==Decimal('.18')
    state=(await client.get('/parts/1/surface-treatment')).json()['surface_treatment']
    await client.patch('/parts/1/surface-treatment',json={'expected_revision':state['revision'],
        'surface_treatment':{'status':'required','items':[{'item_key':'shared-rule','name':'电镀'}]}})
    task,item=await new_item(client)
    payload=dict(price_source='quote',quote_item_id=91,calculation=dict(material={},treatments=[dict(item_key='shared-rule',name='电镀',rule_id=91)]))
    cost=(await client.post(f"/costing/items/{item['id']}/preview",json=payload)).json()
    quote=(await client.post('/costing/quotation-preview',json={'material':dict(thickness=1,width=100,pitch=20,density=10,
        utilization_pct=60,material_price=10,scrap_price=2),'surface_rule_id':91,'surface_rule_snapshot':group['surface_rule_snapshot']})).json()
    assert cost['result']['total']==quote['total']=='0.364000'
    with database.begin() as c:
        c.execute(text('UPDATE parts SET net_weight=NULL WHERE id=1'))
    try:
        estimated=(await client.post(f"/costing/items/{item['id']}/preview",json=payload)).json()
        assert estimated['result']['total']=='0.364000'
        assert estimated['result']['material']['net_weight_basis']=='quote_utilization'
    finally:
        with database.begin() as c:c.execute(text('UPDATE parts SET net_weight=12 WHERE id=1'))
    with database.begin() as c:c.execute(text('UPDATE treatment_dict SET default_rate=18 WHERE id=91'))
    unchanged=(await client.get('/quote-groups/91')).json()
    assert Decimal(unchanged['surface_rule_snapshot']['rate'])==15


@pytest.mark.asyncio
async def test_import_is_read_only_preserves_rows_and_stores_explicit_selection_source(client):
    import io
    from openpyxl import Workbook
    workbook=Workbook();sheet=workbook.active;sheet.title='验收来源'
    sheet.append(['客户件号','模具编号','产品净重/g','单件毛重量(g)'])
    sheet.append(['QA-001','QA-DIE',12,20]);sheet.append(['QA-001-X','QA-DIE',None,20])
    content=io.BytesIO();workbook.save(content)
    before=(await client.get('/parts/1/surface-treatment')).json()
    preview=await client.post('/costing/imports/preview?customer_id=1',files={'file':('fixture.xlsx',content.getvalue())})
    assert preview.status_code==200,preview.text
    rows=preview.json()['rows'];assert [r['row'] for r in rows]==[2,3]
    assert rows[0]['status']=='exact' and rows[1]['status']=='needs_review'
    assert (await client.get('/parts/1/surface-treatment')).json()==before
    task=(await client.post('/costing/tasks',json={'customer_id':1,'name':'导入来源验收'})).json()
    identity={k:rows[0]['candidates'][0][k] for k in ['alias_id','part_id','tooling_id','spec_id']}
    added=await client.post(f"/costing/tasks/{task['id']}/items",json={**identity,'source_reference':rows[0]['source_reference']})
    context=(await client.get(f"/costing/items/{added.json()['id']}/context")).json()
    assert context['import_source']['sheet']=='验收来源' and context['import_source']['row']==2
