"""Part display grouping models for explicit left-right and shared-source groups.

Stage 2: User-confirmed explicit grouping without name-based inference.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GroupType(str, PyEnum):
    """Type of part display group."""

    LEFT_RIGHT = "left_right"  # Left/right part pair
    SHARED_SOURCE = "shared_source"  # Shared material/spec from merged Excel cells


class PartDisplayGroupDef(Base):
    """User-confirmed part display group definition.

    Groups are created explicitly by LV2+ users, not inferred from names/suffixes.
    Each group has a type (left_right or shared_source) and a list of member parts.
    """

    __tablename__ = "part_display_group_defs"
    __table_args__ = (
        CheckConstraint(
            "group_type IN ('left_right', 'shared_source')",
            name="ck_part_display_group_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Group metadata
    group_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    group_key: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True,
        comment="Stable display key for frontend rendering"
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Optional user-friendly name for the group"
    )

    # Audit metadata (read-only source references)
    source_sheet: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Source Excel sheet name (read-only metadata)"
    )
    source_rows: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Source Excel row numbers (read-only metadata)"
    )

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit trail
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    members: Mapped[list["PartDisplayGroupMember"]] = relationship(
        "PartDisplayGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<PartDisplayGroupDef {self.group_key} type={self.group_type}>"


class PartDisplayGroupMember(Base):
    """Member of a part display group.

    Links a part to a display group. A part can belong to at most one active group.
    Position is required for left_right groups, optional for shared_source groups.
    """

    __tablename__ = "part_display_group_members"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Group reference
    group_id: Mapped[int] = mapped_column(
        ForeignKey("part_display_group_defs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Part reference
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Position within group (required for left_right, optional for shared_source)
    position: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="left/right for left_right groups, mold variant for shared_source"
    )

    # Display sequence
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Display order within group (0=first)"
    )

    # Audit metadata (read-only source reference)
    source_row: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Source Excel row number (read-only metadata)"
    )

    # Audit trail
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    group: Mapped["PartDisplayGroupDef"] = relationship(
        "PartDisplayGroupDef",
        back_populates="members"
    )

    __table_args__ = (
        # A part can appear in only one active group
        UniqueConstraint('part_id', name='uq_part_display_group_member_part'),
    )

    def __repr__(self) -> str:
        return f"<PartDisplayGroupMember group_id={self.group_id} part_id={self.part_id}>"


class SharedFieldGroupDef(Base):
    """Shared/merged field group definition for parts with common material/TWP.

    Represents a set of parts that share material and/or TWP specifications,
    typically due to merged Excel cells. Created explicitly by users, not inferred.
    """

    __tablename__ = "shared_field_group_defs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Group metadata
    group_key: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True,
        comment="Stable key for field sharing scope"
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )

    # Shared field flags (what this group actually shares)
    shares_material: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    shares_thickness: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    shares_width: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    shares_pitch: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    shares_cavity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Audit metadata (read-only source reference)
    source_sheet: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Source Excel sheet name (read-only metadata)"
    )
    source_rows: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Source Excel row numbers (read-only metadata)"
    )

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit trail
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    members: Mapped[list["SharedFieldGroupMember"]] = relationship(
        "SharedFieldGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<SharedFieldGroupDef {self.group_key}>"


class SharedFieldGroupMember(Base):
    """Member of a shared field group.

    Links a part or tooling to a shared field group. Members inherit shared
    specifications from the group definition.
    """

    __tablename__ = "shared_field_group_members"
    __table_args__ = (
        CheckConstraint(
            "part_id IS NOT NULL OR tooling_id IS NOT NULL",
            name="ck_shared_field_group_member_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Group reference
    group_id: Mapped[int] = mapped_column(
        ForeignKey("shared_field_group_defs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Target references (at least one must be set)
    part_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    tooling_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tooling.id", ondelete="CASCADE"),
        nullable=True, index=True
    )

    # Audit metadata (read-only source reference)
    source_row: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Source Excel row number (read-only metadata)"
    )

    # Audit trail
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    group: Mapped["SharedFieldGroupDef"] = relationship(
        "SharedFieldGroupDef",
        back_populates="members"
    )

    def __repr__(self) -> str:
        return f"<SharedFieldGroupMember group_id={self.group_id} part={self.part_id} tooling={self.tooling_id}>"
