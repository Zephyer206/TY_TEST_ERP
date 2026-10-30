"""One canonical requirements write service for both part and costing screens."""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from app.api.deps import CurrentUser, DbSession, require_role
from app.core.events import audit_event
from app.models.audit import AuditAction
from app.models.part import Part
from app.schemas.costing import SurfaceTreatment, TreatmentSave

router = APIRouter(prefix='/parts', tags=['Part Surface Treatment'])


def treatment_of(part):
    return SurfaceTreatment.model_validate(part.surface_treatment or {}).model_dump(mode='json')


@router.get('/{part_id}/surface-treatment')
async def get_treatment(part_id: int, db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    part = await db.get(Part, part_id)
    if not part or part.is_deleted:
        raise HTTPException(404, '零件不存在')
    return dict(part_id=part.id, surface_treatment=treatment_of(part))


@router.patch('/{part_id}/surface-treatment')
async def save_treatment(part_id: int, request: TreatmentSave, db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    part = (await db.execute(select(Part).where(Part.id == part_id).with_for_update())).scalar_one_or_none()
    if not part or part.is_deleted:
        raise HTTPException(404, '零件不存在')
    old = treatment_of(part)
    incoming = request.surface_treatment.model_dump(mode='json')
    # Identical retried saves are harmless, even after the successful first response was lost.
    if old['status'] == incoming['status'] and old['items'] == incoming['items']:
        return dict(part_id=part.id, surface_treatment=old)
    if request.expected_revision != old['revision']:
        raise HTTPException(409, detail=dict(message='表面处理已被更新，本地输入已保留，请核对最新资料', current=old))
    incoming['revision'] = old['revision'] + 1
    part.surface_treatment = incoming
    part.updated_at = datetime.utcnow()
    await audit_event(db, AuditAction.UPDATE, 'part', part.id, current_user.id,
        getattr(current_user, 'username', None), old_values={'surface_treatment': old},
        new_values={'surface_treatment': incoming}, extra_data={'scope': '表面处理', 'source': request.source})
    await db.commit()
    return dict(part_id=part.id, surface_treatment=incoming)
