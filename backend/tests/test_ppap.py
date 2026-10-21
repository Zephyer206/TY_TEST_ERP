"""Meaningful domain acceptance: private versions, permissions and snapshots."""
from datetime import date
from io import BytesIO
from types import SimpleNamespace
import copy
import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI, HTTPException
from pypdf import PdfWriter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.api import deps
from app.api.ppap import router
from app.core.config import settings
from app.models.ppap import PpapArchive, PpapFolder, PpapDocument, PpapFileVersion, PpapSubmission, PpapAuditLog
from app.services import ppap_service as service, ppap_files

QUALITY = SimpleNamespace(id=101, username='quality-test', real_name='质量验收', dept='quality', role_level=1)
VIEWER = SimpleNamespace(id=102, username='sales-test', real_name='业务验收', dept='sales', role_level=3)


def pdf():
    out = BytesIO(); writer = PdfWriter(); writer.add_blank_page(width=300, height=400); writer.write(out)
    return out.getvalue()


@pytest_asyncio.fixture
async def context(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'AUTH_DISABLED', False)
    monkeypatch.setenv('PPAP_STORAGE_ROOT', str(tmp_path / 'private'))
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    models = [PpapArchive, PpapFolder, PpapDocument, PpapFileVersion, PpapSubmission, PpapAuditLog]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: PpapArchive.metadata.create_all(c, tables=[m.__table__ for m in models]))
    actor = [QUALITY]
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async def db_override():
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        async def user_override():
            return actor[0]
        async def customer_stub(db, company, key):
            if key != ('customer:1' if company == 'tianyue' else 'workspace:1'):
                service.fail('客户范围无效')
            return 1, 'PPAP验收客户'
        async def reference_stub(db, company, cid, key):
            if key not in ({'part:1', 'part:2'} if company == 'tianyue' else {'requirement:1', 'package:1'}):
                service.fail('对象范围无效')
            kind, raw_id = key.split(':')
            return dict(key=key, source_id=int(raw_id), kind=kind, part_no='PPAP-TEST', name='测试回位簧', tooling_no='TYBU-Q0015', mold_type='成型机', drawing_version='A', composition=[{'quantity': 2, 'tianyue_internal_composition': 'TEST'}] if kind == 'package' else [])
        monkeypatch.setattr(service, 'customer', customer_stub)
        monkeypatch.setattr(service, 'resolve_link', reference_stub)
        app = FastAPI(); app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[deps.get_db] = db_override
        app.dependency_overrides[deps.get_current_user] = user_override
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://ppap.test') as client:
            yield SimpleNamespace(client=client, actor=actor, db=session, root=tmp_path / 'private')
    await engine.dispose()


def payload(company='tianyue'):
    return dict(name='TYBU-Q0015(10020531)回位簧 PPAP 成型机', customer_key='customer:1' if company == 'tianyue' else 'workspace:1', owner='质量验收', links=[dict(key='part:1' if company == 'tianyue' else 'package:1')])


async def archive(c, company='tianyue'):
    r = await c.client.post(f'/api/v1/ppap/{company}/archives', json=payload(company))
    assert r.status_code == 201, r.text
    return r.json()


def path(row, suffix=''):
    return f"/api/v1/ppap/{row['company']}/archives/{row['id']}{suffix}"


async def upload(c, row, name='资料.pdf', data=None, **extra):
    return await c.client.post(path(row, '/files'), data={'revision': str(row['revision']), **extra}, files={'file': (name, data or pdf())})


@pytest.mark.asyncio
async def test_nested_folders_revisions_and_company_isolation(context):
    c = context; row = await archive(c)
    r = await c.client.post(path(row, '/folders'), json={'revision': row['revision'], 'name': '检测报告'})
    assert r.status_code == 201
    row = r.json(); folder = row['folders'][0]['id']
    stale = await c.client.post(path(row, '/folders'), json={'revision': 1, 'name': '旧页面覆盖'})
    assert stale.status_code == 409
    r = await c.client.post(path(row, '/folders'), json={'revision': row['revision'], 'name': '材料', 'parent_id': folder})
    assert r.status_code == 201 and len(r.json()['folders']) == 2
    row = r.json()
    bad = await c.client.post(path(row, '/folders'), json={'revision': row['revision'], 'name': '../越界'})
    assert bad.status_code == 400
    other = await archive(c, 'gaibo')
    mismatch = await c.client.post(path(other, '/folders'), json={'revision': other['revision'], 'name': '越界目录', 'parent_id': folder})
    assert mismatch.status_code == 404
    assert (await c.client.get(path(row).replace('/tianyue/', '/gaibo/'))).status_code == 404


