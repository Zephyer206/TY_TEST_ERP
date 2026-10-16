"""Part editor API - transactional PATCH endpoint with optimistic locking."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.events import audit_event
from app.models.audit import AuditAction, AuditLog
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.schemas.part_editor import (
    PartEditorConflictDetail,
    PartEditorConflictResponse,
    PartEditorUpdateRequest,
    PartEditorUpdateResponse,
)

router = APIRouter(prefix="/parts", tags=["Part Editor"])


@router.get("/{part_id}/editor/history")
async def get_part_editor_history(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[dict]:
    """Return the user-facing edit trail for a part without exposing internal IDs."""
    if current_user.role_level < 2:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Minimum role level required: LV2")

    part = await db.get(Part, part_id)
    if not part or part.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Part {part_id} not found")

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == "part", AuditLog.entity_id == part_id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    history = [
        {
            "created_at": log.created_at.isoformat(),
            "username": log.username or "系统",
            "action": "修改" if log.action == AuditAction.UPDATE else log.action.value,
            "summary": log.changes_summary or (log.extra_data or {}).get("summary") or "已更新零件档案",
        }
        for log in result.scalars().all()
    ]

    # Imported records predate editor audit logging. Keep only meaningful lifecycle facts.
    if not history and part.created_at:
        history.append({
            "created_at": part.created_at.isoformat(),
            "username": "系统",
            "action": "建档",
            "summary": "零件档案已建立",
        })
        if part.updated_at and part.updated_at != part.created_at:
            history.insert(0, {
                "created_at": part.updated_at.isoformat(),
                "username": "系统",
                "action": "更新",
                "summary": "历史记录未保留字段级变更",
            })
    return history


def _build_editor_response(
    part: Part,
    alias: Optional[PartCustomerAlias] = None,
) -> PartEditorUpdateResponse:
    """Build response from Part model."""
    return PartEditorUpdateResponse(
        id=part.id,
        part_name=part.internal_name,
        customer_id=alias.customer_id if alias else None,
        customer_part_no=alias.customer_part_no if alias else None,
        customer_part_name=alias.customer_part_name if alias else None,
        vehicle_model=part.vehicle_model,
        material_name=part.material_name,
        material_id=part.material_id,
        drawing_url=part.drawing_url,
        spec_info=part.spec_info,
        spec_twph=part.spec_twph,
        thickness=part.thickness,
        width=part.width,
        pitch=part.pitch,
        height=part.height,
        gross_weight=part.gross_weight,
        net_weight=part.net_weight,
        part_position=part.part_position,
        part_status=part.part_status,
        remark=part.remark,
        press_tonnage=part.press_tonnage,
        ppap_no=part.ppap_no,
        stock_pcs=part.stock_pcs,
        is_deleted=part.is_deleted,
        created_at=part.created_at,
        updated_at=part.updated_at,
        version=part.version,
    )


def _detect_conflicts(
    part: Part,
    client_timestamp: datetime,
    request_data: dict,
) -> list[PartEditorConflictDetail]:
    """Detect field-level conflicts between client and server state.

    Returns a list of conflicting fields where:
    - Client intended to update the field
    - Server value differs from what client expected
    """
    conflicts = []

    # Map of request field names to Part model attribute names
    field_mapping = {
        'internal_name': 'internal_name',
        # Customer alias fields are handled through part_customer_aliases.
        'vehicle_model': 'vehicle_model',
        'material_name': 'material_name',
        'drawing_url': 'drawing_url',
        'gross_weight': 'gross_weight',
        'net_weight': 'net_weight',
        'part_position': 'part_position',
        'part_status': 'part_status',
        'remark': 'remark',
        'press_tonnage': 'press_tonnage',
        'ppap_no': 'ppap_no',
    }

    for request_field, model_attr in field_mapping.items():
        if request_field not in request_data:
            continue  # Field not in request, no conflict

        client_value = request_data[request_field]
        server_value = getattr(part, model_attr)

        # Normalize for comparison
        if client_value is not None and server_value is not None:
            # Convert Decimal to str for comparison
            cv = str(client_value) if hasattr(client_value, '__float__') else client_value
            sv = str(server_value) if hasattr(server_value, '__float__') else server_value
            if cv == sv:
                continue
        elif client_value is None and server_value is None:
            continue

        # Conflict detected
        conflicts.append(PartEditorConflictDetail(
            field=request_field,
            client_value=str(client_value) if client_value is not None else None,
            server_value=str(server_value) if server_value is not None else None,
            server_updated_at=part.updated_at or part.created_at,
            server_updated_by=None,  # TODO: add updated_by tracking
        ))

    return conflicts


@router.patch("/{part_id}/editor", response_model=PartEditorUpdateResponse)
async def update_part_editor(
    part_id: int,
    request: PartEditorUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PartEditorUpdateResponse:
    """Transactional part editor update with optimistic locking.

    This endpoint provides atomic updates for all editable Part fields with
    optimistic concurrency control using updated_at timestamp.

    Authorization: Requires role level >= 2 (LV2+)

    Optimistic Locking:
    - Client must provide the last known updated_at timestamp
    - If server timestamp differs, returns 409 Conflict with field-level diff
    - Client must resolve conflicts and retry with latest timestamp

    Atomicity:
    - All updates succeed or all fail (database transaction)
    - Foreign key violations return 400 Bad Request
    - Unique constraint violations return 409 Conflict

    Protected Fields:
    - id: immutable identity
    - created_at: immutable creation timestamp
    - updated_at: system-managed, set to current UTC time
    - stock_pcs: managed by stock/production accounting
    - nomination_*: managed by nomination workflow
    - is_deleted: soft delete flag, not editable here
    - price_snapshot: managed by pricing system

    Returns:
    - 200: Successfully updated part
    - 400: Validation error or foreign key violation
    - 403: Insufficient permissions
    - 404: Part not found
    - 409: Optimistic lock conflict (with conflict details)
    """
    # Authorization check
    if current_user.role_level < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Minimum role level required: LV2, you have LV{current_user.role_level}"
        )

    # Fetch current part
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part with id {part_id} not found"
        )

    if part.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part with id {part_id} has been deleted"
        )

    alias_result = await db.execute(
        select(PartCustomerAlias)
        .where(
            PartCustomerAlias.part_id == part.id,
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.data_quality_status == "approved",
        )
        .order_by(PartCustomerAlias.id)
        .limit(1)
    )
    current_alias = alias_result.scalar_one_or_none()

    # Optimistic lock check: compare timestamps
    # Use microsecond-truncated comparison to handle precision differences
    server_ts = part.updated_at or part.created_at
    client_ts = request.updated_at

    if server_ts is None:
        # Fallback for missing timestamp (should not happen in normal operation)
        server_ts = datetime.utcnow()

    # Truncate to seconds for comparison (avoid microsecond precision issues)
    server_ts_sec = server_ts.replace(microsecond=0)
    client_ts_sec = client_ts.replace(microsecond=0)

    if server_ts_sec != client_ts_sec:
        # Optimistic lock failure - detect conflicts
        request_dict = request.model_dump(exclude={'updated_at'}, exclude_unset=True)
        conflicts = _detect_conflicts(part, client_ts, request_dict)

        conflict_response = PartEditorConflictResponse(
            detail="Part was modified by another user. Review conflicts and retry.",
            conflict_type="optimistic_lock",
            client_timestamp=client_ts,
            server_timestamp=server_ts,
            conflicts=conflicts,
            current_part=_build_editor_response(part, current_alias),
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict_response.model_dump(),
        )

    # Apply updates atomically
    update_data = request.model_dump(
        exclude={'updated_at'},
        exclude_unset=True
    )
    old_values = jsonable_encoder({
        field: getattr(part, field)
        for field in update_data
        if hasattr(part, field)
    })
    new_values = jsonable_encoder(update_data)

    try:
        # Apply all field updates
        for field, value in update_data.items():
            if field in {"customer_id", "customer_part_no", "customer_part_name"}:
                continue
            setattr(part, field, value)

        if request.customer_id and request.customer_part_no:
            from app.services.part_identity_service import upsert_part_alias
            current_alias = await upsert_part_alias(
                db,
                part_id=part.id,
                customer_id=request.customer_id,
                customer_part_no=request.customer_part_no,
                customer_part_name=request.customer_part_name,
                vehicle_model=request.vehicle_model,
            )

        # Update timestamp (system-managed)
        part.updated_at = datetime.utcnow()
        await audit_event(
            db=db,
            action=AuditAction.UPDATE,
            entity_type="part",
            entity_id=part.id,
            user_id=current_user.id,
            username=getattr(current_user, "username", None),
            old_values=old_values,
            new_values=new_values,
            extra_data={"scope": "主信息"},
        )

        # Commit transaction
        await db.commit()
        await db.refresh(part)

    except IntegrityError as e:
        await db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)

        # Check for foreign key violations
        if 'foreign key' in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Foreign key constraint violation: {error_msg}"
            )

        # Check for unique constraint violations
        if 'unique' in error_msg.lower() or 'duplicate' in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unique constraint violation: {error_msg}"
            )

        # Generic database error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {error_msg}"
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during update: {str(e)}"
        )

    return _build_editor_response(part, current_alias)
