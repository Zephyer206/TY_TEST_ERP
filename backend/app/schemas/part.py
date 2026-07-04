"""Pydantic schemas for Part - 匹配实际数据库字段."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PartCreate(BaseModel):
    part_number: str = Field(max_length=50)
    internal_name: Optional[str] = Field(default=None, max_length=200)
    customer_id: Optional[int] = None
    customer_product_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    material_name: Optional[str] = Field(default=None, max_length=100)
    remark: Optional[str] = Field(default=None, max_length=500)


class PartUpdate(BaseModel):
    internal_name: Optional[str] = Field(default=None, max_length=200)
    customer_id: Optional[int] = None
    customer_product_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    material_name: Optional[str] = Field(default=None, max_length=100)
    mold_number: Optional[str] = Field(default=None, max_length=50)
    mold_type: Optional[str] = Field(default=None, max_length=50)
    press_tonnage: Optional[str] = Field(default=None, max_length=50)
    ppap_no: Optional[str] = Field(default=None, max_length=100)
    remark: Optional[str] = Field(default=None, max_length=500)


class PartResponse(BaseModel):
    id: int
    part_number: str
    internal_name: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_product_no: Optional[str] = None
    vehicle_model: Optional[str] = None
    material_name: Optional[str] = None
    part_status: str
    stock_pcs: int = 0
    mold_number: Optional[str] = None
    mold_type: Optional[str] = None
    press_tonnage: Optional[str] = None
    ppap_no: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Keep for import compatibility
class PartImportRow(BaseModel):
    material: Optional[str] = None
