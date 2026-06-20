"""Pydantic schemas for Part."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.part import PartState


class PartBase(BaseModel):
    """Base schema for part."""

    part_name: str = Field(max_length=200)
    customer_id: int
    customer_part_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    drawing_no: Optional[str] = Field(default=None, max_length=100)
    material: Optional[str] = Field(default=None, max_length=100)
    thickness: Optional[float] = None
    width: Optional[float] = None
    weight_kg: Optional[float] = None
    cavity_count: Optional[int] = None
    tonnage: Optional[float] = None


class PartCreate(PartBase):
    """Schema for creating a part."""

    pass


class PartUpdate(BaseModel):
    """Schema for updating a part."""

    part_name: Optional[str] = Field(default=None, max_length=200)
    customer_part_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    drawing_no: Optional[str] = Field(default=None, max_length=100)
    material: Optional[str] = Field(default=None, max_length=100)
    thickness: Optional[float] = None
    width: Optional[float] = None
    weight_kg: Optional[float] = None
    cavity_count: Optional[int] = None
    tonnage: Optional[float] = None
    mold_id: Optional[int] = None
    mold_no: Optional[str] = Field(default=None, max_length=50)
    mold_type: Optional[str] = Field(default=None, max_length=50)
    ppap_no: Optional[str] = Field(default=None, max_length=100)
    drawing_path: Optional[str] = None


class PartResponse(PartBase):
    """Schema for part response."""

    id: int
    part_no: str
    quote_id: Optional[int] = None
    state: PartState
    mold_id: Optional[int] = None
    mold_no: Optional[str] = None
    mold_type: Optional[str] = None
    ppap_no: Optional[str] = None
    price_snapshot: Optional[dict] = None
    stock_pcs: int = 0
    drawing_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartListResponse(BaseModel):
    """Schema for part list (summary)."""

    id: int
    part_no: str
    part_name: str
    state: PartState
    customer_id: int
    customer_name: Optional[str] = None
    material: Optional[str] = None
    stock_pcs: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartImportRow(BaseModel):
    """Schema for a single row in the import template."""

    material: Optional[str] = None
    net_weight_kg: Optional[float] = None
    gross_weight_kg: Optional[float] = None
    material_unit_price: Optional[Decimal] = None
    scrap_price: Optional[Decimal] = None
    surface_treatment: Optional[str] = None
    drawing_path: Optional[str] = None
