"""Customer-first gaibo after-sales archive models."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GaiboAfterSalesCustomer(Base):
    """Customer master data owned exclusively by the after-sales company."""

    __tablename__ = "gaibo_after_sales_customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace: Mapped["GaiboCustomerWorkspace"] = relationship(back_populates="after_sales_customer", uselist=False)


class GaiboCustomerWorkspace(Base):
    __tablename__ = "gaibo_customer_workspaces"
    __table_args__ = (UniqueConstraint("after_sales_customer_id", name="uq_gaibo_workspace_after_sales_customer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    after_sales_customer_id: Mapped[int] = mapped_column(ForeignKey("gaibo_after_sales_customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    field_labels: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    extra_field_definitions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    default_view_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    column_config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    after_sales_customer: Mapped[GaiboAfterSalesCustomer] = relationship(back_populates="workspace")
    requirements: Mapped[list["GaiboCustomerRequirement"]] = relationship(back_populates="workspace")
    packages: Mapped[list["GaiboInstallationPackage"]] = relationship(back_populates="workspace")
    change_logs: Mapped[list["GaiboChangeLog"]] = relationship(back_populates="workspace")


class GaiboViewPreference(Base):
    __tablename__ = "gaibo_view_preferences"
    __table_args__ = (UniqueConstraint("user_id", "view_key", name="uq_gaibo_view_preference_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    view_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class GaiboSinglePart(Base):
    __tablename__ = "gaibo_single_parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parts.id", ondelete="SET NULL"), nullable=True, index=True)
    tianyue_internal_part_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    drawing_reference: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    requirements: Mapped[list["GaiboCustomerRequirement"]] = relationship(back_populates="single_part")


class GaiboCustomerRequirement(Base):
    __tablename__ = "gaibo_customer_requirements"
    __table_args__ = (
        UniqueConstraint("workspace_id", "single_part_id", "customer_part_number", name="uq_gaibo_customer_requirement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("gaibo_customer_workspaces.id", ondelete="RESTRICT"), nullable=False, index=True)
    single_part_id: Mapped[int] = mapped_column(ForeignKey("gaibo_single_parts.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_part_number: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    ibi: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    tianyue_internal_composition: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace: Mapped[GaiboCustomerWorkspace] = relationship(back_populates="requirements")
    single_part: Mapped[GaiboSinglePart] = relationship(back_populates="requirements")
    drawings: Mapped[list["GaiboDrawing"]] = relationship(back_populates="requirement", cascade="all, delete-orphan")
    process_routes: Mapped[list["GaiboProcessRoute"]] = relationship(back_populates="requirement", cascade="all, delete-orphan")
    documents: Mapped[list["GaiboDocumentStatus"]] = relationship(back_populates="requirement", cascade="all, delete-orphan")
    package_items: Mapped[list["GaiboPackageItem"]] = relationship(back_populates="requirement")


class GaiboInstallationPackage(Base):
    __tablename__ = "gaibo_installation_packages"
    __table_args__ = (UniqueConstraint("workspace_id", "package_number", name="uq_gaibo_package_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("gaibo_customer_workspaces.id", ondelete="RESTRICT"), nullable=False, index=True)
    package_number: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    d_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tianyue_pn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace: Mapped[GaiboCustomerWorkspace] = relationship(back_populates="packages")
    items: Mapped[list["GaiboPackageItem"]] = relationship(back_populates="package", cascade="all, delete-orphan", order_by="GaiboPackageItem.sequence")
    documents: Mapped[list["GaiboDocumentStatus"]] = relationship(back_populates="package", cascade="all, delete-orphan")

    @property
    def price_mismatch(self) -> bool:
        """Whether the imported FMG price differs from the FCA source price."""
        pricing = (self.source_data or {}).get("legacy_pricing") or {}
        return pricing.get("price_mismatch") is True


class GaiboPackageItem(Base):
    __tablename__ = "gaibo_package_items"
    __table_args__ = (
        UniqueConstraint("package_id", "sequence", name="uq_gaibo_package_item_sequence"),
        CheckConstraint(
            "requirement_id IS NOT NULL OR unlinked_customer_part_number IS NOT NULL OR ibi IS NULL",
            name="ck_gaibo_package_item_reference",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("gaibo_installation_packages.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id: Mapped[Optional[int]] = mapped_column(ForeignKey("gaibo_customer_requirements.id", ondelete="SET NULL"), nullable=True, index=True)
    unlinked_customer_part_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Some authoritative Excel rows contain the Tianyue internal composition
    # but no IBI yet. Preserve that source value and mark the item as pending.
    ibi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tianyue_internal_composition: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    match_state: Mapped[str] = mapped_column(String(20), nullable=False, default="unlinked")
    status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    package: Mapped[GaiboInstallationPackage] = relationship(back_populates="items")
    requirement: Mapped[Optional[GaiboCustomerRequirement]] = relationship(back_populates="package_items")


class GaiboDrawing(Base):
    __tablename__ = "gaibo_drawings"
    __table_args__ = (UniqueConstraint("requirement_id", "version", name="uq_gaibo_drawing_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("gaibo_customer_requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_started")
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    requirement: Mapped[GaiboCustomerRequirement] = relationship(back_populates="drawings")


class GaiboProcessRoute(Base):
    __tablename__ = "gaibo_process_routes"
    __table_args__ = (UniqueConstraint("requirement_id", "version", name="uq_gaibo_route_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("gaibo_customer_requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    requirement: Mapped[GaiboCustomerRequirement] = relationship(back_populates="process_routes")
    steps: Mapped[list["GaiboProcessStep"]] = relationship(back_populates="route", cascade="all, delete-orphan", order_by="GaiboProcessStep.sequence")


class GaiboProcessStep(Base):
    __tablename__ = "gaibo_process_steps"
    __table_args__ = (UniqueConstraint("route_id", "sequence", name="uq_gaibo_process_step_sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("gaibo_process_routes.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_name: Mapped[str] = mapped_column(String(200), nullable=False)
    machine_id: Mapped[Optional[int]] = mapped_column(ForeignKey("machines.id", ondelete="SET NULL"), nullable=True)
    tooling_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tooling.id", ondelete="SET NULL"), nullable=True)
    key_parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    quality_checkpoints: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    route: Mapped[GaiboProcessRoute] = relationship(back_populates="steps")


class GaiboDocumentStatus(Base):
    __tablename__ = "gaibo_document_statuses"
    __table_args__ = (
        CheckConstraint(
            "(requirement_id IS NOT NULL AND package_id IS NULL) OR (requirement_id IS NULL AND package_id IS NOT NULL)",
            name="ck_gaibo_document_owner",
        ),
        Index(
            "uq_gaibo_document_requirement_type",
            "requirement_id",
            "document_type",
            unique=True,
            postgresql_where=text("requirement_id IS NOT NULL"),
        ),
        Index(
            "uq_gaibo_document_package_type",
            "package_id",
            "document_type",
            unique=True,
            postgresql_where=text("package_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[Optional[int]] = mapped_column(ForeignKey("gaibo_customer_requirements.id", ondelete="CASCADE"), nullable=True, index=True)
    package_id: Mapped[Optional[int]] = mapped_column(ForeignKey("gaibo_installation_packages.id", ondelete="CASCADE"), nullable=True, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_started")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    concluded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    requirement: Mapped[Optional[GaiboCustomerRequirement]] = relationship(back_populates="documents")
    package: Mapped[Optional[GaiboInstallationPackage]] = relationship(back_populates="documents")


class GaiboChangeLog(Base):
    __tablename__ = "gaibo_change_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("gaibo_customer_workspaces.id", ondelete="RESTRICT"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    change_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    workspace: Mapped[GaiboCustomerWorkspace] = relationship(back_populates="change_logs")
