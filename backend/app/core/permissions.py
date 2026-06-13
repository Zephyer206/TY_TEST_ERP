"""Role-based permission decorators and utilities."""

from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import HTTPException, status

from src.models.user import User, UserRole

F = TypeVar("F", bound=Callable[..., Any])


def require_role(*roles: UserRole):
    """Decorator for requiring specific roles on endpoint functions."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current_user from kwargs or inject it
            current_user: User = kwargs.get("current_user")
            if current_user is None:
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break

            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            if current_user.is_superuser:
                return await func(*args, **kwargs)

            if current_user.role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required roles: {[r.value for r in roles]}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_min_role(min_role: UserRole):
    """Decorator for requiring minimum role level."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from src.core.security import verify_min_role

            current_user: User = kwargs.get("current_user")
            if current_user is None:
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break

            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            if not verify_min_role(current_user, min_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Minimum required role: {min_role.value}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_superuser(func: F) -> F:
    """Decorator for superuser-only endpoints."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        current_user: User = kwargs.get("current_user")
        if current_user is None:
            for arg in args:
                if isinstance(arg, User):
                    current_user = arg
                    break

        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Superuser access required",
            )

        return await func(*args, **kwargs)

    return wrapper
