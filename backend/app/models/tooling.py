"""Tooling (mold/die) and tooling maintenance models."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.machine import Machine


class ToolingState(str, PyEnum):
    """Tooling/mold status."""

    AVAILABLE = "available"  # Available for use
    IN_USE = "in_use"  # Currently mounted on a machine
    MAINTENANCE = "maintenance"  # Under repair
    CONVERTED = "converted"  # Modified/rebuilt
    SCRAPPED = "scrapped"  # Written off


class ToolingMaintenanceLog(Base):
    """Tooling maintenance log for tracking repairs."""

    __tablename__ = "tooling_maintenance_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_id: Mapped[int] = mapped_column(
        ForeignKey("tooling_molds.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Machine that reported the fault
    machine_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

    # Fault info
    fault_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fault_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Repair info
    repair_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repair_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    repair_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    repair_completed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ToolingMaintenanceLog {self.id}>"


class Tooling(Base):
    """Tooling (mold/die) model."""

    __tablename__ = "tooling_molds"

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_product_no: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    cavity_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tonnage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ppap_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # State
    state: Mapped[ToolingState] = mapped_column(
        Enum(ToolingState), default=ToolingState.AVAILABLE, nullable=False, index=True
    )

    # Parent-child relationship (for die-sets)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tooling_molds.id"), nullable=True, index=True
    )
    parent: Mapped[Optional["Tooling"]] = relationship(
        "Tooling", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["Tooling"]] = relationship(
        "Tooling", back_populates="parent"
    )

    # Technical specs
    spec_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    drawing_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sdr_drawing_path: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Technical analysis drawing

    # Active maintenance log
    active_maintenance_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

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
    """Association table between tooling and parts."""

    __tablename__ = "tooling_parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_id: Mapped[int] = mapped_column(
        ForeignKey("tooling_molds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