@pytest.mark.asyncio
async def test_source_versions_and_submission_snapshots_survive_updates(context):
    c = context; row = await archive(c)
    r = await upload(c, row); assert r.status_code == 201, r.text
    row = r.json(); first = row['documents'][0]['versions'][0]
    assert 'storage_key' not in first
    r = await c.client.post(path(row, '/submissions'), json={'revision': row['revision'], 'submitted_date': '2026-10-20', 'remark': '首轮'})
    assert r.status_code == 201, r.text
    row = r.json(); frozen = copy.deepcopy(row['submissions'][0]['snapshot'])
    same_name = await upload(c, row); assert same_name.status_code == 409
    # Explicit version command advances the source without changing old content.
    r = await upload(c, row, mode='version'); assert r.status_code == 201, r.text
    row = r.json(); assert len(row['documents'][0]['versions']) == 2
    assert row['submissions'][0]['snapshot'] == frozen
    assert row['submissions'][0]['status'] == 'submitted' and row['submissions'][0]['approved_date'] is None
    preview = await c.client.get(path(row, f"/versions/{first['id']}/preview"))
    assert preview.status_code == 200 and preview.content == pdf()
    assert preview.headers['cache-control'] == 'private, no-store'
    r = await c.client.post(path(row, '/submissions'), json={'revision': row['revision']})
    assert r.status_code == 201
    assert r.json()['submissions'][0]['round_no'] == 2
    assert r.json()['submissions'][1]['snapshot']['documents'][0]['version']['id'] == first['id']


@pytest.mark.asyncio
async def test_quality_only_write_and_viewer_preview(context):
    c = context; row = (await upload(c, await archive(c))).json(); v = row['documents'][0]['versions'][0]
    c.actor[0] = VIEWER
    assert (await c.client.get(path(row))).json()['can_write'] is False
    assert (await c.client.get(path(row, f"/versions/{v['id']}/preview"))).status_code == 200
    assert (await c.client.get(path(row, f"/versions/{v['id']}/original"))).status_code == 403
    assert (await c.client.post('/api/v1/ppap/tianyue/archives', json=payload())).status_code == 403
    update = payload() | {'revision': row['revision']}
    commands = [
        ('patch', path(row), update),
        ('post', path(row, '/folders'), {'revision': row['revision'], 'name': '拒绝'}),
        ('patch', path(row, '/folders/unknown'), {'revision': row['revision'], 'name': '拒绝'}),
        ('post', path(row, '/submissions'), {'revision': row['revision']}),
        ('patch', path(row, '/submissions/unknown'), {'revision': row['revision'], 'status': 'approved'}),
    ]
    for method, url, body in commands:
        assert (await c.client.request(method, url, json=body)).status_code == 403
    assert (await upload(c, row)).status_code == 403


@pytest.mark.asyncio
async def test_temporary_approval_conditions_dates_and_evidence_scope(context):
    c = context; row = (await upload(c, await archive(c))).json()
    row = (await c.client.post(path(row, '/submissions'), json={'revision': row['revision'], 'submitted_date': '2026-10-20'})).json()
    sub = row['submissions'][0]; url = path(row, f"/submissions/{sub['id']}")
    assert (await c.client.patch(url, json={'revision': row['revision'], 'status': 'temporary'})).status_code == 400
    assert (await c.client.patch(url, json={'revision': row['revision'], 'status': 'approved', 'approved_date': '2026-10-19'})).status_code == 400
    assert (await c.client.patch(url, json={'revision': row['revision'], 'status': 'temporary', 'conditions': '限制批次', 'evidence_version_id': 'foreign-version'})).status_code == 404
    r = await c.client.patch(url, json={'revision': row['revision'], 'status': 'temporary', 'conditions': '仅用于试装，限2026年11月批次', 'approved_date': '2026-10-20', 'valid_until': '2026-11-20', 'evidence_version_id': row['documents'][0]['versions'][0]['id']})
    assert r.status_code == 200, r.text
    row = r.json(); assert row['status'] == 'temporary' and row['submissions'][0]['conditions']
    assert row['submissions'][0]['snapshot'] == sub['snapshot']
    assert any(a['action'] == '登记客户反馈' for a in row['audit'])


