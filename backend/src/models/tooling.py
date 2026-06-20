"""Tooling (mold/die) models for tooling management."""

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
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.machine import Machine
    from app.models.part import Part
    from app.models.user import User


class ToolingState(str, PyEnum):
    """Tooling/mold lifecycle state."""

    DESIGNING = "designing"  # Under design
    TRIAL = "trial"  # Trial production
    PRODUCTION = "production"  # In production use
    STANDBY = "standby"  # On standby, not in use
    REPAIRING = "repairing"  # Under repair
    SCRAPPED = "scrapped"  # Scrapped/deprecated


class ToolingCavityStatus(str, PyEnum):
    """Cavity status for multi-cavity molds."""

    OK = "ok"  # Normal
    BLOCKED = "blocked"  # Blocked (one cavity out of service)
    REPAIRING = "repairing"  # Cavity under repair


class ToolingMaintenanceType(str, PyEnum):
    """Type of maintenance action."""

    FIRST_SCAN = "first_scan"  # First scan - reported for repair
    SECOND_SCAN = "second_scan"  # Second scan - action selection
    ROUTINE = "routine"  # Routine maintenance
    EMERGENCY = "emergency"  # Emergency repair


class Tooling(Base):
    """Tooling/mold model for die management."""

    __tablename__ = "toolings"

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tooling_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Customer relationship
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id"), nullable=True, index=True
    )
    customer: Mapped[Optional["Customer"]] = relationship("Customer")

    # Parent tooling (for child molds in multi-cavity)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    parent: Mapped[Optional["Tooling"]] = relationship(
        "Tooling", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["Tooling"]] = relationship(
        "Tooling", back_populates="parent"
    )

    # Technical specs
    cavity_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    press_tonnage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spec_twph: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # T×W×PH spec

    # Production info
    ppap_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # State
    state: Mapped[ToolingState] = mapped_column(
        Enum(ToolingState), default=ToolingState.DESIGNING, nullable=False, index=True
    )
    cavity_status: Mapped[ToolingCavityStatus] = mapped_column(
        Enum(ToolingCavityStatus), default=ToolingCavityStatus.OK, nullable=False
    )

    # Mounted machine
    mounted_machine_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    mounted_machine: Mapped[Optional["Machine"]] = relationship("Machine")

    # Design tracking
    designed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trial_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    production_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Drawing path
    drawing_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Tooling {self.tooling_no}>"


class ToolingPart(Base):
    """Association between tooling and parts."""

    __tablename__ = "tooling_parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_id: Mapped[int] = mapped_column(
        ForeignKey("toolings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Assignment info
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    cavity_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Which cavity
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    tooling: Mapped["Tooling"] = relationship("Tooling")
    part: Mapped["Part"] = relationship("Part")


class ToolingMaintenanceLog(Base):
    """Maintenance log for tooling repair tracking."""

    __tablename__ = "tooling_maintenance_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_id: Mapped[int] = mapped_column(
        ForeignKey("toolings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    machine_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

    # Maintenance type
    maintenance_type: Mapped[ToolingMaintenanceType] = mapped_column(
        Enum(ToolingMaintenanceType), nullable=False
    )

    # Scan tracking (for two-scan workflow)
    first_scan_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    first_scan_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    first_scan_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    second_scan_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    second_scan_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    second_scan_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Action taken
    action_taken: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    action_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Repair details
    fault_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repair_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Duration tracking
    fault_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    tooling: Mapped["Tooling"] = relationship("Tooling")

    def __repr__(self) -> str:
        return f"<ToolingMaintenanceLog {self.id} for Tooling {self.tooling_id}>"
