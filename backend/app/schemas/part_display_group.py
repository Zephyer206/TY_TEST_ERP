"""Pydantic schemas for explicit part display grouping."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


# ========== Part Display Group Schemas ==========

class PartDisplayGroupMemberCreate(BaseModel):
    """Request to add a part to a display group."""
    part_id: Optional[int] = None
    customer_part_no: Optional[str] = Field(default=None, max_length=150)
    position: Optional[str] = Field(default=None, max_length=20)
    sequence: int = Field(default=0, ge=0)


class PartDisplayGroupMemberResponse(BaseModel):
    """Response for a display group member."""
    id: int
    group_id: int
    part_id: int
    customer_part_no: Optional[str] = None
    part_name: Optional[str] = None
    position: Optional[str] = None
    sequence: int
    source_row: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartDisplayGroupDefCreate(BaseModel):
    """Request to create a new part display group."""
    group_type: str = Field(..., pattern="^(left_right|shared_source)$")
    group_key: str = Field(..., max_length=200)
    display_name: Optional[str] = Field(default=None, max_length=200)
    remark: Optional[str] = None
    members: list[PartDisplayGroupMemberCreate] = Field(default_factory=list)


class PartDisplayGroupDefUpdate(BaseModel):
    """Request to update a part display group."""
    display_name: Optional[str] = Field(default=None, max_length=200)
    is_active: Optional[bool] = None
    remark: Optional[str] = None


class PartDisplayGroupDefResponse(BaseModel):
    """Response for a part display group definition."""
    id: int
    group_type: str
    group_key: str
    display_name: Optional[str] = None
    source_sheet: Optional[str] = None
    source_rows: Optional[str] = None
    is_active: bool
    remark: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_by: Optional[int] = None
    updated_at: datetime
    members: list[PartDisplayGroupMemberResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ========== Shared Field Group Schemas ==========

class SharedFieldGroupMemberCreate(BaseModel):
    """Request to add a member to a shared field group."""
    part_id: Optional[int] = None
    customer_part_no: Optional[str] = Field(default=None, max_length=150)
    tooling_id: Optional[int] = None
    tooling_number: Optional[str] = Field(default=None, max_length=100)


class SharedFieldGroupMemberResponse(BaseModel):
    """Response for a shared field group member."""
    id: int
    group_id: int
    part_id: Optional[int] = None
    customer_part_no: Optional[str] = None
    part_name: Optional[str] = None
    tooling_id: Optional[int] = None
    tooling_number: Optional[str] = None
    tooling_name: Optional[str] = None
    source_row: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SharedFieldGroupDefCreate(BaseModel):
    """Request to create a new shared field group."""
    group_key: str = Field(..., max_length=200)
    display_name: Optional[str] = Field(default=None, max_length=200)
    shares_material: bool = False
    shares_thickness: bool = False
    shares_width: bool = False
    shares_pitch: bool = False
    shares_cavity: bool = False
    remark: Optional[str] = None
    members: list[SharedFieldGroupMemberCreate] = Field(default_factory=list)


class SharedFieldGroupDefUpdate(BaseModel):
    """Request to update a shared field group."""
    display_name: Optional[str] = Field(default=None, max_length=200)
    shares_material: Optional[bool] = None
    shares_thickness: Optional[bool] = None
    shares_width: Optional[bool] = None
    shares_pitch: Optional[bool] = None
    shares_cavity: Optional[bool] = None
    is_active: Optional[bool] = None
    remark: Optional[str] = None


class SharedFieldGroupDefResponse(BaseModel):
    """Response for a shared field group definition."""
    id: int
    group_key: str
    display_name: Optional[str] = None
    shares_material: bool
    shares_thickness: bool
    shares_width: bool
    shares_pitch: bool
    shares_cavity: bool
    source_sheet: Optional[str] = None
    source_rows: Optional[str] = None
    is_active: bool
    remark: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_by: Optional[int] = None
    updated_at: datetime
    members: list[SharedFieldGroupMemberResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
