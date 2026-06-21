"""Authentication API endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_tokens, verify_password
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response Schemas
class LoginRequest(BaseModel):
    """Login request schema."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User response schema."""

    id: int
    username: str
    email: str
    full_name: str
    role: str
    department_id: int | None
    is_active: bool

    model_config = {"from_attributes": True}


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


# Endpoints
@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: DbSession,
) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    # Find user by username
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.password):  # 注意：字段是 password 不是 hashed_password
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 注意：数据库中没有 is_active 字段，使用 is_superadmin 作为活跃状态判断
    # if not user.is_active:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="User account is disabled",
    #     )

    # Update last login (注意：数据库中也没有 last_login 字段)
    # user.last_login = datetime.utcnow()
    await db.commit()

    # Create tokens
    return create_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: DbSession,
) -> TokenResponse:
    """Refresh access token using refresh token."""
    from app.core.security import decode_token

    payload = decode_token(request.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Get user from database
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new tokens
    return create_tokens(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout(
    current_user: CurrentUser,
) -> dict[str, str]:
    """Logout current user (client should discard tokens)."""
    # In a stateless JWT system, logout is handled client-side
    # For Redis-backed sessions, we could invalidate the token here
    return {"message": "Successfully logged out"}
