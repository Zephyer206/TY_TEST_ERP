"""Persistent project quotation groups and line items."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QuoteGroup(Base):
    __tablename__ = "quote_groups"
    __table_args__ = (UniqueConstraint("inquiry_id", name="uq_quote_groups_inquiry"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    inquiry_id: Mapped[int] = mapped_column(ForeignKey("customer_inquiries.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="待报价")
    quote_path: Mapped[str] = mapped_column(String(60), nullable=False, default="待确定方案")
    tooling_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tooling_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tooling_lead_time: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tooling_life: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    material_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    material_density: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    material_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    material_scrap_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    surface_treatment_fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    inspection_fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    packaging_fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    freight_fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    management_fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    profit_margin: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    material_adjustment: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    quote_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["QuoteGroupItem"]] = relationship(
        "QuoteGroupItem", back_populates="group", cascade="all, delete-orphan", order_by="QuoteGroupItem.sequence"
    )


class QuoteGroupItem(Base):
    __tablename__ = "quote_group_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_group_id: Mapped[int] = mapped_column(ForeignKey("quote_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    customer_part_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    part_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    pair_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    material_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    thickness: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    pitch: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    utilization: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    press_tonnage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cavity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tooling_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tooling_lead_time: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    product_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    annual_usage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifecycle_years: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    technical_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    group: Mapped[QuoteGroup] = relationship("QuoteGroup", back_populates="items")
