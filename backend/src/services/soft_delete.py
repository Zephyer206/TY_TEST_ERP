"""
Database soft delete mixin and utility functions.

Provides soft delete functionality for all models to meet FR-085 requirements.
All DELETE operations should use is_deleted flag instead of hard delete.
"""

from datetime import datetime
from typing import Optional, Type, TypeVar

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


class SoftDeleteMixin:
    """Mixin class that adds soft delete functionality to models.

    Usage:
        class MyModel(Base, SoftDeleteMixin):
            __tablename__ = "my_table"

            id = Column(Integer, primary_key=True)
            name = Column(String)
            is_deleted = Column(Boolean, default=False)
            deleted_at = Column(DateTime, nullable=True)
    """

    is_deleted: bool
    deleted_at: Optional[datetime]

    @classmethod
    async def soft_delete(cls, db: AsyncSession, id: int) -> bool:
        """
        Soft delete a record by setting is_deleted=True.

        Args:
            db: Database session
            id: Record ID to delete

        Returns:
            True if record was found and deleted, False otherwise
        """
        stmt = (
            update(cls)
            .where(cls.id == id)
            .values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
            )
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @classmethod
    async def soft_delete_many(
        cls, db: AsyncSession, ids: list[int]
    ) -> int:
        """
        Soft delete multiple records.

        Args:
            db: Database session
            ids: List of record IDs to delete

        Returns:
            Number of records deleted
        """
        if not ids:
            return 0

        stmt = (
            update(cls)
            .where(cls.id.in_(ids))
            .values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
            )
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount


def soft_delete_query(cls: Type[ModelType], include_deleted: bool = False):
    """
    Create a query filter that excludes soft-deleted records.

    Args:
        cls: Model class
        include_deleted: If True, include deleted records

    Returns:
        SQLAlchemy filter condition
    """
    if include_deleted:
        return True  # No filter
    return cls.is_deleted == False


async def restore_soft_deleted(
    db: AsyncSession,
    cls: Type[ModelType],
    id: int,
) -> bool:
    """
    Restore a soft-deleted record.

    Args:
        db: Database session
        cls: Model class
        id: Record ID to restore

    Returns:
        True if record was found and restored, False otherwise
    """
    stmt = (
        update(cls)
        .where(cls.id == id, cls.is_deleted == True)
        .values(
            is_deleted=False,
            deleted_at=None,
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


async def permanent_delete(
    db: AsyncSession,
    cls: Type[ModelType],
    id: int,
) -> bool:
    """
    Permanently delete a record (hard delete).

    WARNING: This is irreversible. Use soft_delete instead when possible.

    Args:
        db: Database session
        cls: Model class
        id: Record ID to delete

    Returns:
        True if record was deleted, False otherwise
    """
    from sqlalchemy import delete

    stmt = delete(cls).where(cls.id == id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


# Decorator for repository methods to enforce soft delete
def require_undeleted(func):
    """Decorator to ensure repository methods filter out deleted records."""

    async def wrapper(*args, **kwargs):
        # Add include_deleted=False if not provided
        if "include_deleted" not in kwargs:
            kwargs["include_deleted"] = False
        return await func(*args, **kwargs)

    return wrapper


# Audit log for soft delete operations
async def log_soft_delete(
    db: AsyncSession,
    user_id: int,
    entity_type: str,
    entity_id: int,
    reason: Optional[str] = None,
) -> None:
    """
    Create an audit log entry for soft delete operations.

    Args:
        db: Database session
        user_id: ID of user performing the deletion
        entity_type: Type of entity being deleted (e.g., 'Quote', 'Part')
        entity_id: ID of the entity being deleted
        reason: Optional reason for deletion
    """
    from sqlalchemy import text

    await db.execute(
        text("""
            INSERT INTO admin_audit_logs (
                log_no, admin_user_id, operation,
                target_type, target_id, details, created_at
            ) VALUES (
                'DEL-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || SUBSTR(MD5(RANDOM()::TEXT), 1, 6),
                :user_id, 'SOFT_DELETE',
                :entity_type, :entity_id,
                :reason::jsonb,
                NOW()
            )
        """),
        {
            "user_id": user_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "reason": ('{"reason": "' + reason + '"}') if reason else None,
        },
    )
    await db.commit()
