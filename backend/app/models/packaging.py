"""Packaging management models."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.part import Part
    from src.models.production import ProductionSession


class PackagingStatus(str, PyEnum):
    """Packaging record status."""

    SCANNED = "scanned"  # Package scanned, in WIP
    INSPECTING = "inspecting"  # Being inspected
    PASSED = "passed"  # Passed inspection, in stock
    REJECTED = "rejected"  # Rejected during inspection
    SHIPPED = "shipped"  # Shipped out


class PackagingRecord(Base):
    """Packaging scan record model."""

    __tablename__ = "packaging_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_no: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # Part info
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Source
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("production_sessions.id"), nullable=True, index=True
    )
    session: Mapped[Optional["ProductionSession"]] = relationship("ProductionSession")

    # Package info
    package_qty: Mapped[int] = mapped_column(Integer, nullable=False)  # Quantity in this package
    box_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Box/barcode number

    # Inspection result
    status: Mapped[PackagingStatus] = mapped_column(
        Enum(PackagingStatus), default=PackagingStatus.SCANNED, nullable=False, index=True
    )

    # Inspection details
    inspected_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inspected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    inspection_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Operator who scanned
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<PackagingRecord {self.package_no}>"


class Inventory(Base):
    """Finished goods inventory model."""

    __tablename__ = "finished_goods_inventory"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Part info
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Inventory quantity
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)

    # Reserved quantity (for orders not yet shipped)
    reserved_qty: Mapped[int] = mapped_column(Integer, default=0)

    # Location
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Last update
    last_update_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_update_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Inventory part={self.part_id} qty={self.stock_qty}>"


class InventoryTransaction(Base):
    """Inventory transaction log for traceability."""

    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)

    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )

    # Transaction type
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: incoming, outgoing, adjustment, reserve, unreserve

    # Quantities
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # Positive for in, negative for out
    stock_before: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_after: Mapped[int] = mapped_column(Integer, nullable=False)

    # Reference
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # e.g., packaging_record, shipment, adjustment
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Reason
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Operator
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<InventoryTransaction {self.id} {self.transaction_type} {self.quantity}>"
