"""Security utilities: JWT tokens and password hashing with LV1-LV4 permission system."""

from datetime import datetime, timedelta
from typing import Any, Optional

from jose import JWTError, jwt
from app.core.config import settings
from app.models.user import User


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash using bcrypt directly."""
    import bcrypt
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    # Use bcrypt directly so hashing and verification share the same backend.
    # This avoids passlib's compatibility probe failing with newer bcrypt releases.
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


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
    """Create access and refresh tokens for a user.

    JWT payload uses canonical LV1-LV4 role_level field.
    """
    token_data = {
        "sub": str(user.id),
        "username": user.username,
        "role_level": user.role_level,  # LV1-LV4 only
        "dept": user.dept,  # department code string
        "is_tech": user.is_tech,  # orthogonal business metadata
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def verify_min_role_level(user: User, min_level: int) -> bool:
    """Verify if user has at least the minimum required role level.

    Args:
        user: User object with role_level (1-4)
        min_level: Minimum required level (1-4)

    Returns:
        True if user.role_level >= min_level
    """
    if not (1 <= min_level <= 4):
        raise ValueError(f"Invalid min_level {min_level}, must be 1-4")

    return user.role_level >= min_level
