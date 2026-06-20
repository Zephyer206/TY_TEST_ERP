"""Admin API endpoints for context switching and audit."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_admin
from app.schemas.admin import (
    AdminAuditLogResponse,
    ContextStatusResponse,
    ContextSwitchRequest,
    ContextSwitchResponse,
    SwitchBackResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/switch-context", response_model=ContextSwitchResponse)
async def switch_context(
    data: ContextSwitchRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ContextSwitchResponse:
    """
    Switch admin context to a target role.

    This allows admin to temporarily assume another role's perspective.
    - Generates a switch token valid for the specified duration
    - Logs the switch in admin_audit_logs
    - Hides boss-only buttons when in switched context

    Requires: role_level = 10 (admin)
    """
    require_admin(current_user)

    ip_address = request.client.host if request.client else None

    try:
        switch, token_info = await admin_service.switch_context(
            db,
            admin=current_user,
            target_role=data.target_role,
            duration_minutes=data.duration_minutes,
            reason=data.reason,
            ip_address=ip_address,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return ContextSwitchResponse(
        switch_token=token_info["switch_token"],
        switched_role_level=token_info["switched_role_level"],
        switched_role_name=token_info["switched_role_name"],
        original_role_level=token_info["original_role_level"],
        expires_at=token_info["expires_at"],
        message=f"已切换至 {token_info['switched_role_name']} 视角",
    )


@router.post("/switch-back", response_model=SwitchBackResponse)
async def switch_back(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> SwitchBackResponse:
    """
    Switch back to original admin role.

    Requires: role_level = 10 (admin) with active context switch
    """
    require_admin(current_user)

    ip_address = request.client.host if request.client else None

    try:
        switch = await admin_service.switch_back(
            db,
            admin=current_user,
            ip_address=ip_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SwitchBackResponse(
        success=True,
        original_role_level=switch.original_role_level,
        switched_back_at=switch.switched_back_at,
        message="已恢复超级管理员视角",
    )


@router.get("/context-status", response_model=ContextStatusResponse)
async def get_context_status(
    db: DbSession,
    current_user: CurrentUser,
) -> ContextStatusResponse:
    """
    Get current context status.

    Returns whether admin is in a switched context and details.
    """
    require_admin(current_user)

    status_info = await admin_service.get_context_status(db, current_user)
    return ContextStatusResponse(**status_info)


@router.get("/audit-logs", response_model=list[AdminAuditLogResponse])
async def list_audit_logs(
    db: DbSession,
    current_user: CurrentUser,
    admin_user_id: int | None = None,
    operation: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[AdminAuditLogResponse]:
    """
    List admin audit logs.

    Requires: role_level = 10 (admin)
    """
    require_admin(current_user)

    logs = await admin_service.get_audit_logs(
        db,
        admin_user_id=admin_user_id,
        operation=operation,
        skip=skip,
        limit=limit,
    )

    return [AdminAuditLogResponse.model_validate(log) for log in logs]
