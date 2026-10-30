"""Run actual Vue pages against owned synthetic DBs. Never mount in production.

The browser receives an in-memory synthetic JWT and loads the actual main.ts,
router and pages from a dedicated Vite. No live business rows/config are changed.
Only the created DB name/OID is journalled for safe interrupted-run cleanup.
"""
from __future__ import annotations

import asyncio
import argparse
from contextlib import asynccontextmanager, contextmanager
import json
from pathlib import Path
import sys
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
import re
import uvicorn

from app.api import auth, product_boxes, production, warehouse
from app.core.config import settings
from app.core.security import create_access_token
from app.database import get_db
from app.main import validation_exception_handler
from app.models import product_box as m
from app.services import product_box_service as boxes
from app.models.warehouse import Material, Supplier, MaterialBatch, BatchStatus, IQCResult
from app.services.qr_transaction_service import QrError
from backend.tests.qr.conftest import owned_database_factory
from backend.tests.qr.service_fixtures import create_service_fixture, seed_service_fixture

JOURNAL = ROOT / "runtime/qr-ui-owned.json"


@contextmanager
def resume_owned():
    owned = json.loads(JOURNAL.read_text(encoding="utf-8"))
    source = make_url(settings.DATABASE_URL).set(drivername="postgresql+psycopg2")
    name = owned.get("database")
    assert re.fullmatch(r"qrtmp_[a-f0-9]{32}", name or "") and name != source.database
    assert owned["purpose"] == "synthetic QR UI acceptance" and owned["state"] == "active"
    engine = create_engine(source.set(database=name), echo=False, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            assert connection.scalar(text("SELECT oid FROM pg_database WHERE datname=current_database()")) == owned["original_oid"]
        yield engine
    finally:
        engine.dispose()


def seed_materials(connection):
    connection.execute(Supplier.__table__.insert().values(id=701, supplier_no="QA-SUP-701", name="验收钢材供应商"))
    connection.execute(Material.__table__.insert().values(id=801, material_no="QA-STEEL-801",
        name="验收冷轧钢", grade="SPCC", thickness=0.8, width=1000, supplier_id=701))
    connection.execute(MaterialBatch.__table__.insert().values(id=9001, qr_uid="QA-OLD-DATE-9001",
        batch_no="OLD-DATE-20010101", qr_code="MAT:9001:20010101", material_id=801, supplier_id=701,
        thickness=0.8, width=1000, gross_weight=50, current_weight=50, status=BatchStatus.AVAILABLE,
        iqc_result=IQCResult.PASSED, received_at=datetime(2001,1,1), created_at=datetime(2001,1,1)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-fixture", action="store_true",
        help="Pre-issue two synthetic product labels for production-page acceptance")
    parser.add_argument("--trace-fixture", action="store_true",
        help="Add a synthetic three-step route and material ancestry for trace acceptance")
    parser.add_argument("--split-fixture", action="store_true",
        help="Seed a produced parent, compatible target order and unused child labels")
    parser.add_argument("--exception-fixture", action="store_true",
        help="Seed mismatching coils and a past simulated failed-delivery case; run the real in-app worker")
    parser.add_argument("--conversion-fixture", action="store_true", help="Seed four produced boxes, explicit B/C routes and unused child labels")
    parser.add_argument("--resume-owned", action="store_true", help="Resume only the exact active journalled database without reseeding")
    options = parser.parse_args()
    factory_generator=owned_database_factory()
    factory=next(factory_generator)
    owned=None
    try:
        with (resume_owned() if options.resume_owned else factory()) as sync_engine:
            with sync_engine.begin() as connection:
                name=connection.scalar(text("SELECT current_database()"))
                oid=connection.scalar(text("SELECT oid FROM pg_database WHERE datname=current_database()"))
                owned={"database":name,"original_oid":oid,"purpose":"synthetic QR UI acceptance","state":"active"}
                JOURNAL.parent.mkdir(exist_ok=True)
                JOURNAL.write_text(json.dumps(owned),encoding="utf-8")
                if not options.resume_owned:
                    create_service_fixture(connection)
                    seed_service_fixture(connection)
                    seed_materials(connection)
            engine=create_async_engine(sync_engine.url.set(drivername="postgresql+asyncpg"),echo=False,poolclass=NullPool)
            sessions=async_sessionmaker(engine,expire_on_commit=False)
            # Pre-issued labels only, using the real service and synthetic
            # supervisor. Browser acceptance performs actual production binds.
            async def seed_product_labels():
                from types import SimpleNamespace
                async with sessions() as db:
                    if options.conversion_fixture:
                        from backend.tests.qr.test_conversion import prepared
                        from backend.tests.qr.test_production import actor, selected
                        from app.models.production import ProductionPlan
                        from app.services import product_production_service as production_service
                        await db.execute(update(ProductionPlan).where(ProductionPlan.id==401).values(
                            material_name_snapshot="验收冷轧钢",twp_thickness=0.8,twp_width=1000))
                        current,target,labels=await prepared(db,material_batch_id=9001)
                        for index,label in enumerate(labels[:3]):
                            box=(await boxes.bind_box(db,actor(103),qr_payload=label['qr_payload'],order_product_id=801,
                                idempotency_key=f'conversion-browser-bind-{index}'))['box']
                            selected_source=await selected(db,key=f'conversion-browser-select-{index}')
                            await production_service.save_quantity(db,actor(),box_id=int(box['id']),context_id=int(selected_source['context']['id']),
                                current_qty=100,expected_version=box['version'],state_version=selected_source['state']['version'],
                                material_batch_id=9001,idempotency_key=f'conversion-browser-quantity-{index}')
                        await boxes.generate_batch(db,actor(102),count=8,idempotency_key='conversion-extra-child-labels')
                        await db.commit()
                        return
                    if options.exception_fixture:
                        from backend.tests.qr.test_exceptions_notifications import prepared
                        from backend.tests.qr.test_production import actor, selected
                        from app.models.production import ProductionPlan
                        from app.services.coil_exception_service import create_exception
                        from app.services.notification_service import dispatch_due
                        await prepared(db)
                        await boxes.generate_batch(db, actor(102), count=3, idempotency_key="exception-browser-labels")
                        db.add(MaterialBatch(id=9503, qr_uid="SECOND-BAD-COIL", material_id=850, batch_no="SECOND-BAD-COIL",
                            qr_code="MAT:9503:20261027", thickness=0.8, width=850, gross_weight=20, current_weight=20,
                            status=BatchStatus.AVAILABLE, iqc_result=IQCResult.PASSED))
                        await db.execute(update(ProductionPlan).where(ProductionPlan.id == 402).values(
                            material_name_snapshot="追溯冷轧钢", twp_thickness=0.8, twp_width=1000))
                        context = await selected(db, machine=602, assignment=502, product=803, key="failure-fixture-select")
                        failed = await create_exception(db, actor(), context_id=int(context["context"]["id"]),
                            material_batch_id=9502, continue_production=True, idempotency_key="failure-fixture-record")
                        # Replay the real retry service with a past synthetic clock.
                        # This seeds UI failure history; it is not an elapsed-time measurement.
                        baseline = await db.scalar(select(func.clock_timestamp())) - timedelta(minutes=52)
                        await db.execute(update(m.NotificationOutbox).where(
                            m.NotificationOutbox.exception_id == int(failed["exception"]["id"])).values(
                                created_at=baseline, next_retry_at=baseline))
                        async def fail_delivery(db, row):
                            raise RuntimeError("Synthetic in-app delivery failure")
                        for minute in (0, 1, 6, 21, 51):
                            await dispatch_due(db, now=baseline+timedelta(minutes=minute), sink=fail_delivery)
                        await db.commit()
                        return
                    if options.split_fixture:
                        from backend.tests.qr.test_split import prepared
                        await prepared(db, qty=100, count=8)
                        await db.commit()
                        return
                    if options.trace_fixture:
                        from backend.tests.qr.test_process_trace import route_fixture
                        await route_fixture(db)
                    await boxes.generate_batch(db, SimpleNamespace(id=102, dept="prod", role_level=2),
                        count=2, idempotency_key="production-browser-labels")
                    await db.commit()
            if not options.resume_owned and (options.production_fixture or options.trace_fixture or options.split_fixture or options.exception_fixture or options.conversion_fixture):
                asyncio.run(seed_product_labels())
            settings.AUTH_DISABLED=False
            @asynccontextmanager
            async def lifespan(app):
                stop = asyncio.Event()
                task = None
                if options.exception_fixture:
                    from app.workers.qr_notifications import run
                    task = asyncio.create_task(run(sessions, stop, interval=1))
                try:
                    yield
                finally:
                    stop.set()
                    if task:
                        await task
            app=FastAPI(lifespan=lifespan)
            for router in (auth.router, product_boxes.router, warehouse.router, production.router):
                app.include_router(router,prefix="/api/v1")
            app.add_exception_handler(QrError,product_boxes.qr_error_handler)
            app.add_exception_handler(RequestValidationError,validation_exception_handler)
            async def database():
                async with sessions() as session:
                    try:
                        yield session
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise
            app.dependency_overrides[get_db]=database

            def html(actor,path):
                token=create_access_token({"sub":str(actor)})
                return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Zephyr ERP · QR隔离验收</title><body><div id="app"></div><script type="module">
import transport from 'http://127.0.0.1:18124/src/utils/request.ts';
transport.defaults.headers.common.Authorization='Bearer {token}';
history.replaceState(null,'',{json.dumps(path)});
await import('http://127.0.0.1:18124/src/main.ts');
</script></body></html>'''
            @app.get("/acceptance/{actor}",response_class=HTMLResponse)
            async def bootstrap(actor:int,path:str="/product-box-qr"):
                if actor not in (101,102,103,104,105,107) or path not in ("/product-box-qr","/material-qr","/product-box-production","/product-box-trace","/product-box-notifications"):
                    raise HTTPException(400,"Unsupported synthetic identity or page")
                response=HTMLResponse(html(actor,path))
                response.set_cookie("qr_ui_actor",str(actor),httponly=True,samesite="strict")
                return response
            @app.get("/product-box-qr",response_class=HTMLResponse)
            @app.get("/material-qr",response_class=HTMLResponse)
            @app.get("/product-box-production",response_class=HTMLResponse)
            @app.get("/product-box-trace",response_class=HTMLResponse)
            @app.get("/product-box-notifications",response_class=HTMLResponse)
            async def reload_page(request:Request):
                actor=request.cookies.get("qr_ui_actor","102")
                if actor not in {"101","102","103","104","105","107"}: actor="102"
                return HTMLResponse(html(int(actor),request.url.path))
            @app.get("/acceptance-summary")
            async def summary():
                async with sessions() as db:
                    return {"pool_count":await db.scalar(select(func.count()).select_from(m.ProductQrPoolItem)),
                        "pool_items":[dict(row) for row in (await db.execute(select(m.ProductQrPoolItem.id,m.ProductQrPoolItem.qr_payload,m.ProductQrPoolItem.pool_status))).mappings()],
                        "confirmed_items":await db.scalar(select(func.count()).select_from(m.QrPrintConfirmation)),
                        "total_print_count":await db.scalar(select(func.coalesce(func.sum(m.ProductQrPoolItem.print_count),0))),
                        "exceptions":[dict(row) for row in (await db.execute(select(m.CoilSpecException.id,m.CoilSpecException.order_id,
                            m.CoilSpecException.state_id,m.CoilSpecException.status,m.CoilSpecException.resolution,m.CoilSpecException.version,
                            m.CoilSpecException.confirmed_by,m.CoilSpecException.released_by))).mappings()],
                        "conversions":[dict(row) for row in (await db.execute(select(m.ProductConversionRecord.id,m.ProductConversionRecord.product_box_id,
                            m.ProductConversionRecord.source_product_code,m.ProductConversionRecord.target_product_code,
                            m.ProductConversionRecord.confirmation_status,m.ProductConversionRecord.actual_qty,m.ProductConversionRecord.trigger_type,
                            m.ProductConversionRecord.relation_id,m.ProductConversionRecord.created_by,m.ProductConversionRecord.confirmed_by,
                            m.ProductConversionRecord.cancelled_by))).mappings()],
                        "deliveries":[dict(row) for row in (await db.execute(select(m.NotificationOutbox.id,m.NotificationOutbox.exception_id,
                            m.NotificationOutbox.recipient_user_id,m.NotificationOutbox.status,m.NotificationOutbox.attempts,m.NotificationOutbox.retry_batch,m.NotificationOutbox.last_error))).mappings()],
                        "boxes":[dict(row) for row in (await db.execute(select(m.ProductBox.id,m.ProductBox.order_id,m.ProductBox.bound_by,m.ProductBox.current_qty,m.ProductBox.version,m.ProductBox.product_code))).mappings()],
                        "production_states":[dict(row) for row in (await db.execute(select(m.MachineOrderProcessState.id,m.MachineOrderProcessState.production_status,m.MachineOrderProcessState.version,m.MachineOrderProcessState.completed_by))).mappings()],
                        "allocations":[dict(row) for row in (await db.execute(select(m.ProductOutputAllocation.source_quantity_id,m.ProductOutputAllocation.available_qty,m.ProductOutputAllocation.order_qty,m.ProductOutputAllocation.stock_qty,m.ProductOutputAllocation.assigned_by))).mappings()],
                        "material_batches":[dict(row) for row in (await db.execute(select(MaterialBatch.id,MaterialBatch.batch_no,MaterialBatch.qr_code,MaterialBatch.current_weight,MaterialBatch.parent_batch_id))).mappings()]}
            server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=18125,access_log=False,log_level="error"))
            @app.post("/acceptance-stop")
            async def stop():
                server.should_exit=True
                return {"stopping":True}
            print("QR_UI_ACCEPTANCE_READY",flush=True)
            try: server.run()
            finally: asyncio.run(engine.dispose())
        owned["state"]="active" if options.resume_owned else "cleaned"
        JOURNAL.write_text(json.dumps(owned),encoding="utf-8")
    finally:
        factory_generator.close()


if __name__ == "__main__":
    try: main()
    except Exception as error:
        print("QR_UI_ACCEPTANCE_FAILED:"+type(error).__name__,flush=True)
        sys.exit(1)
