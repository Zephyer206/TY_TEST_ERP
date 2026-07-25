"""Schemas for part detail with relationships."""

from typing import Optional
from pydantic import BaseModel, ConfigDict


class ToolingStepInfo(BaseModel):
    """Tooling step information."""
    step_no: int
    step_code: Optional[str] = None
    step_name: Optional[str] = None
    operation_type: Optional[str] = None
    sequence: int


class PartCustomerAliasInfo(BaseModel):
    """Customer alias information for a part."""
    customer_id: int
    customer_name: str
    customer_code: Optional[str] = None
    customer_part_no: Optional[str] = None
    customer_part_name: Optional[str] = None
    vehicle_model: Optional[str] = None
    revision: str
    is_active: bool


class PartToolingSpecInfo(BaseModel):
    """One source-backed TWP option for a part-tooling record."""

    id: int
    part_id: int
    tooling_id: int
    spec_twph: Optional[str] = None
    thickness: Optional[float] = None
    width: Optional[float] = None
    pitch: Optional[float] = None
    is_primary: bool
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    source_note: Optional[str] = None


class PartToolingInfo(BaseModel):
    """Tooling information for a part."""
    tooling_id: int
    part_id: int
    tooling_part_id: int
    tooling_number: Optional[str] = None
    tooling_name: Optional[str] = None
    mold_type: str
    is_continuous: bool
    cavity_count: int
    process_step_count: Optional[int] = None
    status: str
    position: Optional[str] = None
    is_primary: bool
    steps: Optional[list[ToolingStepInfo]] = None
    tooling_customers: Optional[list[str]] = None
    twp_options: list[PartToolingSpecInfo] = []


class SharedToolingRelationInfo(BaseModel):
    """Source-backed shared mold relation visible in part details."""

    relation_id: int
    tooling_id: int
    tooling_number: Optional[str] = None
    related_tooling_id: int
    related_tooling_number: Optional[str] = None
    relation_scope: str
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    source_note: Optional[str] = None
    confidence: str


class PartDetailResponse(BaseModel):
    """Part detail response with all relationships."""
    id: int
    internal_name: Optional[str] = None
    internal_part_no: Optional[str] = None
    drawing_url: Optional[str] = None
    material_name: Optional[str] = None
    thickness: Optional[float] = None
    width: Optional[float] = None
    pitch: Optional[float] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    part_position: Optional[str] = None
    part_status: str
    customer_aliases: list[PartCustomerAliasInfo]
    tooling: list[PartToolingInfo]
    shared_tooling_relations: list[SharedToolingRelationInfo] = []

    model_config = ConfigDict(from_attributes=True)
