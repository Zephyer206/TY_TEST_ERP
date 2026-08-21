"""Production planning and reporting models."""

from datetime import date, datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.part import Part
    from app.models.tooling import Tooling
    from app.models.user import User


class PlanStatus(str, PyEnum):
    """Production plan status."""

    PLANNED = "planned"        # Created, not started
    QUEUED = "queued"          # 机台已占用，等待当前计划完成后激活（澄清 2026-06-20 #13）
    IN_PROGRESS = "in_progress"  # Assigned and running
    COMPLETED = "completed"    # 正常达标完成
    CANCELLED = "cancelled"    # Cancelled
    CLOSED = "closed"          # 组长强制提前关闭（未达目标）


class SessionStatus(str, PyEnum):
    """Production session status."""

    PENDING = "pending"  # Waiting for material scan
    ACTIVE = "active"  # Session in progress
    CLOSED = "closed"  # Session ended
    CANCELLED = "cancelled"  # Session cancelled


class ProcessFlowStatus(str, PyEnum):
    """Process flow card status."""

    PENDING = "pending"  # Created, not started
    IN_PROGRESS = "in_progress"  # Being processed
    COMPLETED = "completed"  # All steps completed
    CANCELLED = "cancelled"  # Cancelled


class ProductionPlan(Base):
    """Production plan model - 匹配实际数据库结构."""

    __tablename__ = "production_plans"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Part reference
    part_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("parts.id"), nullable=True, index=True
    )
    paired_part_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("parts.id"), nullable=True, index=True
    )
    is_left_right_pair: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paired_customer_part_no_snapshot: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    paired_part_name_snapshot: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Plan details
    total_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    progress_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    delivered_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)

    # Scheduling
    due_date: Mapped[Optional[date]] = mapped_column(DateTime, nullable=True)

    # Machine assignment
    machine_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    plan_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    force_order: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)
    assigned_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Priority/Urgency
    urgency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Material-readiness workflow. This remains separate from ``status`` so a
    # plan can be ready for scheduling without pretending that production ran.
    material_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    material_confirmed_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    material_confirmed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    material_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    material_confirmation_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    material_calculation_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual"
    )

    # Source-backed T/W/P snapshot used by purchasing. Manual plan overrides
    # are deliberate business input and must never overwrite the part record.
    twp_source_spec_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("part_tooling_specs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    twp_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    twp_thickness: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    twp_width: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    twp_pitch: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    twp_cavity_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    twp_manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    material_name_snapshot: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    material_density_snapshot: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)

    # Status
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Notes
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Creator
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    assignments: Mapped[list["PlanMachineAssignment"]] = relationship(
        "PlanMachineAssignment", back_populates="plan", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProductionPlan {self.id}>"


class PlanMachineAssignment(Base):
    """Assignment of a machine to a production plan."""

    __tablename__ = "plan_machine_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped["ProductionPlan"] = relationship("ProductionPlan", back_populates="assignments")

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"), nullable=False, index=True
    )
    machine: Mapped["Machine"] = relationship("Machine")

    assigned_qty: Mapped[int] = mapped_column(Integer, nullable=False)  # Quantity assigned to this machine
    completed_qty: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    assigned_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<PlanMachineAssignment {self.id}>"


class ProductionSession(Base):
    """Production session for continuous stamping."""

    __tablename__ = "production_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Plan and assignment
    plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("production_plans.id"), nullable=True, index=True
    )
    assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("plan_machine_assignments.id"), nullable=True, index=True
    )

    # Machine and tooling
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"), nullable=False, index=True
    )
    machine: Mapped["Machine"] = relationship("Machine")
    tooling_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tooling.id"), nullable=True, index=True
    )
    tooling: Mapped[Optional["Tooling"]] = relationship("Tooling")

    # Part
    part_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )

    # Material batch used
    material_batch_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.PENDING, nullable=False, index=True
    )

    # Session tracking
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Summary (filled on close)
    total_strokes: Mapped[int] = mapped_column(Integer, default=0)
    total_output: Mapped[int] = mapped_column(Integer, default=0)  # strokes × cavity_count
    good_qty: Mapped[int] = mapped_column(Integer, default=0)
    reject_qty: Mapped[int] = mapped_column(Integer, default=0)
    work_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # closed_at - started_at（澄清 #24）

    # Process flow
    process_flow_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Operator
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Reports
    reports: Mapped[list["ProductionReport"]] = relationship(
        "ProductionReport", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProductionSession {self.session_no}>"


class ProductionReport(Base):
    """Production report within a session."""

    __tablename__ = "production_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("production_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session: Mapped["ProductionSession"] = relationship("ProductionSession", back_populates="reports")

    # Strokes and output
    strokes: Mapped[int] = mapped_column(Integer, nullable=False)
    cavity_count: Mapped[int] = mapped_column(Integer, default=1)  # Part cavities
    output: Mapped[int] = mapped_column(Integer, nullable=False)  # strokes × cavity_count

    # Quality
    good_qty: Mapped[int] = mapped_column(Integer, default=0)
    reject_qty: Mapped[int] = mapped_column(Integer, default=0)

    # Material consumption
    material_used: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # kg

    # Timestamps
    report_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Operator
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ProductionReport {self.id}>"


class ProcessFlowCard(Base):
    """Process flow card for tracking production steps."""

    __tablename__ = "process_flow_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Session that generated this card
    session_id: Mapped[int] = mapped_column(
        ForeignKey("production_sessions.id"), nullable=False, index=True
    )

    # Part and customer
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Machine and tooling
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"), nullable=False, index=True
    )
    machine: Mapped["Machine"] = relationship("Machine")

    tooling_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tooling.id"), nullable=True
    )
    tooling: Mapped[Optional["Tooling"]] = relationship("Tooling")

    # Material
    material_batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Quantities
    planned_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_output: Mapped[int] = mapped_column(Integer, default=0)
    good_qty: Mapped[int] = mapped_column(Integer, default=0)
    reject_qty: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[ProcessFlowStatus] = mapped_column(
        Enum(ProcessFlowStatus), default=ProcessFlowStatus.PENDING, nullable=False, index=True
    )

    # Timestamps
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Operator
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Inbound (QC passed -> finished goods inventory)
    inbound_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    inbound_operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inbound_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # QR Code
    qr_code: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ProcessFlowCard {self.card_no}>"
