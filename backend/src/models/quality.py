"""Quality inspection and release management models."""

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
    from app.models.part import Part
    from app.models.production import ProductionSession


class InspectionResult(str, PyEnum):
    """Inspection result."""

    PASSED = "passed"
    FAILED = "failed"
    CONDITIONAL = "conditional"  # Passed with conditions


class ExemptionType(str, PyEnum):
    """QA exemption type."""

    EMERGENCY = "emergency"  # Emergency release
    CUSTOMER = "customer"  # Customer approved deviation
    ENGINEERING = "engineering"  # Engineering deviation
    OTHER = "other"


class FirstPieceInspection(Base):
    """First piece inspection model."""

    __tablename__ = "first_piece_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Part and production
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("production_sessions.id"), nullable=True, index=True
    )
    session: Mapped[Optional["ProductionSession"]] = relationship("ProductionSession")

    # Inspection details
    inspected_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    inspected_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Dimensions
    dimension_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    dimension_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Appearance
    appearance_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    appearance_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Function
    function_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    function_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Result
    result: Mapped[InspectionResult] = mapped_column(
        Enum(InspectionResult), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    inspected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<FirstPieceInspection {self.inspection_no}>"


class OQCInspection(Base):
    """Outgoing Quality Control inspection model."""

    __tablename__ = "oqc_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Part and shipment
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Shipment info
    shipment_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    order_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Inspection details
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    inspected_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # AQL results
    aql_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # e.g., "II"
    major_defects: Mapped[int] = mapped_column(Integer, default=0)
    minor_defects: Mapped[int] = mapped_column(Integer, default=0)
    critical_defects: Mapped[int] = mapped_column(Integer, default=0)

    # Result
    result: Mapped[InspectionResult] = mapped_column(
        Enum(InspectionResult), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    inspected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<OQCInspection {self.inspection_no}>"


class QAExemption(Base):
    """QA exemption/waiver model for emergency releases."""

    __tablename__ = "qa_exemptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    exemption_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Part
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Exemption details
    exemption_type: Mapped[ExemptionType] = mapped_column(
        Enum(ExemptionType), nullable=False
    )

    # Issue description
    issue_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Quantities affected
    affected_qty: Mapped[int] = mapped_column(Integer, nullable=False)

    # Approval
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Exemption reason (required for granting)
    exemption_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<QAExemption {self.exemption_no}>"


class PatrolInspection(Base):
    """Patrol inspection (巡检) model."""

    __tablename__ = "patrol_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Machine and production
    machine_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("production_sessions.id"), nullable=True, index=True
    )
    session: Mapped[Optional["ProductionSession"]] = relationship("ProductionSession")

    # Inspection details
    inspected_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Quality checks
    dimension_check: Mapped[bool] = mapped_column(Boolean, default=False)
    appearance_check: Mapped[bool] = mapped_column(Boolean, default=False)
    process_parameter_check: Mapped[bool] = mapped_column(Boolean, default=False)

    # Sample info
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    defect_count: Mapped[int] = mapped_column(Integer, default=0)

    # Result
    result: Mapped[InspectionResult] = mapped_column(
        Enum(InspectionResult), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Corrective action
    corrective_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_taken_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    inspected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<PatrolInspection {self.inspection_no}>"
