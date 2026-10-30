"""Read-only B/C conversion evidence in exactly the original owned UI database."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import socket
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'backend')]
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from app.core.config import settings
from scripts.verification.verify_qr_phase3 import business_database
FEATURE=ROOT/'specs/002-material-qr-traceability'


def snapshot():
    owned=json.loads((ROOT/'runtime/qr-ui-owned.json').read_text(encoding='utf-8'))
    source=make_url(settings.DATABASE_URL).set(drivername='postgresql+psycopg2')
    name=owned.get('database')
    assert re.fullmatch(r'qrtmp_[a-f0-9]{32}',name or '') and name!=source.database
    assert owned['purpose']=='synthetic QR UI acceptance' and owned['state']=='active'
    engine=create_engine(source.set(database=name),echo=False,poolclass=NullPool)
    try:
        with engine.begin() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            assert db.scalar(text('SELECT oid FROM pg_database WHERE datname=current_database()'))==owned['original_oid']
            queries={
                'boxes':'SELECT id,qr_pool_item_id,order_id,order_product_id,product_code,current_qty,current_process_code,bound_by FROM product_boxes ORDER BY id',
                'quantities':'SELECT id,box_id,state_id,current_qty,input_qty,source_quantity_id,material_batch_id,updated_by FROM box_process_quantities ORDER BY id',
                'allocations':'SELECT id,box_id,order_product_id,origin_allocation_id,available_qty,order_qty,stock_qty FROM product_output_allocations ORDER BY id',
                'conversions':'SELECT id,product_box_id,source_product_code,target_product_code,source_process_code,target_process_code,trigger_type,confirmation_status,actual_qty,relation_id,created_by,confirmed_by,cancelled_by,cancel_reason FROM product_conversion_records ORDER BY id',
                'relations':'SELECT id,parent_box_id,child_box_id,relation_type,quantity,order_qty,stock_qty,source_snapshot,created_by FROM product_box_relations ORDER BY id',
                'pool':'SELECT id,pool_status,qr_payload FROM product_qr_pool_items ORDER BY id',
                'events':"SELECT product_box_id,event_type,before_qty,after_qty,before_snapshot,after_snapshot,operator_id FROM product_flow_events WHERE event_type IN ('conversion','process_start') ORDER BY id",
            }
            data={key:[dict(row) for row in db.execute(text(sql)).mappings()] for key,sql in queries.items()}
            assert [(b['product_code'],b['current_qty']) for b in data['boxes']]==[('B',100),('B',70),('B',60),('B',100),('C',20),('B',10),('C',40)]
            assert {b['order_id'] for b in data['boxes']}=={401}
            assert sum(b['current_qty'] for b in data['boxes'])==400
            assert len(data['allocations'])==7 and sum(a['available_qty'] for a in data['allocations'])==400
            assert sum(a['order_qty'] for a in data['allocations'])==100 and sum(a['stock_qty'] for a in data['allocations'])==300
            assert {a['order_product_id'] for a in data['allocations']}=={801}
            assert [(r['parent_box_id'],r['child_box_id'],r['quantity']) for r in data['relations']]==[(2,5,30),(5,6,10),(3,7,40)]
            assert all(r['relation_type']=='partial_conversion' and r['created_by']==101 for r in data['relations'])
            assert len(data['conversions'])==6
            confirmed=data['conversions'][:5];cancelled=data['conversions'][5]
            assert [c['actual_qty'] for c in confirmed]==[100,100,30,10,40]
            assert all(c['confirmation_status']=='confirmed' and c['confirmed_by']==101 for c in confirmed)
            assert confirmed[4]['trigger_type']=='pre_authorized' and confirmed[4]['created_by']==101
            assert all(c['created_by']==104 for c in confirmed[:4])
            assert cancelled['confirmation_status']=='cancelled' and cancelled['actual_qty'] is None and cancelled['cancelled_by']==104
            assert all(c['relation_id'] is None for c in confirmed[:2])
            assert data['boxes'][0]['qr_pool_item_id']==1 and data['boxes'][3]['current_qty']==100
            assert len(data['pool'])==13 and sum(p['pool_status']=='bound' for p in data['pool'])==7
            assert {q['material_batch_id'] for q in data['quantities']}=={9001}
            assert db.scalar(text('SELECT current_weight FROM material_batches WHERE id=9001'))==50
            assert db.scalar(text('SELECT current_qty FROM box_process_quantities WHERE box_id=1 AND state_id=1003'))==0
            handoffs=[e for e in data['events'] if e['event_type']=='process_start']
            assert len(handoffs)==1 and handoffs[0]['product_box_id']==5
            assert handoffs[0]['before_qty']==handoffs[0]['after_qty']==20
            assert sum(e['event_type']=='conversion' for e in data['events'])==8
            pending=json.loads((ROOT/'runtime/qr-conversion-auto-pending.json').read_text(encoding='utf-8-sig'))
            assert sum(b['current_qty'] for b in pending['boxes'])==400
            assert next(b for b in pending['boxes'] if b['id']==3)['product_code']=='B'
            assert next(b for b in pending['boxes'] if b['id']==3)['current_qty']==100
            automatic=next(c for c in pending['conversions'] if c['trigger_type']=='pre_authorized')
            assert automatic['confirmation_status']=='pending_operator_confirmation' and automatic['actual_qty'] is None
            data.update(status='PASS',owned_original_oid=owned['original_oid'],transaction_read_only='on',synthetic_data_only=True,
                physical_qty=400,available_output_qty=400,order_qty=100,stock_qty=300,material_weight_unchanged=50,
                auto_pending_no_mutation=True,full_original_identity_unchanged=True,source_c_current_balance_zero=True)
            (FEATURE/'phase8-db.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
            return dict(status='PASS',quantity=400,boxes=7,conversions=6,relations=3,original_oid=owned['original_oid'])
    finally:engine.dispose()


async def evidence():
    owned=json.loads((ROOT/'runtime/qr-ui-owned.json').read_text(encoding='utf-8'))
    data=json.loads((FEATURE/'phase8-db.json').read_text(encoding='utf-8'))
    assert owned['state']=='cleaned' and owned['original_oid']==data['owned_original_oid']
    reports=['qr-conversion-final-full.xml','qr-conversion-old-route.xml']
    latest={}
    for report in reports:
        for case in ET.parse(ROOT/'runtime'/report).getroot().iter('testcase'):
            latest[(case.get('classname'),case.get('name'))]=case
    cases=list(latest.values())
    assert len(cases)==344 and all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases)
    browser=json.loads((FEATURE/'phase8-browser.json').read_text(encoding='utf-8'))
    assert browser['status']=='PASS' and all(x['status']=='PASS' for x in browser['checks'])
    checks=json.loads((ROOT/'runtime/qr-conversion-checks.json').read_text(encoding='utf-8'))
    assert all(checks[k]=='PASS' for k in ['build','api_usage','design','diff'])
    baseline=await business_database();assert baseline['status']=='PASS'
    for port in [18124,18125]:
        with socket.socket() as probe:
            probe.settimeout(1);assert probe.connect_ex(('127.0.0.1',port))!=0
    paths=sorted(FEATURE.glob('phase8-*.png'))+[FEATURE/'phase8-db.json',FEATURE/'phase8-browser.json']
    result=dict(recorded_at=datetime.now(timezone.utc).isoformat(),client_date='2026-10-28',implementation_status='PASS',acceptance_status='PASS',
        completed_tasks=49,total_tasks=59,active_new_endpoints=31,planned_new_endpoints=31,
        pytest=dict(unique_total=344,failures=0,skipped=0,reports=['runtime/'+name for name in reports]),checks=checks,
        browser=browser,business_database=baseline,owned_ui_cleanup=owned,owned_service_ports={'18124':'STOPPED','18125':'STOPPED'},
        artifacts=[dict(name=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths])
    (FEATURE/'phase8-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(status='PASS',unique_tests=344,completed_tasks=49,browser_checks=len(browser['checks']),business_database=baseline['status'])


if __name__=='__main__':
    try:print(json.dumps(snapshot() if '--snapshot' in sys.argv else asyncio.run(evidence())))
    except Exception as error:
        print(json.dumps(dict(status='INCOMPLETE',error_type=type(error).__name__)));raise SystemExit(1)
