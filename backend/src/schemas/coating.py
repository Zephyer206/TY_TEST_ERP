"""Pydantic schemas for coating (spray painting) management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.coating import CoatingColor, CoatingType


class CoatingRecipeBase(BaseModel):
    """Base schema for coating recipe."""

    name: str
    coating_type: CoatingType
    color_type: CoatingColor = CoatingColor.CUSTOM
    color_code: Optional[str] = None
    primer_type: Optional[str] = None
    primer_thickness: Optional[float] = None
    topcoat_type: Optional[str] = None
    topcoat_thickness: Optional[float] = None
    spray_pressure: Optional[float] = None
    spray_distance: Optional[float] = None
    spray_speed: Optional[float] = None
    curing_temp: Optional[float] = None
    curing_time: Optional[int] = None
    material_consumption: Optional[float] = None
    notes: Optional[str] = None


class CoatingRecipeCreate(CoatingRecipeBase):
    """Schema for creating a coating recipe."""

    pass


class CoatingRecipeUpdate(BaseModel):
    """Schema for updating a coating recipe."""

    name: Optional[str] = None
    coating_type: Optional[CoatingType] = None
    color_type: Optional[CoatingColor] = None
    color_code: Optional[str] = None
    primer_type: Optional[str] = None
    primer_thickness: Optional[float] = None
    topcoat_type: Optional[str] = None
    topcoat_thickness: Optional[float] = None
    spray_pressure: Optional[float] = None
    spray_distance: Optional[float] = None
    spray_speed: Optional[float] = None
    curing_temp: Optional[float] = None
    curing_time: Optional[int] = None
    material_consumption: Optional[float] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class CoatingRecipeResponse(CoatingRecipeBase):
    """Schema for coating recipe response."""

    id: int
    recipe_no: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CoatingRecordBase(BaseModel):
    """Base schema for coating record."""

    recipe_id: int
    part_id: int
    processed_qty: int = Field(ge=1)
    qualified_qty: int = Field(ge=0)
    rejected_qty: int = Field(default=0, ge=0)
    material_used: Optional[float] = Field(default=None, ge=0)
    batch_no: Optional[str] = None
    notes: Optional[str] = None


class CoatingRecordCreate(CoatingRecordBase):
    """Schema for creating a coating record."""

    pass


class CoatingRecordResponse(CoatingRecordBase):
    """Schema for coating record response."""

    id: int
    record_no: str
    recipe_id: int
    recipe_name: Optional[str] = None
    operator_id: Optional[int] = None
    coating_date: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