@pytest.mark.asyncio
async def test_invalid_sources_and_cross_archive_file_ids(context):
    c = context; row = await archive(c)
    for name, data in [('假.pdf', b'%PDF-not-a-valid-document'), ('假.xlsx', b'not-a-zip'), ('不允许.txt', b'text')]:
        r = await upload(c, row, name=name, data=data)
        assert r.status_code == 400, r.text
    assert not list(c.root.rglob('*.pdf'))
    row = (await upload(c, row)).json(); other = await archive(c)
    v = row['documents'][0]['versions'][0]['id']
    assert (await c.client.get(path(other, f'/versions/{v}/preview'))).status_code == 404


@pytest.mark.asyncio
async def test_multisheet_xlsx_saved_original_and_missing_converter(context, monkeypatch):
    import openpyxl
    c = context; row = await archive(c)
    book = openpyxl.Workbook(); book.active.title = '提交清单'; book.active.merge_cells('A1:C1'); book.active['A1'] = 'PPAP资料'; book.create_sheet('尺寸报告')['A1'] = '尺寸结果'
    source = BytesIO(); book.save(source)
    row = (await upload(c, row, name='资料.xlsx', data=source.getvalue())).json()
    v = row['documents'][0]['versions'][0]
    assert v['sheets'] == ['提交清单', '尺寸报告']
    assert (await c.client.get(path(row, f"/versions/{v['id']}/original"))).content == source.getvalue()
    monkeypatch.setattr(ppap_files, 'converter_path', lambda: None)
    r = await c.client.get(path(row, f"/versions/{v['id']}/preview"))
    assert r.status_code == 503
    assert (await c.client.get(path(row, f"/versions/{v['id']}/original"))).content == source.getvalue()


@pytest.mark.asyncio
async def test_missing_bearer_is_401(monkeypatch):
    monkeypatch.setattr(settings, 'AUTH_DISABLED', False)
    with pytest.raises(HTTPException) as rejected:
        await deps.get_current_user(None, None)
    assert rejected.value.status_code == 401


@pytest.mark.asyncio
async def test_fast_cold_profile_failure_retries_once_without_losing_source(context, monkeypatch):
    original = context.root / 'source.xlsx'
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b'immutable source')
    attempts = []
    def converter(source, output):
        attempts.append(source.read_bytes())
        if len(attempts) == 1:
            service.fail('cold profile', 422)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(pdf())
    monkeypatch.setattr(ppap_files, '_convert', converter)
    result = await ppap_files.preview_path(SimpleNamespace(storage_key='source.xlsx', extension='.xlsx', sha256='fixture-cold-profile'))
    assert result.read_bytes() == pdf() and attempts == [b'immutable source'] * 2
    assert original.read_bytes() == b'immutable source'


@pytest.mark.parametrize('name', ['../逃逸', 'a/b', 'a\\b', '.', '..', 'bad\x00name'])
def test_folder_names_are_not_paths(name):
    with pytest.raises(HTTPException):
        service.safe_name(name)


def test_private_sources_cannot_be_configured_under_public_uploads(monkeypatch):
    from app.core.file_service import get_upload_root
    monkeypatch.setenv('PPAP_STORAGE_ROOT', str(get_upload_root() / 'ppap'))
    with pytest.raises(HTTPException) as rejected:
        ppap_files.storage_root()
    assert rejected.value.status_code == 503
