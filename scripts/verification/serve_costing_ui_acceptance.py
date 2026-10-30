"""Serve real costing/part/quote routes against an owned disposable database.

Only test fixtures are writable; no business record is used for browser edits.
"""
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'backend')]
from app.api import costing, part_treatments, customers, auth, part_editor_relationships, part_editor, part_display_groups, quote_groups, materials, treatments
from app.api.deps import get_current_user
from app.database import get_db, Base
from backend.tests.pricing.test_api import database


def main():
    # Reuse the tested owned-database fixture; its finally block verifies the
    # original database OID before cleaning up only the generated test database.
    fixture=database.__wrapped__()
    sync_engine=next(fixture)
    engine=create_async_engine(sync_engine.url.set(drivername='postgresql+asyncpg'),echo=False,poolclass=NullPool)
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    with sync_engine.begin() as c:
        for name in ['part_display_group_defs','part_display_group_members','tooling_shared_relations','tooling_customer_links','tooling_steps']:
            Base.metadata.tables[name].create(c,checkfirst=True)
        c.execute(text("INSERT INTO treatment_dict (name,calc_mode,default_rate,unit,is_active,sort_order,created_at,updated_at) VALUES ('验收电镀按件','manual',0.2,'元/件',true,1,now(),now()),('验收喷涂按净重','net_weight',15,'元/kg',true,2,now(),now())"))
        c.execute(text('INSERT INTO customer_inquiries (id) VALUES (1)'))
        from app.models.quote_group import QuoteGroup, QuoteGroupItem
        c.execute(QuoteGroup.__table__.insert().values(id=1,group_no='QA-QUOTE-001',inquiry_id=1,customer_id=1,project_name='简易核算浏览器验收',material_name='QA-STEEL',material_density=10,material_unit_price=10,material_scrap_price=2,surface_treatment_fee='.2',quote_path='直接开量产模具',tooling_type='连续模'))
        c.execute(QuoteGroupItem.__table__.insert().values(id=1,quote_group_id=1,customer_part_no='QA-001',part_name='验收零件',thickness=1,width=100,pitch=20,utilization=60,product_price=1,annual_usage=1000))
    @asynccontextmanager
    async def life(app):
        yield
        await engine.dispose()
    app=FastAPI(lifespan=life)
    for module in [costing,part_treatments,customers,auth,part_editor_relationships,part_editor,part_display_groups,quote_groups,materials,treatments]:
        app.include_router(module.router,prefix='/api/v1')
    @app.get('/health')
    def health():return {'status':'healthy','mode':'synthetic costing acceptance'}
    actor=SimpleNamespace(id=1,username='acceptance',real_name='核算验收',dept='tech',position='验收',role_level=4,is_tech=True,created_at=None)
    async def session():
        async with sessions() as db:
            try:yield db
            finally:await db.rollback()
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_current_user]=lambda:actor
    try:
        print('Isolated costing browser acceptance on 127.0.0.1:8016',flush=True)
        stop_file=ROOT/'runtime'/'costing-acceptance.stop'
        stop_file.unlink(missing_ok=True)
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8016,log_level='warning'))
        def stop_when_requested():
            while not server.should_exit:
                if stop_file.exists():
                    server.should_exit=True
                    return
                time.sleep(.2)
        threading.Thread(target=stop_when_requested,daemon=True).start()
        server.run()
    finally:fixture.close()


if __name__=='__main__':main()
