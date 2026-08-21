"""Review queue for legacy part identity values that lack an explicit customer mapping."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PartIdentityMigrationIssue(Base):
    __tablename__ = "part_identity_migration_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_column: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_review", server_default="pending_review"
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
