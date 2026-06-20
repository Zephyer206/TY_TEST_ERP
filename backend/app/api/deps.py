"""API dependency injection functions."""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User, UserRole

# Security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise credentials_exception

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Get user from database
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


def require_roles(roles: list[UserRole]):
    """Dependency factory for role-based access control."""
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.is_superuser:
            return current_user

        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {[r.value for r in roles]}",
            )
        return current_user

    return role_checker


def require_role(min_level: int):
    """Dependency factory for minimum role level check.

    Args:
        min_level: Minimum role level required (0-10 scale).
            1=操作工, 2=发货员/仓库, 3=组长/主管,
            4=工程师, 5=业务经理, 9=老板, 10+=超级管理员
    """
    async def level_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.is_superuser:
            return current_user

        user_level = getattr(current_user, "role_level", 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Minimum role level required: {min_level}",
            )
        return current_user

    return level_checker


def require_min_role(min_role: UserRole):
    """Dependency factory for minimum role level check."""
    from app.core.security import verify_min_role

    async def min_role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not verify_min_role(current_user, min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Minimum required role: {min_role.value}",
            )
        return current_user

    return min_role_checker


# Type aliases for common dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = Annotated[User, Depends(get_current_active_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
