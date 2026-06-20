"""Admin context switching models for role impersonation."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class SwitchTargetRole(str, PyEnum):
    """Target role when admin switches context."""

    OPERATOR = "operator"  # 操作工 (role_level=1)
    MOLD_ENGINEER = "mold_engineer"  # 模具工程师 (role_level=2)
    SUPERVISOR = "supervisor"  # 组长/主管 (role_level=3)
    DESIGN_ENGINEER = "design_engineer"  # 设计工程师 (role_level=4)
    SALES_MANAGER = "sales_manager"  # 业务经理 (role_level=5)


class AdminContextSwitch(Base):
    """Admin context switch tracking for audit and session management."""

    __tablename__ = "admin_context_switches"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Admin user who performed the switch
    admin_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Original role (always 10 for admin)
    original_role_level: Mapped[int] = mapped_column(Integer, nullable=False)

    # Switched role
    switched_role_level: Mapped[int] = mapped_column(Integer, nullable=False)
    switched_role_name: Mapped[str] = mapped_column(String(50), nullable=False)

    # Session token for the switched context
    switch_token: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, index=True
    )

    # Validity
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    switched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    switched_back_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Reason
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # IP for security tracking
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AdminContextSwitch admin={self.admin_user_id} "
            f"role={self.original_role_level}->{self.switched_role_level}>"
        )


class AdminAuditLog(Base):
    """Admin operation audit log for security compliance."""

    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    log_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Admin user
    admin_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Operation type
    operation: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Target entity
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Context switch info (if applicable)
    context_switch_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Details
    details: Mapped[Optional[dict]] = mapped_column(nullable=True)

    # IP for security
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AdminAuditLog {self.log_no} {self.operation}>"
