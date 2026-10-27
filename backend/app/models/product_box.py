"""Product-box traceability foundation; services own the business transactions.

New records use timezone-aware timestamps and restrictive foreign keys. Existing
integer identifiers are kept as integer FKs; new domain identifiers are bigint.
"""
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
    ForeignKeyConstraint, Identity, Index, Integer, String, Text,
    UniqueConstraint, false, func, text, true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class _Record:
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class _Version:
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1)


class ProductRouteRevision(_Record, Base):
    __tablename__ = "product_route_revisions"
    __table_args__ = (
        UniqueConstraint("route_code", "revision", name="uq_pfb_route_revision"),
        UniqueConstraint("id", "product_code", name="uq_pfb_route_product"),
        CheckConstraint("revision >= 1", name="ck_pfb_route_revision"),
        CheckConstraint("product_code IN ('B','C')", name="ck_pfb_route_product"),
        CheckConstraint("jsonb_typeof(steps_json) = 'array' AND jsonb_array_length(steps_json) > 0",
                        name="ck_pfb_route_steps"),
    )
    route_code: Mapped[str] = mapped_column(String(80))
    revision: Mapped[int] = mapped_column(Integer)
    product_code: Mapped[str] = mapped_column(String(40))
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    first_output_process_code: Mapped[str] = mapped_column(String(50))
    is_published: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class ProductOrderContext(_Record, _Version, Base):
    __tablename__ = "product_order_contexts"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_pfb_order_context_version"),)
    order_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"), unique=True)
    business_owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    configured_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductOrderProduct(_Record, _Version, Base):
    __tablename__ = "product_order_products"
    __table_args__ = (
        UniqueConstraint("order_id", "part_id", "product_code", name="uq_pfb_order_part"),
        UniqueConstraint("id", "order_id", name="uq_pfb_product_order"),
        UniqueConstraint("id", "order_id", "product_code", name="uq_pfb_product_order_code"),
        UniqueConstraint("id", "order_id", "part_id", "product_code", name="uq_pfb_product_identity"),
        ForeignKeyConstraint(["route_revision_id", "product_code"],
                             ["product_route_revisions.id", "product_route_revisions.product_code"],
                             name="fk_pfb_product_route"),
        ForeignKeyConstraint(["conversion_source_id", "order_id"],
                             ["product_order_products.id", "product_order_products.order_id"],
                             name="fk_pfb_conversion_source"),
        CheckConstraint("target_qty >= 0 AND version >= 1", name="ck_pfb_product_quantity"),
        CheckConstraint("product_code IN ('B','C')", name="ck_pfb_product_code"),
        CheckConstraint("(binding_allowed AND conversion_source_id IS NULL) OR "
                        "(NOT binding_allowed AND conversion_source_id IS NOT NULL AND target_qty = 0)",
                        name="ck_pfb_product_purpose"),
        CheckConstraint("conversion_source_id IS NULL OR conversion_source_id <> id",
                        name="ck_pfb_product_source"),
    )
    order_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"), index=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"))
    product_code: Mapped[str] = mapped_column(String(40))
    target_qty: Mapped[int] = mapped_column(Integer)
    route_revision_id: Mapped[int] = mapped_column(BigInteger)
    binding_allowed: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    conversion_source_id: Mapped[int | None] = mapped_column(BigInteger)
    conversion_authorization: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), default=dict,
    )
    configured_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class MachineOrderProcessState(_Record, _Version, Base):
    __tablename__ = "machine_order_process_states"
    __table_args__ = (
        UniqueConstraint("assignment_id", "order_product_id", "route_revision_id", "process_code",
                         name="uq_pfb_machine_process"),
        CheckConstraint("target_qty >= 0 AND version >= 1", name="ck_pfb_state_quantity"),
        CheckConstraint("production_status IN ('pending','in_progress','completed')",
                        name="ck_pfb_state_status"),
        CheckConstraint("(production_status = 'completed' AND completed_by IS NOT NULL AND completed_at IS NOT NULL)"
                        " OR (production_status <> 'completed' AND completed_by IS NULL AND completed_at IS NULL)",
                        name="ck_pfb_state_completion"),
    )
    assignment_id: Mapped[int] = mapped_column(ForeignKey("plan_machine_assignments.id"), index=True)
    order_product_id: Mapped[int] = mapped_column(ForeignKey("product_order_products.id"), index=True)
    route_revision_id: Mapped[int] = mapped_column(ForeignKey("product_route_revisions.id"))
    process_code: Mapped[str] = mapped_column(String(50))
    target_qty: Mapped[int] = mapped_column(Integer)
    production_status: Mapped[str] = mapped_column(String(20), server_default="pending", default="pending")
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quantity_difference_confirmed: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)


