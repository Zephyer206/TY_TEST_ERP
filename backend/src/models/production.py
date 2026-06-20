"""Production planning and reporting models."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.part import Part
    from app.models.tooling import Tooling
    from app.models.user import User


class PlanState(str, PyEnum):
    """Production plan status."""

    PLANNED = "planned"  # Created, not started
    IN_PROGRESS = "in_progress"  # Started, machine assigned
    COMPLETED = "completed"  # All quantity produced
    CANCELLED = "cancelled"  # Cancelled
    CLOSED = "closed"  # Closed after completion


class SessionState(str, PyEnum):
    """Production session status."""

    OPEN = "open"  # Active, accepting reports
    CLOSED = "closed"  # Ended
    CANCELLED = "cancelled"  # Forcefully cancelled


class ProductionPlan(Base):
    """Production plan for part manufacturing."""

    __tablename__ = "production_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Part reference
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Planning details
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1)  # 1=normal, 2=urgent, 3=critical

    # Dates
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    state: Mapped[PlanState] = mapped_column(
        Enum(PlanState), default=PlanState.PLANNED, nullable=False, index=True
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Creator
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ProductionPlan {self.plan_no}>"


class PlanMachineAssignment(Base):
    """Assignment of machines to production plan."""

    __tablename__ = "plan_machine_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped["ProductionPlan"] = relationship("ProductionPlan")

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"), nullable=False, index=True
    )
    machine: Mapped["Machine"] = relationship("Machine")

    # Assignment details
    assigned_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    # Assignment time
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    assigned_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ProductionSession(Base):
    """Active production session for a machine-plan combination."""

    __tablename__ = "production_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Plan and machine
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("production_plans.id"), nullable=False, index=True
    )
    plan: Mapped["ProductionPlan"] = relationship("ProductionPlan")

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"), nullable=False, index=True
    )
    machine: Mapped["Machine"] = relationship("Machine")

    # Material validation
    material_batch_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    tooling_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    material_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    force_started: Mapped[bool] = mapped_column(Boolean, default=False)  # Forced by supervisor

    # Session status
    state: Mapped[SessionState] = mapped_column(
        Enum(SessionState), default=SessionState.OPEN, nullable=False, index=True
    )

    # Output tracking
    total_strokes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # strokes * cavities
    total_good_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Process flow card
    process_flow_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ProductionSession {self.session_no}>"


class ProductionReport(Base):
    """Individual production report (stroke report)."""

    __tablename__ = "production_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Session reference
    session_id: Mapped[int] = mapped_column(
        ForeignKey("production_sessions.id"), nullable=False, index=True
    )
    session: Mapped["ProductionSession"] = relationship("ProductionSession")

    # Report details
    strokes: Mapped[int] = mapped_column(Integer, nullable=False)
    cavity_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    output_qty: Mapped[int] = mapped_column(Integer, nullable=False)  # strokes * cavity_count
    good_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reject_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Reject reasons (JSON)
    reject_reasons: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Operator
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    operator_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    reported_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ProductionReport {self.report_no}>"


class ProcessFlowCard(Base):
    """Process flow card generated after session closure."""

    __tablename__ = "process_flow_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Session reference
    session_id: Mapped[int] = mapped_column(
        ForeignKey("production_sessions.id"), nullable=False, index=True
    )
    session: Mapped["ProductionSession"] = relationship("ProductionSession")

    # Part info
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Machine info
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"), nullable=False, index=True
    )
    machine: Mapped["Machine"] = relationship("Machine")

    # Material info
    material_batch_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    material_lot_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Production summary
    total_strokes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    good_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reject_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Time tracking
    production_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    production_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    # QR code path
    qr_code_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ProcessFlowCard {self.card_no}>"
