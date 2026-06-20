"""Admin and superuser management models."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ContextSwitchType(str, PyEnum):
    """Context switch type."""

    TO_BUSINESS = "to_business"  # Switch to business perspective
    TO_PRODUCTION = "to_production"  # Switch to production perspective
    TO_QUALITY = "to_quality"  # Switch to quality perspective
    TO_WAREHOUSE = "to_warehouse"  # Switch to warehouse perspective
    TO_DESIGN = "to_design"  # Switch to design perspective
    TO_ADMIN = "to_admin"  # Switch back to admin


class AdminContextSwitch(Base):
    """Admin context switch record model.

    Records when super admins temporarily switch their view to another department's perspective.
    """

    __tablename__ = "admin_context_switches"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Admin user who performed the switch
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    user: Mapped["User"] = relationship("User")

    # Original role (stored for audit and restoration)
    original_role_level: Mapped[int] = mapped_column(Integer, nullable=False)
    original_dept: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Switched to
    switched_to_dept: Mapped[str] = mapped_column(String(50), nullable=False)
    switched_to_role_level: Mapped[int] = mapped_column(Integer, nullable=False)

    # Switch type
    switch_type: Mapped[ContextSwitchType] = mapped_column(
        Enum(ContextSwitchType), nullable=False
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Session reference (for linking with Redis session)
    session_key: Mapped[Optional[str]] = mapped_column(
        String(200), unique=True, nullable=True, index=True
    )

    # Timestamps
    switched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    switched_back_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AdminContextSwitch user={self.user_id} dept={self.switched_to_dept}>"
