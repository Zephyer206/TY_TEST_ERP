"""Shared nonconforming records; source cells and workflow evidence stay together."""
from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class NonconformingImportBatch(Base):
    __tablename__ = 'nonconforming_import_batches'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NonconformingRecord(Base):
    __tablename__ = 'nonconforming_records'
    __table_args__ = (
        UniqueConstraint('company', 'record_no', name='uq_nc_company_no'),
        CheckConstraint('quantity >= 0', name='ck_nc_quantity'),
        CheckConstraint('revision >= 1', name='ck_nc_revision'),
        CheckConstraint("company IN ('tianyue', 'gaibo')", name='ck_nc_company'),
        CheckConstraint("status IN ('pending_confirmation','pending','processing','inspection','closed')", name='ck_nc_status'),
    )
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    company: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    record_no: Mapped[str] = mapped_column(String(80), nullable=False)
    part_no: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NonconformingReworkMold(Base):
    __tablename__ = 'nonconforming_rework_molds'
    __table_args__ = (CheckConstraint('revision >= 1', name='ck_nc_mold_revision'),)
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    company: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    part_no: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