class MachineProductionContext(_Record, _Version, Base):
    __tablename__ = "machine_production_contexts"
    __table_args__ = (
        CheckConstraint("version >= 1 AND expires_at > scanned_at", name="ck_pfb_context_lifetime"),
        Index("ix_pfb_context_user_machine", "user_id", "machine_id", "closed_at"),
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"))
    scan_ticket_digest: Mapped[str] = mapped_column(String(64), unique=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    state_id: Mapped[int | None] = mapped_column(ForeignKey("machine_order_process_states.id"))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completion_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductQrPoolItem(_Record, Base):
    __tablename__ = "product_qr_pool_items"
    __table_args__ = (
        CheckConstraint("payload_version = 'v1'", name="ck_pfb_payload_version"),
        CheckConstraint("pool_status IN ('unused','bound','void')", name="ck_pfb_pool_status"),
        CheckConstraint("print_count >= 0", name="ck_pfb_print_count"),
        Index("ix_pfb_pool_status_created", "pool_status", "created_at"),
    )
    public_code: Mapped[str] = mapped_column(String(80), unique=True)
    payload_version: Mapped[str] = mapped_column(String(16), server_default="v1", default="v1")
    qr_payload: Mapped[str] = mapped_column(String(200), unique=True)
    pool_status: Mapped[str] = mapped_column(String(20), server_default="unused", default="unused")
    print_batch_no: Mapped[str | None] = mapped_column(String(50), index=True)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    print_count: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductBox(_Record, _Version, Base):
    __tablename__ = "product_boxes"
    __table_args__ = (
        UniqueConstraint("id", "order_id", name="uq_pfb_box_order"),
        ForeignKeyConstraint(["order_product_id", "order_id", "part_id", "product_code"],
                             ["product_order_products.id", "product_order_products.order_id",
                              "product_order_products.part_id", "product_order_products.product_code"],
                             name="fk_pfb_box_product"),
        ForeignKeyConstraint(["route_revision_id", "product_code"],
                             ["product_route_revisions.id", "product_route_revisions.product_code"],
                             name="fk_pfb_box_route"),
        CheckConstraint("current_qty >= 0 AND version >= 1", name="ck_pfb_box_quantity"),
        CheckConstraint("product_code IN ('B','C')", name="ck_pfb_box_product"),
        CheckConstraint("lifecycle_status IN ('active','empty','closed','scrapped')", name="ck_pfb_box_lifecycle"),
    )
    qr_pool_item_id: Mapped[int] = mapped_column(ForeignKey("product_qr_pool_items.id"), unique=True)
    box_no: Mapped[str] = mapped_column(String(80), unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"), index=True)
    order_product_id: Mapped[int] = mapped_column(BigInteger)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"))
    product_code: Mapped[str] = mapped_column(String(40))
    product_name_snapshot: Mapped[str] = mapped_column(String(200))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    customer_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    customer_part_no: Mapped[str | None] = mapped_column(String(150))
    route_revision_id: Mapped[int] = mapped_column(BigInteger)
    current_process_code: Mapped[str | None] = mapped_column(String(50))
    next_process_code: Mapped[str | None] = mapped_column(String(50))
    current_qty: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    lifecycle_status: Mapped[str] = mapped_column(String(30), server_default="active", default="active")
    bound_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BoxProcessQuantity(_Record, _Version, Base):
    __tablename__ = "box_process_quantities"
    __table_args__ = (
        UniqueConstraint("state_id", "box_id", name="uq_pfb_state_box"),
        UniqueConstraint("id", "box_id", name="uq_pfb_quantity_box"),
        CheckConstraint("current_qty >= 0 AND input_qty >= 0 AND version >= 1", name="ck_pfb_process_quantity"),
    )
    state_id: Mapped[int] = mapped_column(ForeignKey("machine_order_process_states.id"))
    box_id: Mapped[int] = mapped_column(ForeignKey("product_boxes.id"), index=True)
    current_qty: Mapped[int] = mapped_column(Integer)
    input_qty: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    material_batch_id: Mapped[int | None] = mapped_column(ForeignKey("material_batches.id"))
    source_quantity_id: Mapped[int | None] = mapped_column(ForeignKey("box_process_quantities.id"))
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductOutputAllocation(_Record, _Version, Base):
    __tablename__ = "product_output_allocations"
    __table_args__ = (
        ForeignKeyConstraint(["source_quantity_id", "box_id"],
                             ["box_process_quantities.id", "box_process_quantities.box_id"],
                             name="fk_pfb_allocation_source"),
        ForeignKeyConstraint(["order_product_id", "order_id"],
                             ["product_order_products.id", "product_order_products.order_id"],
                             name="fk_pfb_allocation_order"),
        CheckConstraint("available_qty >= 0 AND remaining_order_qty_snapshot >= 0 AND order_qty >= 0 "
                        "AND stock_qty >= 0 AND order_qty + stock_qty = available_qty AND version >= 1",
                        name="ck_pfb_allocation_quantity"),
    )
    source_quantity_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"), index=True)
    order_product_id: Mapped[int] = mapped_column(BigInteger)
    box_id: Mapped[int] = mapped_column(ForeignKey("product_boxes.id"))
    origin_allocation_id: Mapped[int | None] = mapped_column(ForeignKey("product_output_allocations.id"))
    available_qty: Mapped[int] = mapped_column(Integer)
    remaining_order_qty_snapshot: Mapped[int] = mapped_column(Integer)
    order_qty: Mapped[int] = mapped_column(Integer)
    stock_qty: Mapped[int] = mapped_column(Integer)
    manually_adjusted: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductFlowEvent(_Record, Base):
    __tablename__ = "product_flow_events"
    __table_args__ = (
        CheckConstraint("before_qty >= 0 AND after_qty >= 0 AND box_version >= 1", name="ck_pfb_event_quantity"),
        CheckConstraint("event_type IN ('bind','scan','qty_save','quantity_correction','metadata_edit',"
                        "'process_start','process_complete','split','cross_order_split','allocation',"
                        "'conversion','exception','resume')", name="ck_pfb_event_type"),
        Index("ix_pfb_event_box_time", "product_box_id", "occurred_at", "id"),
        Index("ix_pfb_event_order_time", "order_id", "occurred_at"),
        Index("ix_pfb_event_machine_time", "machine_id", "occurred_at"),
    )
    product_box_id: Mapped[int] = mapped_column(ForeignKey("product_boxes.id"))
    event_type: Mapped[str] = mapped_column(String(40))
    process_code: Mapped[str | None] = mapped_column(String(50))
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machines.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"))
    order_product_id: Mapped[int] = mapped_column(ForeignKey("product_order_products.id"))
    state_id: Mapped[int | None] = mapped_column(ForeignKey("machine_order_process_states.id"))
    context_id: Mapped[int | None] = mapped_column(ForeignKey("machine_production_contexts.id"))
    material_batch_id: Mapped[int | None] = mapped_column(ForeignKey("material_batches.id"))
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    before_qty: Mapped[int] = mapped_column(Integer)
    after_qty: Mapped[int] = mapped_column(Integer)
    box_version: Mapped[int] = mapped_column(Integer)
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), default=dict)
    after_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), default=dict)
    status: Mapped[str] = mapped_column(String(30), server_default="recorded", default="recorded")
    remark: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductBoxRelation(_Record, Base):
    __tablename__ = "product_box_relations"
    __table_args__ = (
        ForeignKeyConstraint(["parent_box_id", "source_order_id"],
                             ["product_boxes.id", "product_boxes.order_id"], name="fk_pfb_relation_source_box"),
        ForeignKeyConstraint(["child_box_id", "target_order_id"],
                             ["product_boxes.id", "product_boxes.order_id"], name="fk_pfb_relation_target_box"),
        ForeignKeyConstraint(["source_order_product_id", "source_order_id", "source_product_code"],
                             ["product_order_products.id", "product_order_products.order_id",
                              "product_order_products.product_code"], name="fk_pfb_relation_source_product"),
        ForeignKeyConstraint(["target_order_product_id", "target_order_id", "target_product_code"],
                             ["product_order_products.id", "product_order_products.order_id",
                              "product_order_products.product_code"], name="fk_pfb_relation_target_product"),
        CheckConstraint("parent_box_id <> child_box_id", name="ck_pfb_relation_distinct"),
        CheckConstraint("quantity > 0 AND order_qty >= 0 AND stock_qty >= 0 AND order_qty + stock_qty = quantity",
                        name="ck_pfb_relation_quantity"),
        CheckConstraint("relation_type IN ('split','cross_order_split','partial_conversion')", name="ck_pfb_relation_type"),
        CheckConstraint("(relation_type = 'cross_order_split' AND source_order_id <> target_order_id) OR "
                        "(relation_type <> 'cross_order_split' AND source_order_id = target_order_id)",
                        name="ck_pfb_relation_orders"),
    )
    parent_box_id: Mapped[int] = mapped_column(ForeignKey("product_boxes.id"), index=True)
    child_box_id: Mapped[int] = mapped_column(ForeignKey("product_boxes.id"), unique=True)
    relation_type: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[int] = mapped_column(Integer)
    source_product_code: Mapped[str] = mapped_column(String(40))
    target_product_code: Mapped[str] = mapped_column(String(40))
    source_order_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"), index=True)
    target_order_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"), index=True)
    source_order_product_id: Mapped[int] = mapped_column(ForeignKey("product_order_products.id"))
    target_order_product_id: Mapped[int] = mapped_column(ForeignKey("product_order_products.id"))
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    order_qty: Mapped[int] = mapped_column(Integer)
    stock_qty: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class CoilSpecException(_Record, _Version, Base):
    __tablename__ = "coil_spec_exceptions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_pfb_exception_version"),
        CheckConstraint("status IN ('pending_confirmation','confirmed')", name="ck_pfb_exception_status"),
        CheckConstraint("resolution IS NULL OR resolution IN ('accept_continue','pause','reconfirm_coil')",
                        name="ck_pfb_exception_resolution"),
        CheckConstraint("(status = 'confirmed' AND resolution IS NOT NULL AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)"
                        " OR (status = 'pending_confirmation' AND resolution IS NULL AND confirmed_by IS NULL AND confirmed_at IS NULL)",
                        name="ck_pfb_exception_confirmation"),
        CheckConstraint("(released_at IS NULL AND released_by IS NULL) OR "
                        "(released_at IS NOT NULL AND released_by IS NOT NULL AND resume_reason IS NOT NULL "
                        "AND rechecked_material_batch_id IS NOT NULL AND status = 'confirmed' "
                        "AND resolution IN ('pause','reconfirm_coil'))", name="ck_pfb_exception_resume"),
        Index("uq_pfb_active_exception", "active_dedupe_key", unique=True,
              postgresql_where=text("released_at IS NULL")),
    )
    order_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"), index=True)
    product_box_id: Mapped[int | None] = mapped_column(ForeignKey("product_boxes.id"))
    state_id: Mapped[int] = mapped_column(ForeignKey("machine_order_process_states.id"), index=True)
    material_batch_id: Mapped[int] = mapped_column(ForeignKey("material_batches.id"))
    expected_spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    actual_spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    active_dedupe_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), server_default="pending_confirmation", default="pending_confirmation")
    resolution: Mapped[str | None] = mapped_column(String(30))
    remark: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resume_reason: Mapped[str | None] = mapped_column(Text)
    rechecked_material_batch_id: Mapped[int | None] = mapped_column(ForeignKey("material_batches.id"))


