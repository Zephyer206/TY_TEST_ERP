"""Warehouse and material batch management models."""

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
    from app.models.user import User


class BatchStatus(str, PyEnum):
    """Material batch status."""

    PENDING_IQC = "pending_iqc"  # Waiting for incoming quality check
    AVAILABLE = "available"  # Passed IQC, available for use
    IN_USE = "in_use"  # Currently being used in production
    PARTIAL = "partial"  # Partially consumed (after split)
    EXHAUSTED = "exhausted"  # Fully consumed
    REJECTED = "rejected"  # Failed IQC
    SCRAPPED = "scrapped"  # Manually scrapped


class IQCResult(str, PyEnum):
    """IQC inspection result."""

    PASSED = "passed"
    FAILED = "failed"


class Supplier(Base):
    """Raw material supplier model."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_person: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Supplier {self.supplier_no}>"


class Material(Base):
    """Raw material catalog model."""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    grade: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., DC01, SPCC
    thickness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # mm
    width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # mm
    weight_per_unit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # kg per unit
    unit: Mapped[str] = mapped_column(String(20), default="kg")  # kg, ton, piece

    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True, index=True
    )
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Material {self.material_no}>"


class MaterialBatch(Base):
    """Material batch for tracking and tracing."""

    __tablename__ = "material_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_no: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    qr_code: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # QR code content

    # Material info
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id"), nullable=False, index=True
    )
    material: Mapped["Material"] = relationship("Material")
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True, index=True
    )
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier")

    # Dimensions
    thickness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Weight
    gross_weight: Mapped[float] = mapped_column(Float, nullable=False)  # kg
    net_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # kg
    current_weight: Mapped[float] = mapped_column(Float, nullable=False)  # kg

    # Batch status
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus), default=BatchStatus.PENDING_IQC, nullable=False, index=True
    )

    # IQC
    iqc_result: Mapped[Optional[IQCResult]] = mapped_column(
        Enum(IQCResult), nullable=True
    )
    iqc_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    iqc_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    iqc_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Parent for split batches
    parent_batch_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

    # Purchase order reference
    po_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Children (after split)
    children: Mapped[list["MaterialBatchChild"]] = relationship(
        "MaterialBatchChild", back_populates="parent_batch", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MaterialBatch {self.batch_no}>"


class MaterialBatchChild(Base):
    """Child batch created from split operation."""

    __tablename__ = "material_batch_children"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_batch_id: Mapped[int] = mapped_column(
        ForeignKey("material_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_batch: Mapped["MaterialBatch"] = relationship(
        "MaterialBatch", back_populates="children"
    )

    # Child batch info
    child_batch_no: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    child_qr_code: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Dimensions (may differ after split)
    width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_weight: Mapped[float] = mapped_column(Float, nullable=False)

    # Status
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus), default=BatchStatus.AVAILABLE, nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<MaterialBatchChild {self.child_batch_no}>"


class BatchTransaction(Base):
    """Material batch transaction log for traceability."""

    __tablename__ = "batch_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("material_batches.id"), nullable=False, index=True
    )
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # iqc, split, consume, scrap
    quantity_change: Mapped[float] = mapped_column(Float, nullable=False)  # kg change
    weight_after: Mapped[float] = mapped_column(Float, nullable=False)  # weight after change

    # Reference
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # session, plan, etc.
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<BatchTransaction {self.id}>"
