"""Business logic for admin operations including context switching."""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminAuditLog, AdminContextSwitch, SwitchTargetRole
from app.models.user import User


# Role level mapping for switch targets
ROLE_LEVEL_MAP = {
    SwitchTargetRole.OPERATOR: (1, "操作工"),
    SwitchTargetRole.MOLD_ENGINEER: (2, "模具工程师"),
    SwitchTargetRole.SUPERVISOR: (3, "组长/主管"),
    SwitchTargetRole.DESIGN_ENGINEER: (4, "设计工程师"),
    SwitchTargetRole.SALES_MANAGER: (5, "业务经理"),
}


def generate_switch_token() -> str:
    """Generate a secure token for context switch."""
    return secrets.token_urlsafe(32)


def generate_log_no() -> str:
    """Generate a unique log number."""
    now = datetime.utcnow()
    suffix = secrets.token_hex(3).upper()[:6]
    return f"AUD-{now.strftime('%Y%m%d')}-{suffix}"


async def switch_context(
    db: AsyncSession,
    admin: User,
    target_role: SwitchTargetRole,
    duration_minutes: int,
    reason: str,
    ip_address: Optional[str] = None,
) -> tuple[AdminContextSwitch, dict]:
    """
    Switch admin context to a target role.

    Returns the context switch record and token info.
    """
    # Validate admin has role_level 10
    if admin.role_level != 10:
        raise PermissionError("Only admin (role_level=10) can switch context")

    # Get target role info
    role_level, role_name = ROLE_LEVEL_MAP[target_role]

    # Deactivate any existing active switches for this admin
    existing = await db.execute(
        select(AdminContextSwitch).where(
            AdminContextSwitch.admin_user_id == admin.id,
            AdminContextSwitch.is_active == True,
        )
    )
    for old_switch in existing.scalars().all():
        old_switch.is_active = False
        old_switch.switched_back_at = datetime.utcnow()

    # Create new switch
    switch_token = generate_switch_token()
    expires_at = datetime.utcnow() + timedelta(minutes=duration_minutes)

    switch = AdminContextSwitch(
        admin_user_id=admin.id,
        original_role_level=admin.role_level,
        switched_role_level=role_level,
        switched_role_name=role_name,
        switch_token=switch_token,
        is_active=True,
        switched_at=datetime.utcnow(),
        expires_at=expires_at,
        reason=reason,
        ip_address=ip_address,
    )
    db.add(switch)
    await db.commit()
    await db.refresh(switch)

    # Create audit log
    await _create_audit_log(
        db,
        admin_id=admin.id,
        operation="CONTEXT_SWITCH",
        details={
            "target_role_level": role_level,
            "target_role_name": role_name,
            "duration_minutes": duration_minutes,
            "reason": reason,
        },
        context_switch_id=switch.id,
        ip_address=ip_address,
    )

    return switch, {
        "switch_token": switch_token,
        "switched_role_level": role_level,
        "switched_role_name": role_name,
        "original_role_level": admin.role_level,
        "expires_at": expires_at,
    }


async def switch_back(
    db: AsyncSession,
    admin: User,
    ip_address: Optional[str] = None,
) -> AdminContextSwitch:
    """Switch back to original admin role."""
    # Find active switch for this admin
    result = await db.execute(
        select(AdminContextSwitch).where(
            AdminContextSwitch.admin_user_id == admin.id,
            AdminContextSwitch.is_active == True,
        )
    )
    switch = result.scalar_one_or_none()

    if not switch:
        raise ValueError("No active context switch found")

    # Deactivate switch
    switch.is_active = False
    switch.switched_back_at = datetime.utcnow()

    await db.commit()
    await db.refresh(switch)

    # Create audit log
    await _create_audit_log(
        db,
        admin_id=admin.id,
        operation="CONTEXT_SWITCH_BACK",
        details={
            "original_role_level": switch.original_role_level,
            "switched_role_level": switch.switched_role_level,
        },
        context_switch_id=switch.id,
        ip_address=ip_address,
    )

    return switch


async def get_active_switch(
    db: AsyncSession,
    admin_user_id: int,
) -> Optional[AdminContextSwitch]:
    """Get active context switch for an admin."""
    result = await db.execute(
        select(AdminContextSwitch).where(
            AdminContextSwitch.admin_user_id == admin_user_id,
            AdminContextSwitch.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def get_context_status(
    db: AsyncSession,
    admin: User,
) -> dict:
    """Get current context status for admin."""
    switch = await get_active_switch(db, admin.id)

    if not switch:
        return {
            "is_switched": False,
            "current_role_level": admin.role_level,
            "current_role_name": _get_role_name(admin.role_level),
        }

    remaining = 0
    if switch.expires_at:
        delta = switch.expires_at - datetime.utcnow()
        remaining = max(0, int(delta.total_seconds() / 60))

    return {
        "is_switched": True,
        "current_role_level": switch.switched_role_level,
        "current_role_name": switch.switched_role_name,
        "original_role_level": switch.original_role_level,
        "original_role_name": _get_role_name(switch.original_role_level),
        "switched_at": switch.switched_at,
        "expires_at": switch.expires_at,
        "remaining_minutes": remaining,
    }


def get_effective_role(
    db: AsyncSession,
    admin: User,
) -> tuple[int, bool]:
    """
    Get effective role level for a user.

    Returns (role_level, is_switched_context).
    If admin has active switch, returns switched role level.
    """
    if admin.role_level != 10:
        return admin.role_level, False

    # For admin, check if there's an active switch
    # This is a simplified sync version - in production, use Redis cache
    # For now, we rely on the token-based approach in the API layer
    return admin.role_level, False


def validate_switch_token(
    db: AsyncSession,
    token: str,
) -> Optional[AdminContextSwitch]:
    """Validate a switch token and return the context switch if valid."""
    result = db.execute(
        select(AdminContextSwitch).where(
            AdminContextSwitch.switch_token == token,
            AdminContextSwitch.is_active == True,
        )
    )
    switch = result.scalar_one_or_none()

    if not switch:
        return None

    # Check if expired
    if switch.expires_at and switch.expires_at < datetime.utcnow():
        switch.is_active = False
        db.commit()
        return None

    return switch


async def _create_audit_log(
    db: AsyncSession,
    admin_id: int,
    operation: str,
    details: Optional[dict] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    context_switch_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> AdminAuditLog:
    """Create an admin audit log entry."""
    log = AdminAuditLog(
        log_no=generate_log_no(),
        admin_user_id=admin_id,
        operation=operation,
        target_type=target_type,
        target_id=target_id,
        context_switch_id=context_switch_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(log)
    await db.commit()
    return log


async def get_audit_logs(
    db: AsyncSession,
    admin_user_id: Optional[int] = None,
    operation: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[AdminAuditLog]:
    """Get admin audit logs with filters."""
    query = select(AdminAuditLog)

    if admin_user_id:
        query = query.where(AdminAuditLog.admin_user_id == admin_user_id)
    if operation:
        query = query.where(AdminAuditLog.operation == operation)

    query = query.order_by(AdminAuditLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


def _get_role_name(role_level: int) -> str:
    """Get role name from role level."""
    role_names = {
        1: "操作工",
        2: "模具工程师",
        3: "组长/主管",
        4: "设计工程师",
        5: "业务经理",
        9: "老板",
        10: "超级管理员",
    }
    return role_names.get(role_level, f"未知({role_level})")