class ProductConversionRecord(_Record, _Version, Base):
    __tablename__ = "product_conversion_records"
    __table_args__ = (
        ForeignKeyConstraint(["source_order_product_id", "order_id", "source_product_code"],
                             ["product_order_products.id", "product_order_products.order_id",
                              "product_order_products.product_code"], name="fk_pfb_conversion_source_product"),
        ForeignKeyConstraint(["target_order_product_id", "order_id", "target_product_code"],
                             ["product_order_products.id", "product_order_products.order_id",
                              "product_order_products.product_code"], name="fk_pfb_conversion_target_product"),
        CheckConstraint("source_product_code IN ('B','C') AND target_product_code IN ('B','C') "
                        "AND source_product_code <> target_product_code", name="ck_pfb_conversion_direction"),
        CheckConstraint("trigger_type IN ('manual','pre_authorized','exception')", name="ck_pfb_conversion_trigger"),
        CheckConstraint("version >= 1 AND (proposed_qty IS NULL OR proposed_qty > 0)", name="ck_pfb_conversion_version"),
        CheckConstraint("confirmation_status IN ('pending_operator_confirmation','confirmed','cancelled')",
                        name="ck_pfb_conversion_status"),
        CheckConstraint("(confirmation_status = 'confirmed' AND actual_qty > 0 AND actual_qty IS NOT NULL "
                        "AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL AND cancelled_at IS NULL AND cancelled_by IS NULL) OR "
                        "(confirmation_status = 'cancelled' AND actual_qty IS NULL AND confirmed_by IS NULL AND confirmed_at IS NULL "
                        "AND cancelled_by IS NOT NULL AND cancelled_at IS NOT NULL) OR "
                        "(confirmation_status = 'pending_operator_confirmation' AND actual_qty IS NULL AND confirmed_by IS NULL "
                        "AND confirmed_at IS NULL AND cancelled_by IS NULL AND cancelled_at IS NULL)",
                        name="ck_pfb_conversion_confirmation"),
    )
    product_box_id: Mapped[int] = mapped_column(ForeignKey("product_boxes.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"))
    source_order_product_id: Mapped[int] = mapped_column(ForeignKey("product_order_products.id"))
    target_order_product_id: Mapped[int] = mapped_column(ForeignKey("product_order_products.id"))
    source_product_code: Mapped[str] = mapped_column(String(40))
    target_product_code: Mapped[str] = mapped_column(String(40))
    source_process_code: Mapped[str | None] = mapped_column(String(50))
    target_process_code: Mapped[str | None] = mapped_column(String(50))
    proposed_qty: Mapped[int | None] = mapped_column(Integer)
    actual_qty: Mapped[int | None] = mapped_column(Integer)
    trigger_type: Mapped[str] = mapped_column(String(30))
    confirmation_status: Mapped[str] = mapped_column(String(40), server_default="pending_operator_confirmation",
                                                   default="pending_operator_confirmation")
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    relation_id: Mapped[int | None] = mapped_column(ForeignKey("product_box_relations.id"), unique=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    remark: Mapped[str | None] = mapped_column(Text)


class QrCapabilitySet(_Version, Base):
    __tablename__ = "qr_capability_sets"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_pfb_capability_version"),)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)


class QrCapabilityGrant(_Record, Base):
    __tablename__ = "qr_capability_grants"
    __table_args__ = (
        CheckConstraint("(revoked_at IS NULL AND revoked_by IS NULL) OR "
                        "(revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revoked_at >= granted_at)",
                        name="ck_pfb_capability_revocation"),
        Index("uq_pfb_active_capability", "user_id", "capability", unique=True,
              postgresql_where=text("revoked_at IS NULL")),
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    capability: Mapped[str] = mapped_column(String(80))
    granted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QrPrintJob(_Record, Base):
    __tablename__ = "qr_print_jobs"
    __table_args__ = (
        CheckConstraint("request_type IN ('initial','reprint')", name="ck_pfb_print_request"),
        UniqueConstraint("id", "requested_by", name="uq_pfb_print_job_requester"),
    )
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    template_code: Mapped[str] = mapped_column(String(50))
    request_type: Mapped[str] = mapped_column(String(20))


class QrPrintJobItem(_Record, Base):
    __tablename__ = "qr_print_job_items"
    __table_args__ = (UniqueConstraint("job_id", "pool_item_id", name="uq_pfb_print_job_item"),)
    job_id: Mapped[int] = mapped_column(ForeignKey("qr_print_jobs.id"))
    pool_item_id: Mapped[int] = mapped_column(ForeignKey("product_qr_pool_items.id"))
    display_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)


class QrPrintConfirmation(_Record, Base):
    __tablename__ = "qr_print_confirmations"
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "confirmed_by"],
                             ["qr_print_jobs.id", "qr_print_jobs.requested_by"], name="fk_pfb_print_requester"),
        UniqueConstraint("job_id", "pool_item_id", name="uq_pfb_print_confirmation"),
        ForeignKeyConstraint(["job_id", "pool_item_id"],
                             ["qr_print_job_items.job_id", "qr_print_job_items.pool_item_id"],
                             name="fk_pfb_print_confirmation_item"),
    )
    job_id: Mapped[int] = mapped_column(BigInteger)
    pool_item_id: Mapped[int] = mapped_column(BigInteger)
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QrIdempotencyRecord(_Record, Base):
    __tablename__ = "qr_idempotency_records"
    __table_args__ = (
        UniqueConstraint("operator_id", "action", "entity_key", "request_key", name="uq_pfb_idempotency_scope"),
        CheckConstraint("http_status BETWEEN 100 AND 599", name="ck_pfb_idempotency_http"),
    )
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    entity_key: Mapped[str] = mapped_column(String(120))
    request_key: Mapped[str] = mapped_column(String(120))
    request_digest: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    http_status: Mapped[int] = mapped_column(Integer)


