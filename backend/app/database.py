"""Database connection and session management using asyncpg."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import settings

# Async engine for PostgreSQL with asyncpg
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # SQL echo in debug mode
    poolclass=AsyncAdaptedQueuePool,
    # Keep the pool bounded for the remote PostgreSQL deployment. A large
    # pool makes a Windows service restart look like a connection failure
    # while stale sockets are still being reclaimed.
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=900,  # Recycle connections before common idle timeouts
    connect_args={"timeout": 10, "command_timeout": 30},
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions outside of request scope."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database - create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
