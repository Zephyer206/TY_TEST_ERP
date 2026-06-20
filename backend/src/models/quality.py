"""Quality control models for inspection and release management."""

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
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.part import Part
    from app.models.production import ProcessFlowCard
    from app.models.user import User


class InspectionResult(str, PyEnum):
    """Inspection result enumeration."""

    PASS = "pass"  # Passed inspection
    FAIL = "fail"  # Failed inspection
    CONDITIONAL = "conditional"  # Conditionally accepted
    PENDING = "pending"  # Awaiting decision


class FirstPieceStatus(str, PyEnum):
    """First piece inspection status."""

    PENDING = "pending"  # Awaiting inspection
    APPROVED = "approved"  # Approved for production
    REJECTED = "rejected"  # Rejected
    CONDITIONAL = "conditional"  # Conditionally approved


class OQCResult(str, PyEnum):
    """OQC (Outgoing Quality Control) result."""

    PASS = "pass"  # Passed OQC
    FAIL = "fail"  # Failed OQC


class FirstPieceInspection(Base):
    """First piece inspection model for production start validation."""

    __tablename__ = "first_piece_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Part reference
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Process flow card reference
    process_flow_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

    # Inspection criteria results (JSON)
    dimension_check: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    surface_check: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    material_check: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Overall result
    result: Mapped[FirstPieceStatus] = mapped_column(
        Enum(FirstPieceStatus), default=FirstPieceStatus.PENDING, nullable=False
    )

    # Reject details
    reject_reasons: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rework_required: Mapped[bool] = mapped_column(Boolean, default=False)

    # Inspector
    inspector_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inspected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Notes and attachments
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachment_paths: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Batch info
    batch_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<FirstPieceInspection {self.inspection_no}>"


class OQCInspection(Base):
    """OQC (Outgoing Quality Control) inspection model for shipment validation."""

    __tablename__ = "oqc_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Part reference
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Shipment reference
    shipment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Inspection quantities
    inspected_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_qty: Mapped[int] = mapped_column(Integer, nullable=False)

    # Defect details
    defect_types: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"type1": count, ...}
    defect_positions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # defect location map

    # Result
    result: Mapped[OQCResult] = mapped_column(
        Enum(OQCResult), nullable=False
    )

    # Inspector
    inspector_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inspected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Sampling info
    sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sampling_plan: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachment_paths: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
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

    # Part reference
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Related inspection
    related_inspection_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    related_inspection_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Exemption details
    defect_description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_affected: Mapped[int] = mapped_column(Integer, nullable=False)

    # Justification
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    impact_assessment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_notification_required: Mapped[bool] = mapped_column(Boolean, default=False)

    # Approval
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Requester
    requested_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    request_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Approver
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approval_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Expiry
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<QAExemption {self.exemption_no}>"


class PatrolInspection(Base):
    """Patrol inspection model for in-process quality checks."""

    __tablename__ = "patrol_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Machine/Line reference
    machine_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    production_session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Inspection content
    check_points: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # inspection criteria
    check_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # actual results

    # Overall result
    result: Mapped[InspectionResult] = mapped_column(
        Enum(InspectionResult), default=InspectionResult.PENDING, nullable=False
    )

    # Issues found
    issues_found: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # critical/major/minor

    # Corrective action
    corrective_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_required: Mapped[bool] = mapped_column(Boolean, default=False)

    # Inspector
    inspector_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inspected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

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
        return f"<PatrolInspection {self.inspection_no}>"
