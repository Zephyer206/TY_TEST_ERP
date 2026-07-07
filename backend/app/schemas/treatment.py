"""Pydantic schemas for treatment dictionary management - T019."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TreatmentDictCreate(BaseModel):
    """Schema for creating a treatment dictionary entry."""

    name: str = Field(min_length=1, max_length=100, description="工序名称")
    calc_mode: str = Field(default="manual", description="计价方式: manual / net_weight")
    default_rate: Decimal = Field(ge=0, description="默认费率")
    unit: str = Field(default="元/件", max_length=20, description="单位")
    is_active: bool = Field(default=True, description="是否激活")
    sort_order: int = Field(default=0, description="排序顺序")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "电镀锌",
                "calc_mode": "manual",
                "default_rate": 2.00,
                "unit": "元/件",
                "is_active": True,
                "sort_order": 1,
            }
        }
    )


class TreatmentDictUpdate(BaseModel):
    """Schema for updating a treatment dictionary entry."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    calc_mode: Optional[str] = Field(default=None)
    default_rate: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = Field(default=None)
    sort_order: Optional[int] = Field(default=None)


class TreatmentDictResponse(BaseModel):
    """Schema for treatment dictionary response."""

    id: int
    name: str
    calc_mode: str
    default_rate: Decimal
    unit: str
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
