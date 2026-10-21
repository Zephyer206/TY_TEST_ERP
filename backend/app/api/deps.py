"""API dependency injection functions with canonical LV1-LV4 permission system."""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User

# Security scheme. `auto_error=False` lets the temporary acceptance mode
# inject the administrator when no login header is present.
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current authenticated user from JWT token."""
    if settings.AUTH_DISABLED:
        result = await db.execute(
            select(User)
            .where(User.role_level == 4)
            .order_by(User.id.asc())
        )
        admin_user = result.scalars().first()
        if admin_user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Acceptance administrator is not configured",
            )
        return admin_user

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None or payload.get("type") != "access":
        raise credentials_exception

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Get user from database
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current active user. All users are active by default."""
    return current_user


def require_role(current_user=None, min_level: Optional[int] = None):
    """Dependency factory for minimum role level check with canonical LV1-LV4 system.

    Canonical 4-level permission system:
    - LV1 (min_level=1): Ordinary staff - operators, warehouse staff, QC staff, spray workers, maintenance
    - LV2 (min_level=2): Managers & business/technical staff - team leaders, technical, business, supervisors
    - LV3 (min_level=3): Boss - final approval, global data visibility
    - LV4 (min_level=4): Super administrator - system management, context switching

    Args:
        min_level: Minimum role level required (1-4 only).

    Returns:
        Dependency function that checks user.role_level >= min_level
    """
    # Two call styles exist in the migrated API surface:
    #   * ``Depends(require_role(min_level=2))`` (dependency factory)
    #   * ``require_role(current_user, min_level=2)`` (direct route guard)
    # Keep both forms valid while routes are migrated incrementally.
    if min_level is None:
        min_level = current_user
        current_user = None

    if not isinstance(min_level, int) or not (1 <= min_level <= 4):
        raise ValueError(f"Invalid min_level {min_level}, must be 1-4")

    if current_user is not None:
        user_level = current_user.role_level
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Minimum role level required: LV{min_level}, you have LV{user_level}",
            )
        return current_user

    async def level_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        user_level = current_user.role_level
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Minimum role level required: LV{min_level}, you have LV{user_level}",
            )
        return current_user

    return level_checker


# Type aliases for common dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = Annotated[User, Depends(get_current_active_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
