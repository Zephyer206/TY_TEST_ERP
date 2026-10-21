"""PPAP domain HTTP contract. All resources are scoped by company and archive."""
from typing import Literal, Optional
from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import cast, func, or_, select, Text
from sqlalchemy.dialects.postgresql import JSONB
from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.ppap import PpapArchive, PpapSubmission, PpapFileVersion
from app.schemas.ppap import ArchiveInput, ArchiveUpdate, Company, FolderInput, FolderRename, SubmissionInput, FeedbackInput
from app.services import ppap_service as service
from app.services import ppap_files as files

router = APIRouter(prefix='/ppap', tags=['PPAP'])


@router.get('')
async def ledger(db: DbSession, actor: CurrentUser, company: Company = 'tianyue', search: str = Query('', max_length=200), status: Optional[Literal['preparing', 'submitted', 'supplement', 'temporary', 'approved', 'rejected']] = None, part_id: Optional[int] = None, requirement_id: Optional[int] = None, package_id: Optional[int] = None, page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100)):
    latest = select(PpapSubmission.status).where(PpapSubmission.archive_id == PpapArchive.id).order_by(PpapSubmission.round_no.desc()).limit(1).correlate(PpapArchive).scalar_subquery()
    query = select(PpapArchive).where(PpapArchive.company == company)
    if search:
        pattern = '%' + search.replace('%', r'\%').replace('_', r'\_') + '%'
        query = query.where(or_(PpapArchive.name.ilike(pattern), PpapArchive.record_no.ilike(pattern), PpapArchive.customer_name.ilike(pattern), cast(PpapArchive.links, Text).ilike(pattern)))
    if status:
        query = query.where(func.coalesce(latest, 'preparing') == status)
    # Exact JSON key comparison avoids substring collisions (part:1 / part:10).
    for kind, value in [('part', part_id), ('requirement', requirement_id), ('package', package_id)]:
        if value is not None:
            # PostgreSQL JSON containment, keeping parameters bound.
            query = query.where(cast(PpapArchive.links, JSONB).contains([{'key': f'{kind}:{value}'}]))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(PpapArchive.updated_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = []
    for row in rows:
        sub = (await db.execute(select(PpapSubmission).where(PpapSubmission.archive_id == row.id).order_by(PpapSubmission.round_no.desc()).limit(1))).scalar_one_or_none()
        items.append(service.row_data(row) | dict(status=sub.status if sub else 'preparing', submitted_date=sub.submitted_date if sub else None, approved_date=sub.approved_date if sub else None, valid_until=sub.valid_until if sub else None, round_no=sub.round_no if sub else 0))
    return dict(items=items, total=total, can_write=service.can_write(actor), acceptance_mode=settings.AUTH_DISABLED, identity=dict(name=service.actor_name(actor), dept=actor.dept))


@router.get('/options')
async def options(db: DbSession, actor: CurrentUser, company: Company = 'tianyue', customer_key: Optional[str] = None, search: str = Query('', max_length=200)):
    return await service.options(db, company, customer_key, search)


@router.post('/{company}/archives', status_code=201)
async def create(company: Company, payload: ArchiveInput, db: DbSession, actor: CurrentUser):
    row = await service.create_archive(db, company, payload, actor)
    return await service.detail(db, row, actor)


@router.get('/{company}/archives/{archive_id}')
async def detail(company: Company, archive_id: str, db: DbSession, actor: CurrentUser):
    return await service.detail(db, await service.get_archive(db, company, archive_id), actor)


@router.patch('/{company}/archives/{archive_id}')
async def update(company: Company, archive_id: str, payload: ArchiveUpdate, db: DbSession, actor: CurrentUser):
    service.require_quality(actor)
    row = await service.get_archive(db, company, archive_id, payload.revision)
    await service.update_archive(db, row, payload, actor)
    return await service.detail(db, row, actor)


@router.post('/{company}/archives/{archive_id}/folders', status_code=201)
async def folder_create(company: Company, archive_id: str, payload: FolderInput, db: DbSession, actor: CurrentUser):
    service.require_quality(actor)
    row = await service.get_archive(db, company, archive_id, payload.revision)
    await service.save_folder(db, row, payload, actor)
    return await service.detail(db, row, actor)


@router.patch('/{company}/archives/{archive_id}/folders/{folder_id}')
async def folder_rename(company: Company, archive_id: str, folder_id: str, payload: FolderRename, db: DbSession, actor: CurrentUser):
    service.require_quality(actor)
    row = await service.get_archive(db, company, archive_id, payload.revision)
    await service.save_folder(db, row, payload, actor, folder_id)
    return await service.detail(db, row, actor)


@router.post('/{company}/archives/{archive_id}/files', status_code=201)
async def upload(company: Company, archive_id: str, db: DbSession, actor: CurrentUser, file: UploadFile = File(...), revision: int = Form(..., ge=1), folder_id: Optional[str] = Form(None), linked_key: Optional[str] = Form(None), mode: Literal['new', 'version'] = Form('new')):
    service.require_quality(actor)
    row = await service.get_archive(db, company, archive_id, revision)
    name = service.safe_name(file.filename or '', 255)
    doc = await service.prepare_document(db, row, name, folder_id, linked_key, mode)
    saved = await files.save_source(file, company, archive_id)
    try:
        version = PpapFileVersion(id=service.uid(), document_id=doc.id, version=doc.current_version, **{k: v for k, v in saved.items() if k != 'name'}, created_by=service.actor_name(actor))
        db.add(version)
        await service.audit(db, row, actor, '上传文件版本', dict(document_id=doc.id, name=doc.name, version=version.version, sha256=version.sha256))
        result = await service.detail(db, row, actor)
        # Commit here so a failed metadata transaction can remove only this
        # newly-created UUID source, never an existing document version.
        await db.commit()
        return result
    except BaseException:
        files.stored_path(saved['storage_key']).unlink(missing_ok=True)
        raise


@router.get('/{company}/archives/{archive_id}/versions/{version_id}/preview')
async def preview(company: Company, archive_id: str, version_id: str, db: DbSession, actor: CurrentUser):
    await service.get_archive(db, company, archive_id)
    version, document = await service.get_version(db, archive_id, version_id)
    path = await files.preview_path(version)
    return FileResponse(path, media_type='application/pdf', filename=document.name + ('' if version.extension == '.pdf' else '.pdf'), content_disposition_type='inline', headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/{company}/archives/{archive_id}/versions/{version_id}/original')
async def original(company: Company, archive_id: str, version_id: str, db: DbSession, actor: CurrentUser):
    service.require_quality(actor)
    await service.get_archive(db, company, archive_id)
    version, document = await service.get_version(db, archive_id, version_id)
    path = files.stored_path(version.storage_key)
    if not path.is_file():
        service.fail('原始文件不存在', 404)
    media = {'.pdf': 'application/pdf', '.xls': 'application/vnd.ms-excel', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    return FileResponse(path, media_type=media[version.extension], filename=document.name, headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.post('/{company}/archives/{archive_id}/submissions', status_code=201)
async def submit(company: Company, archive_id: str, payload: SubmissionInput, db: DbSession, actor: CurrentUser):
    service.require_quality(actor)
    row = await service.get_archive(db, company, archive_id, payload.revision)
    await service.submit(db, row, payload, actor)
    return await service.detail(db, row, actor)


@router.patch('/{company}/archives/{archive_id}/submissions/{submission_id}')
async def feedback(company: Company, archive_id: str, submission_id: str, payload: FeedbackInput, db: DbSession, actor: CurrentUser):
    service.require_quality(actor)
    row = await service.get_archive(db, company, archive_id, payload.revision)
    await service.feedback(db, row, submission_id, payload, actor)
    return await service.detail(db, row, actor)
