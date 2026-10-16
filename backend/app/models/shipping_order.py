"""Shipping order workflow models."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ShippingOrder(Base):
    __tablename__ = "shipping_orders"
    __table_args__ = (
        Index("ix_shipping_orders_status_created", "status", "created_at"),
        Index("ix_shipping_orders_customer_po", "customer_id", "po_no"),
        Index("ix_shipping_orders_draft_cleanup", "status", "last_modified_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False, default="formal", server_default="formal")
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    temporary_customer_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    po_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", server_default="draft", index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    lines: Mapped[list["ShippingOrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan", order_by="ShippingOrderLine.id")
    shipments: Mapped[list["ShippingShipment"]] = relationship(back_populates="order", cascade="all, delete-orphan", order_by="ShippingShipment.confirmed_at")


class ShippingOrderLine(Base):
    __tablename__ = "shipping_order_lines"
    __table_args__ = (
        Index("ix_shipping_order_lines_order_status", "order_id", "status"),
        Index("ix_shipping_order_lines_alias", "part_customer_alias_id"),
        Index("ix_shipping_order_lines_planned_date", "planned_ship_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("shipping_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    part_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parts.id"), nullable=True, index=True)
    part_customer_alias_id: Mapped[Optional[int]] = mapped_column(ForeignKey("part_customer_aliases.id"), nullable=True)
    customer_part_no_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    part_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    ordered_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_ship_date: Mapped[date] = mapped_column(Date, nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False, default="draft", server_default="draft", index=True)
    cancelled_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    order: Mapped[ShippingOrder] = relationship(back_populates="lines")
    label_confirmation: Mapped[Optional["ShippingLabelConfirmation"]] = relationship(back_populates="line", uselist=False, cascade="all, delete-orphan")
    cancellation_consents: Mapped[list["ShippingCancellationConsent"]] = relationship(back_populates="line", cascade="all, delete-orphan")
    shipment_lines: Mapped[list["ShippingShipmentLine"]] = relationship(back_populates="order_line")


class ShippingLabelConfirmation(Base):
    __tablename__ = "shipping_label_confirmations"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("shipping_order_lines.id", ondelete="CASCADE"), nullable=False, unique=True)
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line: Mapped[ShippingOrderLine] = relationship(back_populates="label_confirmation")


class ShippingCancellationConsent(Base):
    __tablename__ = "shipping_cancellation_consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("shipping_order_lines.id", ondelete="CASCADE"), nullable=False, index=True)
    cancel_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    business_confirmed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    business_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    label_confirmed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    label_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    line: Mapped[ShippingOrderLine] = relationship(back_populates="cancellation_consents")


class ShippingShipment(Base):
    __tablename__ = "shipping_shipments"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("shipping_orders.id"), nullable=False, index=True)
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    production_batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order: Mapped[ShippingOrder] = relationship(back_populates="shipments")
    lines: Mapped[list["ShippingShipmentLine"]] = relationship(back_populates="shipment", cascade="all, delete-orphan")
    logistics: Mapped[list["ShippingLogistics"]] = relationship(back_populates="shipment", cascade="all, delete-orphan")


class ShippingShipmentLine(Base):
    __tablename__ = "shipping_shipment_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipping_shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("shipping_order_lines.id"), nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    shipment: Mapped[ShippingShipment] = relationship(back_populates="lines")
    order_line: Mapped[ShippingOrderLine] = relationship(back_populates="shipment_lines")


class ShippingLogistics(Base):
    __tablename__ = "shipping_logistics"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipping_shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    carrier_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tracking_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    shipment: Mapped[ShippingShipment] = relationship(back_populates="logistics")
