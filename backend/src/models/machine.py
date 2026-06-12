"""Machine model for production equipment."""

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
    from app.models.tooling import Tooling


class MachineState(str, PyEnum):
    """Machine operational state."""

    IDLE = "idle"  # Available, no job assigned
    RUNNING = "running"  # In production
    FAULT = "fault"  # Fault reported, awaiting confirmation
    PENDING_CHECK = "pending_check"  # Awaiting first scan (maintenance)
    REPAIRING = "repairing"  # Under repair
    OFFLINE = "offline"  # Manually taken offline


class Machine(Base):
    """Machine/press model."""

    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Machine specs
    machine_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tonnage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_stroke: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bed_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Current state
    state: Mapped[MachineState] = mapped_column(
        Enum(MachineState), default=MachineState.IDLE, nullable=False, index=True
    )

    # Current tooling mounted
    current_tooling_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Fault tracking
    fault_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fault_reported_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fault_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Repair tracking
    repair_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    repairer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Location
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Machine {self.machine_no}>"


class MachineStatusLog(Base):
    """Machine status change log for audit trail."""

    __tablename__ = "machine_status_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_state: Mapped[MachineState] = mapped_column(
        Enum(MachineState), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
