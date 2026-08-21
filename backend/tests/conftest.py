"""Test configuration and fixtures."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models.user import User


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session.

    Note: This is a placeholder. For real tests, you should use a separate test database.
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as session:
            yield session
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for testing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def lv1_headers(db) -> dict[str, str]:
    """Authentication headers for LV1 user."""
    result = await db.execute(select(User).where(User.username == "test_lv1"))
    user = result.scalar_one_or_none()
    if not user:
        user = User(username="test_lv1", password="hashed", role_level=1)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def lv2_headers(db) -> dict[str, str]:
    """Authentication headers for LV2 user."""
    result = await db.execute(select(User).where(User.username == "test_lv2"))
    user = result.scalar_one_or_none()
    if not user:
        user = User(username="test_lv2", password="hashed", role_level=2)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_parts():
    """Placeholder fixture for sample parts (tests create their own as needed)."""
    return {}
