"""Admin and context switch management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.admin import AdminContextSwitch
from app.schemas.admin import (
    AdminContextInfo,
    ContextSwitchRecordResponse,
    DeptRoleMapping,
    SESSION_EXPIRY_SECONDS,
    SwitchBackResponse,
    SwitchContextRequest,
    SwitchContextResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])


def _switch_to_response(
    context_switch: AdminContextSwitch,
) -> SwitchContextResponse:
    """Convert AdminContextSwitch to response."""
    return SwitchContextResponse(
        success=True,
        message=f"Switched to {context_switch.switched_to_dept} perspective",
        original_role_level=context_switch.original_role_level,
        original_dept=context_switch.original_dept,
        switched_to_role_level=context_switch.switched_to_role_level,
        switched_to_dept=context_switch.switched_to_dept,
        session_key=context_switch.session_key,
        expires_in_seconds=SESSION_EXPIRY_SECONDS,
    )


def _history_to_response(
    context_switch: AdminContextSwitch,
) -> ContextSwitchRecordResponse:
    """Convert AdminContextSwitch to history response."""
    return ContextSwitchRecordResponse(
        id=context_switch.id,
        user_id=context_switch.user_id,
        original_role_level=context_switch.original_role_level,
        original_dept=context_switch.original_dept,
        switched_to_role_level=context_switch.switched_to_role_level,
        switched_to_dept=context_switch.switched_to_dept,
        switch_type=context_switch.switch_type,
        is_active=context_switch.is_active,
        switched_at=context_switch.switched_at,
        switched_back_at=context_switch.switched_back_at,
    )


@router.post("/switch-context", response_model=SwitchContextResponse)
async def switch_context(
    data: SwitchContextRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> SwitchContextResponse:
    """Switch admin context to another department perspective.

    This endpoint allows super admins (LV4) to temporarily view the system
    from another department's perspective. When switched, the admin's
    effective role will be changed to the target department's role level,
    and boss-only buttons (LV3) will be hidden.

    The switch expires after 1 hour and must be explicitly switched back.
    """
    try:
        context_switch, _ = await admin_service.switch_context(
            db, current_user, data.department
        )
        return _switch_to_response(context_switch)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/switch-back", response_model=SwitchBackResponse)
async def switch_back(
    db: DbSession,
    current_user: CurrentUser,
    session_key: Optional[str] = None,
) -> SwitchBackResponse:
    """Switch back to admin perspective.

    Restores the admin's original role level and perspective.
    """
    try:
        context_switch = await admin_service.switch_back(
            db, current_user, session_key
        )
        return SwitchBackResponse(
            success=True,
            message="Switched back to admin perspective",
            restored_role_level=context_switch.original_role_level,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/context-info", response_model=AdminContextInfo)
async def get_context_info(
    db: DbSession,
    current_user: CurrentUser,
) -> AdminContextInfo:
    """Get current context information.

    Returns the effective role and context switch status for the current user.
    """
    context_switch = await admin_service.get_active_context_switch(db, current_user.id)
    effective = admin_service.get_effective_role(current_user, context_switch)

    return AdminContextInfo(
        user_id=current_user.id,
        original_role_level=effective["original_role_level"],
        original_dept=effective["original_dept"],
        current_role_level=effective["role_level"],
        current_dept=effective["dept"],
        is_switched=effective["is_switched"],
        switch_type=effective.get("switch_type"),
        switched_at=effective.get("switched_at"),
        expires_at=effective.get("expires_at"),
    )


@router.get("/departments", response_model=list[DeptRoleMapping])
async def list_departments() -> list[DeptRoleMapping]:
    """List available departments for context switching.

    Returns all departments that can be switched to with their role levels.
    """
    from app.schemas.admin import DEPT_ROLE_MAPPINGS

    return [
        DeptRoleMapping(department=dept, **mapping)
        for dept, mapping in DEPT_ROLE_MAPPINGS.items()
    ]


@router.get("/history", response_model=list[ContextSwitchRecordResponse])
async def get_context_switch_history(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
) -> list[ContextSwitchRecordResponse]:
    """Get context switch history for the current admin."""
    # Only admins can see their own history
    if current_user.role_level < 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can view context switch history",
        )

    records = await admin_service.get_context_switch_history(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return [_history_to_response(r) for r in records]
