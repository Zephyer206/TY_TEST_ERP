"""Persistent customer inquiry records and their uploaded review files."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomerInquiry(Base):
    __tablename__ = "customer_inquiries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inquiry_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False, default="待命名项目")
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="报价中")
    technical_review: Mapped[str] = mapped_column(String(40), nullable=False, default="待评审", index=True)
    technical_review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technical_data: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    owner_name: Mapped[str] = mapped_column(String(100), nullable=False, default="待分配")
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomerInquiryAttachment(Base):
    __tablename__ = "customer_inquiry_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inquiry_id: Mapped[int] = mapped_column(ForeignKey("customer_inquiries.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
