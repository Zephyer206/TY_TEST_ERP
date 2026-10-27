"""Loopback-only disposable API for browser testing the real frontend wrapper.

Uses synthetic identities and an owned test database. Never mount this diagnostic
application in production. Browser tokens are generated in memory, not emitted
to the terminal, saved to files, or stored in the user's normal application origin.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
import uvicorn

from app.api.product_boxes import router, qr_error_handler
from app.core.config import settings
from app.core.security import create_access_token
from app.database import get_db
from app.main import validation_exception_handler
from app.services.qr_transaction_service import QrError
from backend.tests.qr.conftest import owned_database_factory
from backend.tests.qr.service_fixtures import create_service_fixture, seed_service_fixture


PAGE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>二维码客户端接口验收 · 独立测试库</title>
<style>body{font:16px system-ui;margin:40px;max-width:900px}button{padding:10px 16px}pre{line-height:1.7;white-space:pre-wrap}</style>
<h1>二维码客户端接口验收</h1><p>独立测试数据库 · 合成账号 · 实际 frontend/src/api/productBoxes.ts</p>
<p>此页验证客户端接口模块；产品二维码池页面、系统打印和实物标签另行验收。</p>
<button id="run" disabled>运行客户端验收</button><pre id="result">正在加载实际客户端模块…</pre>
<script type="module">
import { productBoxesApi as api } from 'http://127.0.0.1:18124/src/api/productBoxes.ts';
import transport from 'http://127.0.0.1:18124/src/utils/request.ts';
const tokens = TOKENS_PLACEHOLDER;
const button = document.querySelector('#run'), result = document.querySelector('#result');
const auth = role => { transport.defaults.headers.common.Authorization = `Bearer ${tokens[role]}`; };
const check = (ok, name) => { if (!ok) throw new Error(name); result.textContent += `PASS · ${name}\n`; };
button.disabled = false; result.textContent = '已加载真实客户端模块，等待验收。';
button.onclick = async () => {
 button.disabled = true; result.textContent = '';
 const key = crypto.randomUUID();
 try {
  auth('supervisor');
  const batch = await api.generateBatch({count:2,idempotency_key:key});
  const repeat = await api.generateBatch({count:2,idempotency_key:key});
  check(batch.count===2 && batch.items[0].id===repeat.items[0].id,'唯一批量生成与同请求重放');
  const item = batch.items[0];
  auth('warehouse');
  const job = await api.printData({item_ids:[item.id],idempotency_key:crypto.randomUUID()});
  check(job.items[0].print_count===0 && job.template.columns===3 && job.template.rows===7,'打印数据不冒充打印成功');
  const bound = await api.bind({qr_payload:item.qr_payload,order_product_id:'801',idempotency_key:crypto.randomUUID()});
  check(bound.box.order_id===401 && bound.box.bound_by===103,'一框一订单及当前登录操作者');
  const scan = await api.scan(item.qr_payload);
  check(scan.box.id===bound.box.id && !scan.allowed_actions.includes('bind'),'已绑定再次扫码只返回当前框');
  const confirmation = {print_job_id:job.print_job_id,confirmed_item_ids:[item.id],idempotency_key:crypto.randomUUID()};
  const printed = await api.confirmPrint(confirmation);
  const printedAgain = await api.confirmPrint({...confirmation,idempotency_key:crypto.randomUUID()});
  check(printed.items[0].print_count===1 && printedAgain.items[0].print_count===1 && printed.items[0].bound_box_id===bound.box.id,'同作业确认仅计一次且保留框关联');
  const reprint = await api.reprint(item.id,{idempotency_key:crypto.randomUUID()});
  check(reprint.items[0].qr_payload===item.qr_payload && reprint.print_job_id!==job.print_job_id,'补打保留原二维码身份');
  auth('otherSales');
  const hidden = await api.listPool();
  let denied=false; try { await api.scan(item.qr_payload); } catch(error) { denied=error.response?.status===403; }
  check(hidden.total===0 && denied,'其他订单业务人员查询及扫码拒绝');
  result.textContent += '客户端浏览器接口验收：7项通过。产品页面与实物打印：未验收。';
 } catch(error) { result.textContent += 'FAIL · '+error.message; button.disabled=false; }
};
</script></html>"""


def main():
    factory_generator = owned_database_factory()
    factory = next(factory_generator)
    try:
        with factory() as sync_engine:
            with sync_engine.begin() as connection:
                create_service_fixture(connection)
            with sync_engine.begin() as connection:
                seed_service_fixture(connection)
            engine = create_async_engine(sync_engine.url.set(drivername="postgresql+asyncpg"), echo=False, poolclass=NullPool)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            # Process-local setting for this synthetic application, not .env.
            settings.AUTH_DISABLED = False
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            app.add_exception_handler(QrError, qr_error_handler)
            app.add_exception_handler(RequestValidationError, validation_exception_handler)
            async def database():
                async with sessions() as session:
                    try:
                        yield session
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise
            app.dependency_overrides[get_db] = database
            @app.get("/acceptance", response_class=HTMLResponse)
            async def page():
                import json
                tokens = {name: create_access_token({"sub": str(identity)})
                          for name, identity in {"supervisor":102,"warehouse":103,"otherSales":105}.items()}
                return PAGE.replace("TOKENS_PLACEHOLDER", json.dumps(tokens))
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18123, log_level="error", access_log=False))
            @app.post("/acceptance/stop")
            async def stop():
                server.should_exit = True
                return {"stopping": True}
            print("QR_CLIENT_ACCEPTANCE_READY", flush=True)
            try:
                server.run()
            finally:
                asyncio.run(engine.dispose())
    finally:
        factory_generator.close()


if __name__ == "__main__":
    main()
