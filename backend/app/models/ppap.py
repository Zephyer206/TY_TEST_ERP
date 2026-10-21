"""Customer PPAP archives; immutable source versions and submission snapshots."""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSON_DATA = JSON().with_variant(JSONB(), 'postgresql')


class PpapArchive(Base):
    __tablename__ = 'ppap_archives'
    __table_args__ = (CheckConstraint("company IN ('tianyue','gaibo')", name='ck_ppap_company'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    company: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    record_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    customer_key: Mapped[str] = mapped_column(String(80), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    planned_date: Mapped[Optional[date]] = mapped_column(Date)
    remark: Mapped[str] = mapped_column(Text, nullable=False, default='')
    links: Mapped[list] = mapped_column(JSON_DATA, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class PpapFolder(Base):
    __tablename__ = 'ppap_folders'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    archive_id: Mapped[str] = mapped_column(ForeignKey('ppap_archives.id'), nullable=False, index=True)
    parent_id: Mapped[Optional[str]] = mapped_column(ForeignKey('ppap_folders.id'))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    __table_args__ = (Index('uq_ppap_folder_sibling', archive_id, func.coalesce(parent_id, ''), func.lower(name), unique=True),)


class PpapDocument(Base):
    __tablename__ = 'ppap_documents'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    archive_id: Mapped[str] = mapped_column(ForeignKey('ppap_archives.id'), nullable=False, index=True)
    folder_id: Mapped[Optional[str]] = mapped_column(ForeignKey('ppap_folders.id'))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    linked_key: Mapped[Optional[str]] = mapped_column(String(80))
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (Index('uq_ppap_document_sibling', archive_id, func.coalesce(folder_id, ''), func.lower(name), unique=True),)


class PpapFileVersion(Base):
    __tablename__ = 'ppap_file_versions'
    __table_args__ = (UniqueConstraint('document_id', 'version', name='uq_ppap_document_version'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('ppap_documents.id'), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    extension: Mapped[str] = mapped_column(String(10), nullable=False)
    sheets: Mapped[list] = mapped_column(JSON_DATA, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class PpapSubmission(Base):
    __tablename__ = 'ppap_submissions'
    __table_args__ = (UniqueConstraint('archive_id', 'round_no', name='uq_ppap_submission_round'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    archive_id: Mapped[str] = mapped_column(ForeignKey('ppap_archives.id'), nullable=False, index=True)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='submitted')
    feedback: Mapped[str] = mapped_column(Text, nullable=False, default='')
    approved_date: Mapped[Optional[date]] = mapped_column(Date)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    conditions: Mapped[str] = mapped_column(Text, nullable=False, default='')
    evidence_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey('ppap_file_versions.id'))
    snapshot: Mapped[dict] = mapped_column(JSON_DATA, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class PpapAuditLog(Base):
    __tablename__ = 'ppap_audit_logs'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    archive_id: Mapped[str] = mapped_column(ForeignKey('ppap_archives.id'), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON_DATA, nullable=False, default=dict)
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
