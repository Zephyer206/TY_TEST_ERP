"""Private immutable PPAP sources and local, time-bounded spreadsheet previews."""
import asyncio
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from fastapi import HTTPException
from app.core.config import settings
from app.core.file_service import get_upload_root
from app.services.ppap_service import fail, safe_name, uid

MAX_BYTES = 100 * 1024 * 1024
PROJECT = Path(__file__).resolve().parents[3]


def storage_root():
    root = Path(os.environ.get('PPAP_STORAGE_ROOT') or settings.PPAP_STORAGE_ROOT or PROJECT / 'backend' / 'private' / 'ppap').resolve()
    public_roots = [get_upload_root().resolve(), (PROJECT / 'static').resolve(), (PROJECT / 'backend/static').resolve(), (PROJECT / 'frontend/public').resolve(), (PROJECT / 'frontend/dist').resolve()]
    if any(root.is_relative_to(public) for public in public_roots):
        fail('PPAP存储目录必须位于公开文件目录之外，请联系管理员调整配置', 503)
    return root


def stored_path(key):
    root = storage_root()
    target = (root / key).resolve()
    if not target.is_relative_to(root):
        fail('文件存储路径无效')
    return target


def validate_source(path, extension):
    head = path.open('rb').read(8)
    if extension == '.pdf':
        if not head.startswith(b'%PDF-'):
            fail('文件内容不是有效PDF')
        try:
            from pypdf import PdfReader
            book = PdfReader(str(path), strict=True)
            if book.is_encrypted or not len(book.pages):
                fail('PDF已加密或没有可查看的页面')
        except HTTPException:
            raise
        except Exception:
            fail('PDF文件损坏或无法读取')
        return []
    if extension == '.xls':
        if not head.startswith(bytes.fromhex('D0CF11E0A1B11AE1')):
            fail('文件内容不是有效XLS')
        try:
            import xlrd
            book = xlrd.open_workbook(str(path), on_demand=True)
            sheets = book.sheet_names()
            book.release_resources()
            return sheets
        except Exception:
            fail('XLS文件损坏、加密或无法读取')
    if extension == '.xlsx':
        try:
            with zipfile.ZipFile(path) as book:
                members = book.infolist()
                if len(members) > 10000 or sum(m.file_size for m in members) > 500 * 1024 * 1024:
                    fail('Excel解压体积过大')
                # Read only workbook metadata; never execute macros or links.
                meta = book.getinfo('xl/workbook.xml')
                if meta.file_size > 4 * 1024 * 1024:
                    fail('Excel工作表元数据过大')
                root = ElementTree.fromstring(book.read(meta))
                return [s.attrib['name'] for s in root.findall('{*}sheets/{*}sheet')]
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
            fail('XLSX文件损坏、加密或格式不正确')
    fail('仅支持PDF、XLS、XLSX文件')


async def save_source(upload, company, archive_id):
    name = safe_name(upload.filename or '', 255)
    extension = Path(name).suffix.lower()
    if extension not in {'.pdf', '.xls', '.xlsx'}:
        fail('仅支持PDF、XLS、XLSX文件')
    key = f'{company}/{archive_id}/{uid()}{extension}'
    target = stored_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    total, digest = 0, hashlib.sha256()
    try:
        with target.open('xb') as stream:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    fail('单个文件不能超过100MB', 413)
                stream.write(chunk)
                digest.update(chunk)
        if not total:
            fail('不能上传空文件')
        sheets = await asyncio.to_thread(validate_source, target, extension)
        return dict(name=name, storage_key=key, sha256=digest.hexdigest(), size=total, extension=extension, sheets=sheets)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def converter_path():
    configured = os.environ.get('PPAP_SOFFICE') or settings.PPAP_SOFFICE
    if configured:
        return Path(configured) if Path(configured).is_file() else None
    local = PROJECT / 'runtime' / 'tools' / 'libreoffice'
    candidates = [local / 'program' / 'soffice.com', Path('C:/Program Files/LibreOffice/program/soffice.com')]
    executable = shutil.which('soffice')
    if executable:
        candidates.append(Path(executable))
    for p in candidates:
        if p.is_file():
            return p
    if local.exists():
        return next(local.rglob('soffice.com'), None)
    return None


_conversion_slots = asyncio.Semaphore(2)


def _convert(source, output):
    executable = converter_path()
    if not executable:
        fail('Excel预览服务尚未配置，请联系管理员配置LibreOffice后重试', 503)
    # Unique job/profile avoids interference with open applications and stale
    # office locks. The profile disables macros and document link updates.
    with tempfile.TemporaryDirectory(prefix='ppap-preview-') as temporary:
        work = Path(temporary)
        profile = work / 'profile'
        (profile / 'user').mkdir(parents=True)
        (profile / 'user' / 'registrymodifications.xcu').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Content/Update"><prop oor:name="Mode" oor:op="fuse"><value>0</value></prop></item>
</oor:items>''', encoding='utf-8')
        staged = work / ('source' + source.suffix)
        shutil.copyfile(source, staged)
        # Every sheet is included, including content outside print ranges.
        pdf_filter = 'pdf:calc_pdf_Export:{"SinglePageSheets":{"type":"boolean","value":"true"},"UseLosslessCompression":{"type":"boolean","value":"true"},"Magnification":{"type":"long","value":"2"}}'
        arguments = [str(executable), '-env:UserInstallation=' + profile.as_uri(), '--headless', '--nologo', '--nodefault', '--norestore', '--convert-to', pdf_filter, '--outdir', str(work), str(staged)]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
        try:
            process.communicate(timeout=90)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, creationflags=creationflags)
            else:
                process.kill()
            process.communicate()
            fail('Excel预览转换超时，请检查文档后重试', 503)
        generated = work / 'source.pdf'
        if not generated.is_file() or not generated.read_bytes().startswith(b'%PDF-'):
            fail('Excel无法生成预览，请检查是否加密或文件损坏', 422)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary_output = output.with_name(uid() + '.pdf')
        shutil.copyfile(generated, temporary_output)
        os.replace(temporary_output, output)


async def preview_path(version):
    source = stored_path(version.storage_key)
    if not source.is_file():
        fail('原始文件不存在，请联系质量部门核对存储', 404)
    if version.extension == '.pdf':
        return source
    output = storage_root() / 'previews' / (version.sha256 + '-sheets-v1.pdf')
    if not output.exists():
        async with _conversion_slots:
            if not output.exists():
                started = time.monotonic()
                try:
                    await asyncio.to_thread(_convert, source, output)
                except HTTPException as error:
                    # Office can exit without a result during a cold-profile
                    # initialization. Retry one fast failure in a new profile,
                    # keeping the worst-case job within the client timeout.
                    if error.status_code != 422 or time.monotonic() - started >= 20:
                        raise
                    await asyncio.to_thread(_convert, source, output)
    return output
