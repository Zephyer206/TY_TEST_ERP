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
    part_number: Optional[str] = None
    internal_name: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_product_no: Optional[str] = None
    customer_product_name: Optional[str] = None
    vehicle_model: Optional[str] = None
    material_name: Optional[str] = None
    material_name_full: Optional[str] = None  # 完整材料名称
    part_status: str
    stock_pcs: int = 0
    mold_number: Optional[str] = None
    mold_type: Optional[str] = None
    press_tonnage: Optional[str] = None
    ppap_no: Optional[str] = None
    # TWP字段
    spec_twph: Optional[str] = None
    thickness: Optional[float] = None
    width: Optional[float] = None
    pitch: Optional[float] = None
    twp_options_count: int = 0
    has_primary_twp: bool = False
    height: Optional[float] = None
    # 重量
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    # 左右件
    part_position: Optional[str] = None
    # 穴数（从tooling表获取）
    cavity_count: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PartDisplayGroup(BaseModel):
    """One row in the parts management list.

    Left/right parts that share a base tooling number are returned as one group;
    ordinary parts contain a single member.
    """

    key: str
    is_left_right_pair: bool = False
    # Source-block groups keep each mold/part row separate while allowing the
    # frontend to rowspan only the shared material/TWP/cavity columns.
    is_shared_source_group: bool = False
    members: list[PartResponse]


class PartDisplayPage(BaseModel):
    total: int
    items: list[PartDisplayGroup]


# Keep for import compatibility
class PartImportRow(BaseModel):
    material: Optional[str] = None
