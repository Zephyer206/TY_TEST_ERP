"""Event bus and audit logging system."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit import AuditAction, AuditLog


class EventBus:
    """Simple event bus for application events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event to all subscribed handlers."""
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            if callable(handler):
                await handler(data)


# Global event bus instance
event_bus = EventBus()


async def audit_event(
    db: AsyncSession,
    action: AuditAction,
    entity_type: str,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    extra_data: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """Create an audit log entry."""
    # Build changes summary
    changes_summary = None
    if old_values and new_values:
        changes = []
        for key in set(list(old_values.keys()) + list(new_values.keys())):
            old_val = old_values.get(key)
            new_val = new_values.get(key)
            if old_val != new_val:
                changes.append(f"{key}: {old_val} -> {new_val}")
        if changes:
            changes_summary = "; ".join(changes[:10])  # Limit to 10 changes

    audit_log = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
        old_values=old_values,
        new_values=new_values,
        changes_summary=changes_summary,
        request_id=request_id,
        session_id=session_id,
        extra_data=extra_data,
        created_at=datetime.utcnow(),
    )

    db.add(audit_log)
    await db.flush()

    return audit_log


async def log_create(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    new_values: Optional[dict[str, Any]] = None,
    **kwargs,
) -> AuditLog:
    """Log a create action."""
    return await audit_event(
        db=db,
        action=AuditAction.CREATE,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        username=username,
        new_values=new_values,
        **kwargs,
    )


async def log_update(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    old_values: dict[str, Any],
    new_values: dict[str, Any],
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    **kwargs,
) -> AuditLog:
    """Log an update action."""
    return await audit_event(
        db=db,
        action=AuditAction.UPDATE,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        username=username,
        old_values=old_values,
        new_values=new_values,
        **kwargs,
    )


async def log_delete(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    old_values: Optional[dict[str, Any]] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    **kwargs,
) -> AuditLog:
    """Log a delete action."""
    return await audit_event(
        db=db,
        action=AuditAction.DELETE,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        username=username,
        old_values=old_values,
        **kwargs,
    )


async def log_login(
    db: AsyncSession,
    user_id: int,
    username: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
) -> AuditLog:
    """Log a login attempt."""
    return await audit_event(
        db=db,
        action=AuditAction.LOGIN,
        entity_type="user",
        entity_id=user_id,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
        status="success" if success else "failed",
    )
