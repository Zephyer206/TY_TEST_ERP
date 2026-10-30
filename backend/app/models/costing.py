"""Persisted tasks and immutable simple-costing revisions."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CostingTask(Base):
    __tablename__ = 'costing_tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CostingItem(Base):
    __tablename__ = 'costing_items'
    __table_args__ = (UniqueConstraint('task_id', 'alias_id', 'tooling_id', 'scheme_key', name='uq_costing_item_scheme'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('costing_tasks.id'), index=True)
    alias_id: Mapped[int] = mapped_column(ForeignKey('part_customer_aliases.id'))
    part_id: Mapped[int] = mapped_column(ForeignKey('parts.id'))
    tooling_id: Mapped[int] = mapped_column(ForeignKey('tooling.id'))
    spec_id: Mapped[int | None] = mapped_column(ForeignKey('part_tooling_specs.id'), nullable=True)
    scheme_key: Mapped[str] = mapped_column(String(80))
    source_reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CostingRevision(Base):
    __tablename__ = 'costing_revisions'
    __table_args__ = (
        UniqueConstraint('item_id', 'revision_no', name='uq_costing_revision'),
        UniqueConstraint('item_id', 'request_id', name='uq_costing_request'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('costing_items.id'), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    inputs: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(500), default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
