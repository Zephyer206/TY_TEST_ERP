"""After-sales installation kit archive models."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AfterSalesInstallationKit(Base):
    """An installation kit archive imported from the FMG workbook."""

    __tablename__ = "after_sales_installation_kits"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_item_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="installation_kit")
    fmg_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    d_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tianyue_pn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    ibi_spec: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_kit_spec: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    drawing_status: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    sample_status: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    ppap_status: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    source_sheet: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_row: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    components: Mapped[list["AfterSalesKitComponent"]] = relationship(
        back_populates="kit", cascade="all, delete-orphan", order_by="AfterSalesKitComponent.sequence"
    )
    change_logs: Mapped[list["AfterSalesKitChangeLog"]] = relationship(
        back_populates="kit", cascade="all, delete-orphan", order_by="AfterSalesKitChangeLog.created_at"
    )
    component_annotations: Mapped[list["AfterSalesKitComponentAnnotation"]] = relationship(
        back_populates="kit", cascade="all, delete-orphan", order_by="AfterSalesKitComponentAnnotation.sequence"
    )


class AfterSalesKitComponent(Base):
    """A parsed IBI or Tianyue component; raw source text remains authoritative."""

    __tablename__ = "after_sales_kit_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    kit_id: Mapped[int] = mapped_column(
        ForeignKey("after_sales_installation_kits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    part_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    kit: Mapped[AfterSalesInstallationKit] = relationship(back_populates="components")


class AfterSalesKitComponentAnnotation(Base):
    """A user-maintained status for one paired IBI/Tianyue component sequence."""

    __tablename__ = "after_sales_kit_component_annotations"
    __table_args__ = (
        UniqueConstraint("kit_id", "sequence", name="uq_after_sales_kit_component_annotation_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kit_id: Mapped[int] = mapped_column(
        ForeignKey("after_sales_installation_kits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    kit: Mapped[AfterSalesInstallationKit] = relationship(back_populates="component_annotations")


class AfterSalesKitChangeLog(Base):
    """Import and future edit history for an installation kit archive."""

    __tablename__ = "after_sales_kit_change_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kit_id: Mapped[int] = mapped_column(
        ForeignKey("after_sales_installation_kits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    change_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    kit: Mapped[AfterSalesInstallationKit] = relationship(back_populates="change_logs")
