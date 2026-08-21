"""Schemas for Stage 3 part editor - relationship editing APIs."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==================== Customer Aliases ====================

class CustomerAliasItem(BaseModel):
    """Single customer alias in the editor."""
    model_config = ConfigDict(extra='forbid')

    id: Optional[int] = Field(None, description="Existing alias ID, null for new")
    customer_id: int = Field(..., description="Customer ID (required)")
    customer_part_no: str = Field(..., min_length=1, max_length=150, description="Customer part number")
    customer_part_name: Optional[str] = Field(None, max_length=200, description="Customer part name")
    revision: str = Field("", max_length=50, description="Revision code")
    vehicle_model: Optional[str] = Field(None, max_length=100, description="Vehicle model")
    remark: Optional[str] = Field(None, description="Remarks")
    is_active: bool = Field(True, description="Active status")


class CustomerAliasesUpdateRequest(BaseModel):
    """Request to update customer aliases with explicit upsert/delete."""
    model_config = ConfigDict(extra='forbid')

    aliases: list[CustomerAliasItem] = Field(
        ...,
        description="Aliases to upsert (by ID if present, otherwise create)"
    )
    delete_alias_ids: list[int] = Field(
        default_factory=list,
        description="Alias IDs to explicitly delete"
    )


class CustomerAliasResponse(BaseModel):
    """Response for a single customer alias."""

    id: int
    part_id: int
    customer_id: int
    customer_part_no: str
    customer_part_name: Optional[str]
    revision: str
    vehicle_model: Optional[str]
    remark: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ==================== Tooling Associations ====================

class ToolingPartItem(BaseModel):
    """Single tooling-part association in the editor."""
    model_config = ConfigDict(extra='forbid')

    id: Optional[int] = Field(None, description="Existing ToolingPart ID for update")
    tooling_id: int = Field(..., description="Tooling ID (required)")
    position: Optional[str] = Field(None, max_length=20, description="Position (left/right/center)")
    sequence: int = Field(0, ge=0, description="Sort order")
    is_primary: bool = Field(False, description="Client-requested primary flag")


class ToolingPartsUpdateRequest(BaseModel):
    """Request to update tooling associations with explicit operations."""
    model_config = ConfigDict(extra='forbid')

    tooling_parts: list[ToolingPartItem] = Field(
        ...,
        description="Tooling associations to create/update"
    )
    delete_tooling_part_ids: list[int] = Field(
        default_factory=list,
        description="ToolingPart IDs to explicitly delete"
    )


class ToolingPartResponse(BaseModel):
    """Response for a single tooling-part association."""

    id: int
    tooling_id: int
    part_id: int
    position: Optional[str]
    sequence: int
    is_primary: bool
    created_at: datetime
    tooling_number: Optional[str] = None
    tooling_name: Optional[str] = None
    mold_type: Optional[str] = None
    is_continuous: bool = False


# ==================== TWP Specifications ====================

class TWPSpecItem(BaseModel):
    """Single TWP spec record for a (part, tooling) pair.

    Source fields (source_sheet, source_row, source_note) are read-only and cannot be set via API.
    Pydantic extra='forbid' enforces this constraint at validation time.
    """
    model_config = ConfigDict(extra='forbid')

    id: Optional[int] = Field(None, description="Existing spec ID for update, null for new")
    tooling_id: int = Field(..., description="Tooling ID this spec belongs to")
    spec_twph: Optional[str] = Field(None, max_length=100, description="Combined T/W/P/H string")
    # Pydantic 2.6+ rejects max_digits/decimal_places metadata on Optional
    # constrained decimals during model construction. Keep non-negative
    # validation here and enforce the three-decimal business rule below.
    thickness: Optional[Decimal] = Field(None, ge=0, description="T")
    width: Optional[Decimal] = Field(None, ge=0, description="W")
    pitch: Optional[Decimal] = Field(None, ge=0, description="P")
    is_primary: bool = Field(False, description="Client-requested primary for this (part, tooling)")

    @field_validator('thickness', 'width', 'pitch')
    @classmethod
    def validate_decimal_scale(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure decimal values have at most 3 decimal places."""
        if v is not None and v.as_tuple().exponent < -3:
            raise ValueError("Decimal precision must be at most 3 decimal places")
        return v


