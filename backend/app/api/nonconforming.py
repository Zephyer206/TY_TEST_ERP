from fastapi import APIRouter
from app.api.deps import CurrentUser, DbSession
from app.schemas.nonconforming import Company, DefectDraft, MoldDraft, RecordAction, WorkspaceResponse
from app.services import nonconforming_service as service

router = APIRouter(prefix='/nonconforming', tags=['Nonconforming'])

@router.get('', response_model=WorkspaceResponse)
async def list_workspace(db: DbSession, current_user: CurrentUser, company: Company = 'tianyue'):
    return await service.workspace(db, company, current_user)

@router.post('/{company}/records', response_model=WorkspaceResponse, status_code=201)
async def create_record(company: Company, draft: DefectDraft, db: DbSession, current_user: CurrentUser):
    return await service.create_record(db, company, draft.model_dump(), current_user)

@router.post('/{company}/records/{record_id}/actions', response_model=WorkspaceResponse)
async def execute_action(company: Company, record_id: str, command: RecordAction, db: DbSession, current_user: CurrentUser):
    return await service.execute_action(db, company, record_id, command, current_user)

@router.post('/{company}/molds', response_model=WorkspaceResponse)
async def save_mold(company: Company, draft: MoldDraft, db: DbSession, current_user: CurrentUser):
    return await service.save_mold(db, company, draft, current_user)
