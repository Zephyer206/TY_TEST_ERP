"""Security utilities: JWT tokens and password hashing."""

from datetime import datetime, timedelta
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.config import settings
from src.models.user import User, UserRole

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def create_tokens(user: User) -> dict[str, str]:
    """Create access and refresh tokens for a user."""
    token_data = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def verify_role(user: User, required_roles: list[UserRole]) -> bool:
    """Verify if user has one of the required roles."""
    if user.is_superuser:
        return True
    return user.role in required_roles


def verify_min_role(user: User, min_role: UserRole) -> bool:
    """Verify if user has at least the minimum required role."""
    if user.is_superuser:
        return True

    role_hierarchy = {
        UserRole.VIEWER: 0,
        UserRole.WAREHOUSE: 1,
        UserRole.QC: 2,
        UserRole.PRODUCTION: 3,
        UserRole.TECH: 4,
        UserRole.SALES: 5,
        UserRole.MANAGER: 6,
        UserRole.ADMIN: 7,
    }

    user_level = role_hierarchy.get(user.role, 0)
    required_level = role_hierarchy.get(min_role, 0)

    return user_level >= required_level
