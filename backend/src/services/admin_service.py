"""Business logic for admin and context switch management."""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.admin import AdminContextSwitch, ContextSwitchType
from src.models.user import User
from src.schemas.admin import DEPT_ROLE_MAPPINGS


SESSION_EXPIRY_SECONDS = 3600  # 1 hour


def generate_session_key() -> str:
    """Generate a unique session key for context switch."""
    return f"ctx_switch_{secrets.token_urlsafe(32)}"


def _get_dept_mapping(department: str) -> dict:
    """Get role mapping for a department."""
    mapping = DEPT_ROLE_MAPPINGS.get(department.lower())
    if not mapping:
        raise ValueError(f"Unknown department: {department}")
    return mapping


async def switch_context(
    db: AsyncSession,
    user: User,
    department: str,
) -> tuple[AdminContextSwitch, str]:
    """Switch admin context to another department perspective.

    Args:
        db: Database session
        user: Current admin user
        department: Target department to switch to

    Returns:
        Tuple of (context switch record, session key)

    Raises:
        ValueError: If user is not admin or department is invalid
    """
    # Verify user is admin (role_level >= 10)
    if user.role_level < 10:
        raise ValueError("Only super admin can switch context")

    # Deactivate any existing active switches for this user
    await db.execute(
        update(AdminContextSwitch)
        .where(AdminContextSwitch.user_id == user.id)
        .where(AdminContextSwitch.is_active == True)
        .values(is_active=False, switched_back_at=datetime.utcnow())
    )

    # Get role mapping for department
    mapping = _get_dept_mapping(department)

    # Map department to switch type
    switch_type_map = {
        "sales": ContextSwitchType.TO_BUSINESS,
        "production": ContextSwitchType.TO_PRODUCTION,
        "quality": ContextSwitchType.TO_QUALITY,
        "warehouse": ContextSwitchType.TO_WAREHOUSE,
        "design": ContextSwitchType.TO_DESIGN,
        "mold": ContextSwitchType.TO_BUSINESS,
        "packaging": ContextSwitchType.TO_PRODUCTION,
        "spray": ContextSwitchType.TO_PRODUCTION,
    }
    switch_type = switch_type_map.get(department.lower(), ContextSwitchType.TO_BUSINESS)

    # Create new context switch record
    session_key = generate_session_key()
    expires_at = datetime.utcnow() + timedelta(seconds=SESSION_EXPIRY_SECONDS)

    context_switch = AdminContextSwitch(
        user_id=user.id,
        original_role_level=user.role_level,
        original_dept=user.dept,
        switched_to_dept=department,
        switched_to_role_level=mapping["role_level"],
        switch_type=switch_type,
        is_active=True,
        session_key=session_key,
        expires_at=expires_at,
    )
    db.add(context_switch)
    await db.commit()
    await db.refresh(context_switch)

    return context_switch, session_key


async def switch_back(
    db: AsyncSession,
    user: User,
    session_key: Optional[str] = None,
) -> AdminContextSwitch:
    """Switch back to admin perspective.

    Args:
        db: Database session
        user: Current user
        session_key: Optional session key to verify

    Returns:
        Updated context switch record

    Raises:
        ValueError: If no active switch found
    """
    # Find active context switch
    query = select(AdminContextSwitch).where(
        AdminContextSwitch.user_id == user.id,
        AdminContextSwitch.is_active == True,
    )

    if session_key:
        query = query.where(AdminContextSwitch.session_key == session_key)

    result = await db.execute(query)
    context_switch = result.scalar_one_or_none()

    if not context_switch:
        raise ValueError("No active context switch found")

    # Deactivate the switch
    context_switch.is_active = False
    context_switch.switched_back_at = datetime.utcnow()

    await db.commit()
    await db.refresh(context_switch)

    return context_switch


async def get_active_context_switch(
    db: AsyncSession,
    user_id: int,
) -> Optional[AdminContextSwitch]:
    """Get the active context switch for a user."""
    result = await db.execute(
        select(AdminContextSwitch)
        .where(AdminContextSwitch.user_id == user_id)
        .where(AdminContextSwitch.is_active == True)
    )
    return result.scalar_one_or_none()


async def get_context_switch_history(
    db: AsyncSession,
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[AdminContextSwitch]:
    """Get context switch history."""
    query = select(AdminContextSwitch).order_by(
        AdminContextSwitch.switched_at.desc()
    )

    if user_id:
        query = query.where(AdminContextSwitch.user_id == user_id)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


def get_effective_role(user: User, context_switch: Optional[AdminContextSwitch] = None) -> dict:
    """Get effective role after considering context switch.

    Args:
        user: Original user
        context_switch: Active context switch if any

    Returns:
        Dict with effective role_level and dept
    """
    if context_switch and context_switch.is_active:
        # Check if switch has expired
        if context_switch.expires_at and context_switch.expires_at < datetime.utcnow():
            return {
                "role_level": user.role_level,
                "dept": user.dept,
                "is_switched": False,
                "original_role_level": user.role_level,
                "original_dept": user.dept,
            }

        return {
            "role_level": context_switch.switched_to_role_level,
            "dept": context_switch.switched_to_dept,
            "is_switched": True,
            "original_role_level": context_switch.original_role_level,
            "original_dept": context_switch.original_dept,
            "switch_type": context_switch.switch_type,
            "switched_at": context_switch.switched_at,
            "expires_at": context_switch.expires_at,
        }

    return {
        "role_level": user.role_level,
        "dept": user.dept,
        "is_switched": False,
        "original_role_level": user.role_level,
        "original_dept": user.dept,
    }


def can_access_boss_button(role_level: int) -> bool:
    """Check if user can access boss-only buttons.

    Boss buttons (role_level >= 9) should be hidden when admin
    is switched to another perspective.
    """
    return role_level >= 9
