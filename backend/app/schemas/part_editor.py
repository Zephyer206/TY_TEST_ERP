"""Part editor schemas for transactional updates."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PartEditorUpdateRequest(BaseModel):
    """Request schema for part editor transactional update.

    Includes all editable canonical part fields safe for the editor screen:
    - Identity: internal_name
    - Customer alias: customer_id, customer_part_no, customer_part_name
    - Vehicle: vehicle_model
    - Material: material_name
    - Drawing: drawing_url
    - Weights: gross_weight, net_weight
    - Position: part_position
    - Status: part_status, status
    - Remark: remark
    - Press/quality fields: press_tonnage, ppap_no

    Protected fields NOT included:
    - id (internal primary key)
    - timestamps (created_at, updated_at - system managed)
    - stock_pcs (stock/production accounting)
    - nomination fields (nomination_status, nomination_attachment, etc.)
    - sample_judgment_status, spray_status, spray_stamped_at
    - is_urgent, target_count, version
    - is_deleted (soft delete flag)
    - price_snapshot (pricing system)
    """

    # Identity
    internal_name: Optional[str] = Field(default=None, max_length=200)

    # Canonical customer alias fields
    customer_id: Optional[int] = None
    customer_part_no: Optional[str] = Field(default=None, max_length=150)
    customer_part_name: Optional[str] = Field(default=None, max_length=200)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)

    # Material
    material_name: Optional[str] = Field(default=None, max_length=100)

    # Drawing
    drawing_url: Optional[str] = None

    # Weights
    # Pydantic 2.6 cannot apply decimal_places metadata through Optional[Decimal].
    # Keep the non-negative validation; the database decimal columns remain the
    # authoritative precision boundary.
    gross_weight: Optional[Decimal] = Field(default=None, ge=0)
    net_weight: Optional[Decimal] = Field(default=None, ge=0)

    # Position
    part_position: Optional[str] = Field(default=None, max_length=20)

    # Status
    part_status: Optional[str] = Field(default=None, max_length=50)
    status: Optional[str] = Field(default=None, max_length=50)

    # Remark
    remark: Optional[str] = Field(default=None, max_length=500)

    # Press/quality fields remain part-level metadata.
    press_tonnage: Optional[str] = Field(default=None, max_length=50)
    ppap_no: Optional[str] = Field(default=None, max_length=100)

    # Optimistic concurrency control
    updated_at: datetime = Field(
        description="Client's last known updated_at timestamp for optimistic locking"
    )

    @field_validator('part_status')
    @classmethod
    def validate_part_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate part_status is a known state."""
        if v is None:
            return v
        allowed = ['DRAFT', 'draft', 'SAMPLING', 'sampling', 'MASS_PRODUCTION',
                   'mass_production', 'OBSOLETE', 'obsolete']
        if v not in allowed:
            raise ValueError(f'part_status must be one of {allowed}')
        return v

    @field_validator('part_position')
    @classmethod
    def validate_position(cls, v: Optional[str]) -> Optional[str]:
        """Validate part_position is a known value."""
        if v is None:
            return v
        allowed = ['left', 'right', 'center', 'single', '']
        if v and v not in allowed:
            raise ValueError(f'part_position must be one of {allowed}')
        return v

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class PartEditorUpdateResponse(BaseModel):
    """Response schema for part editor update.

    Returns all editable fields plus system-managed fields for display.
    """

    id: int

    # Identity
    part_name: Optional[str] = None

    # Customer alias
    customer_id: Optional[int] = None
    customer_part_no: Optional[str] = None
    customer_part_name: Optional[str] = None
    vehicle_model: Optional[str] = None

    # Material
    material_name: Optional[str] = None
    material_id: Optional[int] = None

    # Historical part-level specification is returned read-only for source comparison.
    drawing_url: Optional[str] = None
    spec_info: Optional[str] = None

    # Legacy part-level TWP fields are returned read-only for source comparison.
    # Authoritative editable TWP lives in part_tooling_specs.
    spec_twph: Optional[str] = None
    thickness: Optional[Decimal] = None
    width: Optional[Decimal] = None
    pitch: Optional[Decimal] = None
    height: Optional[Decimal] = None

    # Weights
    gross_weight: Optional[Decimal] = None
    net_weight: Optional[Decimal] = None

    # Position
    part_position: Optional[str] = None

    # Status
    part_status: str
    status: Optional[str] = None

    # Remark
    remark: Optional[str] = None

    # Press/quality fields
    press_tonnage: Optional[str] = None
    ppap_no: Optional[str] = None

    # System-managed fields
    stock_pcs: int = 0
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Version for next optimistic lock
    version: str = "V1.0"

    model_config = ConfigDict(from_attributes=True)


class PartEditorConflictDetail(BaseModel):
    """Details about an optimistic lock conflict."""

    field: str
    client_value: Optional[str] = None
    server_value: Optional[str] = None
    server_updated_at: datetime
    server_updated_by: Optional[int] = None


class PartEditorConflictResponse(BaseModel):
    """Response for optimistic lock conflict (HTTP 409)."""

    detail: str = "Part was modified by another user"
    conflict_type: str = "optimistic_lock"
    client_timestamp: datetime
    server_timestamp: datetime
    conflicts: list[PartEditorConflictDetail] = []
    current_part: PartEditorUpdateResponse

    model_config = ConfigDict(from_attributes=True)