class TWPSpecsUpdateRequest(BaseModel):
    """Request to update TWP specs with explicit upsert/delete."""
    model_config = ConfigDict(extra='forbid')

    specs: list[TWPSpecItem] = Field(
        ...,
        description="TWP specs to upsert (by ID if present, preserving source fields)"
    )
    delete_spec_ids: list[int] = Field(
        default_factory=list,
        description="Spec IDs to explicitly delete"
    )


class TWPSpecResponse(BaseModel):
    """Response for a single TWP spec."""

    id: int
    part_id: int
    tooling_id: int
    spec_twph: Optional[str]
    thickness: Optional[Decimal]
    width: Optional[Decimal]
    pitch: Optional[Decimal]
    is_primary: bool
    source_sheet: Optional[str]
    source_row: Optional[int]
    source_note: Optional[str]
    created_at: datetime
    updated_at: datetime


# ==================== Combined Editor Detail ====================

class ToolingBriefInfo(BaseModel):
    """Brief tooling info for editor context."""

    id: int
    tooling_number: Optional[str]
    tooling_name: Optional[str]
    mold_type: str
    is_continuous: bool


class PartEditorDetailResponse(BaseModel):
    """Complete part detail response for the editor."""

    # Part basic info - all editable base fields from PartEditorUpdateResponse
    id: int
    part_name: Optional[str]
    customer_id: Optional[int]
    customer_part_no: Optional[str]
    customer_part_name: Optional[str]
    vehicle_model: Optional[str]
    material_id: Optional[int]
    material_name: Optional[str]
    drawing_url: Optional[str]
    spec_info: Optional[str]
    spec_twph: Optional[str]
    thickness: Optional[Decimal]
    width: Optional[Decimal]
    pitch: Optional[Decimal]
    height: Optional[Decimal]
    gross_weight: Optional[Decimal]
    net_weight: Optional[Decimal]
    part_position: Optional[str]
    part_status: str
    status: Optional[str]
    remark: Optional[str]
    press_tonnage: Optional[str]
    ppap_no: Optional[str]
    stock_pcs: int
    is_deleted: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    version: str

    # Relationships
    customer_aliases: list[CustomerAliasResponse]
    tooling_associations: list[ToolingPartResponse]
    twp_specs: list[TWPSpecResponse]

    # Tooling context (for validation)
    available_toolings: list[ToolingBriefInfo]


# ==================== Bulk Update ====================

class PartEditorBulkUpdateRequest(BaseModel):
    """Atomic update for all relationship categories with optimistic locking."""
    model_config = ConfigDict(extra='forbid')

    expected_updated_at: datetime = Field(
        ...,
        description="Expected part.updated_at for optimistic lock (409 on mismatch)"
    )
    customer_aliases: Optional[list[CustomerAliasItem]] = Field(
        None,
        description="Aliases to upsert (by ID), null = no change"
    )
    delete_alias_ids: list[int] = Field(
        default_factory=list,
        description="Alias IDs to explicitly delete"
    )
    tooling_parts: Optional[list[ToolingPartItem]] = Field(
        None,
        description="Tooling associations to upsert, null = no change"
    )
    delete_tooling_part_ids: list[int] = Field(
        default_factory=list,
        description="ToolingPart IDs to explicitly delete"
    )
    twp_specs: Optional[list[TWPSpecItem]] = Field(
        None,
        description="TWP specs to upsert (preserves source fields), null = no change"
    )
    delete_spec_ids: list[int] = Field(
        default_factory=list,
        description="Spec IDs to explicitly delete"
    )


class PartEditorBulkUpdateResponse(BaseModel):
    """Response after bulk update."""

    success: bool
    part_id: int
    updated_at: datetime
    customer_aliases_count: int
    tooling_parts_count: int
    twp_specs_count: int
    message: str