class ExceptionRecipientGroup(_Record, Base):
    __tablename__ = "exception_recipient_groups"
    __table_args__ = (
        UniqueConstraint("exception_id", "group_type", name="uq_pfb_exception_group"),
        CheckConstraint("group_type IN ('supervisor','business_owner')", name="ck_pfb_recipient_group"),
        CheckConstraint("resolution_status IN ('pending_configuration','resolved')", name="ck_pfb_recipient_resolution"),
        CheckConstraint("jsonb_typeof(recipient_ids) = 'array'", name="ck_pfb_recipient_ids"),
        CheckConstraint("(resolution_status = 'pending_configuration' AND resolved_at IS NULL) OR "
                        "(resolution_status = 'resolved' AND resolved_at IS NOT NULL AND jsonb_array_length(recipient_ids) > 0)",
                        name="ck_pfb_recipient_resolved"),
    )
    exception_id: Mapped[int] = mapped_column(ForeignKey("coil_spec_exceptions.id"))
    group_type: Mapped[str] = mapped_column(String(30))
    resolution_status: Mapped[str] = mapped_column(String(30), server_default="pending_configuration",
                                                 default="pending_configuration")
    recipient_ids: Mapped[list[int]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), default=list)
    missing_reason: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationOutbox(_Record, _Version, Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        UniqueConstraint("id", "recipient_user_id", name="uq_pfb_outbox_recipient"),
        CheckConstraint("status IN ('pending','sent','failed')", name="ck_pfb_delivery_status"),
        CheckConstraint("attempts BETWEEN 0 AND 5 AND retry_batch >= 0 AND version >= 1", name="ck_pfb_delivery_attempts"),
        CheckConstraint("(status = 'sent' AND sent_at IS NOT NULL AND attempts >= 1) OR "
                        "(status <> 'sent' AND sent_at IS NULL)", name="ck_pfb_delivery_sent"),
        Index("ix_pfb_outbox_due", "status", "next_retry_at"),
    )
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    exception_id: Mapped[int] = mapped_column(ForeignKey("coil_spec_exceptions.id"))
    event_type: Mapped[str] = mapped_column(String(50))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), server_default="pending", default="pending")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    retry_batch: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(String(80))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QrNotification(_Record, Base):
    __tablename__ = "qr_notifications"
    __table_args__ = (
        ForeignKeyConstraint(["outbox_id", "recipient_user_id"],
                             ["notification_outbox.id", "notification_outbox.recipient_user_id"],
                             name="fk_pfb_notification_recipient"),
    )
    outbox_id: Mapped[int] = mapped_column(ForeignKey("notification_outbox.id"), unique=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QrNotificationAttempt(_Record, Base):
    __tablename__ = "qr_notification_attempts"
    __table_args__ = (
        UniqueConstraint("outbox_id", "retry_batch", "attempt_no", name="uq_pfb_delivery_attempt"),
        CheckConstraint("retry_batch >= 0 AND attempt_no BETWEEN 1 AND 5", name="ck_pfb_attempt_number"),
        CheckConstraint("trigger_type IN ('automatic','manual') AND result IN ('sent','failed')", name="ck_pfb_attempt_result"),
    )
    outbox_id: Mapped[int] = mapped_column(ForeignKey("notification_outbox.id"))
    retry_batch: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    attempt_no: Mapped[int] = mapped_column(Integer)
    trigger_type: Mapped[str] = mapped_column(String(20))
    result: Mapped[str] = mapped_column(String(20))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))


DOMAIN_TABLES = tuple(
    cls.__table__ for cls in (
        ProductRouteRevision, ProductOrderContext, ProductOrderProduct,
        MachineOrderProcessState, MachineProductionContext, ProductQrPoolItem,
        ProductBox, BoxProcessQuantity, ProductOutputAllocation, ProductFlowEvent,
        ProductBoxRelation, CoilSpecException, ProductConversionRecord,
        QrCapabilitySet, QrCapabilityGrant, QrPrintJob, QrPrintJobItem,
        QrPrintConfirmation, QrIdempotencyRecord, ExceptionRecipientGroup,
        NotificationOutbox, QrNotification, QrNotificationAttempt,
    )
)
