"""Sampling task model for sample production management."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.part import Part
    from app.models.user import User


class SamplingTaskState(str, PyEnum):
    """Sampling task status."""

    PENDING_APPROVAL = "pending_approval"  # Waiting for boss approval
    APPROVED = "approved"  # Boss approved, ready for production
    IN_PRODUCTION = "in_production"  # Sampling in progress
    PENDING_REVIEW = "pending_review"  # Awaiting customer review
    PASSED = "passed"  # Review passed
    FAILED = "failed"  # Review failed
    CANCELLED = "cancelled"  # Task cancelled


class SamplingTask(Base):
    """Sampling task model for managing sample production workflow."""

    __tablename__ = "sampling_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Part and customer
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part", back_populates="sampling_tasks")

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    customer: Mapped["Customer"] = relationship("Customer")

    # Quote reference (optional, for context)
    quote_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quotes.id"), nullable=True, index=True
    )

    # Task state
    state: Mapped[SamplingTaskState] = mapped_column(
        Enum(SamplingTaskState),
        default=SamplingTaskState.PENDING_APPROVAL,
        nullable=False,
        index=True,
    )

    # Task details
    sample_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_completion_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_completion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Urgent flag
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Review
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewer_id])

    # Cancellation
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Approval tracking
    approved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by])
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<SamplingTask {self.task_no}>"
