"""Pydantic schemas for coating (spray painting) management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.coating import RecipeStatus, RecordStatus


class CoatingRecipeCreate(BaseModel):
    """Schema for creating a coating recipe."""

    name: str = Field(max_length=200)
    color_code: Optional[str] = Field(default=None, max_length=50)
    color_name: Optional[str] = Field(default=None, max_length=100)
    coating_type: str = Field(max_length=100)
    process_params: Optional[dict] = None
    material_consumption: Optional[dict] = None
    coating_cost_per_part: Optional[float] = Field(default=None, ge=0)
    quality_standards: Optional[dict] = None
    compatible_parts: Optional[dict] = None
    notes: Optional[str] = None


class CoatingRecipeUpdate(BaseModel):
    """Schema for updating a coating recipe."""

    name: Optional[str] = None
    color_code: Optional[str] = None
    color_name: Optional[str] = None
    coating_type: Optional[str] = None
    process_params: Optional[dict] = None
    material_consumption: Optional[dict] = None
    coating_cost_per_part: Optional[float] = None
    quality_standards: Optional[dict] = None
    status: Optional[RecipeStatus] = None
    compatible_parts: Optional[dict] = None
    notes: Optional[str] = None


class CoatingRecipeResponse(BaseModel):
    """Schema for coating recipe response."""

    id: int
    recipe_no: str
    name: str
    color_code: Optional[str] = None
    color_name: Optional[str] = None
    coating_type: str
    process_params: Optional[dict] = None
    material_consumption: Optional[dict] = None
    coating_cost_per_part: Optional[float] = None
    quality_standards: Optional[dict] = None
    status: RecipeStatus
    compatible_parts: Optional[dict] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CoatingRecordCreate(BaseModel):
    """Schema for creating a coating record (spray painting work order)."""

    part_id: int
    recipe_id: Optional[int] = None
    work_order_barcode: Optional[str] = None
    production_batch_no: Optional[str] = None
    process_flow_no: Optional[str] = None
    input_qty: int = Field(ge=1)
    equipment_id: Optional[int] = None
    booth_no: Optional[str] = None
    notes: Optional[str] = None


class CoatingRecordUpdate(BaseModel):
    """Schema for updating a coating record."""

    passed_qty: Optional[int] = Field(default=None, ge=0)
    rejected_qty: Optional[int] = Field(default=None, ge=0)
    paint_used_kg: Optional[float] = None
    solvent_used_kg: Optional[float] = None
    actual_params: Optional[dict] = None
    status: Optional[RecordStatus] = None
    quality_check_result: Optional[str] = None
    quality_check_notes: Optional[str] = None
    notes: Optional[str] = None


class CoatingRecordResponse(BaseModel):
    """Schema for coating record response."""

    id: int
    record_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    recipe_id: Optional[int] = None
    recipe_name: Optional[str] = None
    production_batch_no: Optional[str] = None
    process_flow_no: Optional[str] = None
    work_order_barcode: Optional[str] = None
    input_qty: int
    passed_qty: int
    rejected_qty: int
    paint_used_kg: Optional[float] = None
    solvent_used_kg: Optional[float] = None
    actual_consumption_per_part: Optional[float] = None
    actual_params: Optional[dict] = None
    status: RecordStatus
    quality_check_result: Optional[str] = None
    quality_check_notes: Optional[str] = None
    quality_check_by: Optional[int] = None
    quality_check_at: Optional[datetime] = None
    operator_id: Optional[int] = None
    equipment_id: Optional[int] = None
    booth_no: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CoatingRecordListResponse(BaseModel):
    """Schema for coating record list."""

    id: int
    record_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    recipe_name: Optional[str] = None
    input_qty: int
    passed_qty: int
    rejected_qty: int
    status: RecordStatus
    operator_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CoatingMaterialInventoryResponse(BaseModel):
    """Schema for coating material inventory response."""

    id: int
    material_type: str
    material_name: str
    color_code: Optional[str] = None
    current_qty_kg: float
    unit: str
    reorder_point_kg: Optional[float] = None
    supplier_id: Optional[int] = None
    warehouse_location: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
