"""Schemas for the persistent project quotation workspace."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class QuoteGroupItemUpdate(BaseModel):
    product_price: Decimal = Field(default=0, ge=0)
    annual_usage: int = Field(default=0, ge=0)
    lifecycle_years: Optional[Decimal] = Field(default=None, ge=0)


class QuoteGroupCreate(BaseModel):
    inquiry_id: int


class QuoteGroupUpdate(BaseModel):
    surface_rule_id: Optional[int] = Field(default=None, gt=0)
    refresh_surface_rule: bool = False
    quote_path: Optional[str] = Field(default=None, max_length=60)
    tooling_type: Optional[str] = Field(default=None, max_length=100)
    tooling_cost: Optional[Annotated[Decimal, Field(ge=0, le=Decimal("9999999999.99"), decimal_places=2)]] = Field(
        default=None,
        description="Final customer tooling price in yuan; does not modify engineering estimates",
    )
    tooling_lead_time: Optional[int] = Field(default=None, ge=0)
    tooling_life: Optional[int] = Field(default=None, ge=0)
    material_name: Optional[str] = Field(default=None, max_length=100)
    material_density: Optional[Decimal] = Field(default=None, ge=0)
    material_unit_price: Optional[Decimal] = Field(default=None, ge=0)
    material_scrap_price: Optional[Decimal] = Field(default=None, ge=0)
    surface_treatment_fee: Optional[Decimal] = Field(default=None, ge=0)
    inspection_fee: Optional[Decimal] = Field(default=None, ge=0)
    packaging_fee: Optional[Decimal] = Field(default=None, ge=0)
    freight_fee: Optional[Decimal] = Field(default=None, ge=0)
    management_fee: Optional[Decimal] = Field(default=None, ge=0)
    profit_margin: Optional[Decimal] = Field(default=None, ge=0, le=100)
    material_adjustment: Optional[Decimal] = None
    quote_note: Optional[str] = Field(default=None, max_length=4000)
    items: Optional[list[QuoteGroupItemUpdate]] = None

    @field_validator("tooling_cost")
    @classmethod
    def tooling_price_must_not_be_null(cls, value: Optional[Decimal]) -> Decimal:
        if value is None:
            raise ValueError("Final tooling price must be a number; use zero for free tooling")
        return value


class QuoteGroupItemResponse(BaseModel):
    id: int
    sequence: int
    customer_part_no: Optional[str]
    part_name: Optional[str]
    pair_key: Optional[str]
    material_name: Optional[str]
    thickness: Optional[Decimal]
    width: Optional[Decimal]
    pitch: Optional[Decimal]
    utilization: Optional[Decimal]
    press_tonnage: Optional[int]
    press_type_key: Optional[str] = None
    press_type_label: Optional[str] = None
    press_is_dual_axis: Optional[bool] = None
    press_tonnage_source: Optional[Literal["type", "manual"]] = None
    cavity_count: int
    tooling_cost: Decimal
    tooling_lead_time: int
    product_price: Decimal
    annual_usage: int
    lifecycle_years: Optional[Decimal]

    model_config = {"from_attributes": True}


class QuoteGroupResponse(BaseModel):
    surface_rule_snapshot: Optional[dict] = None
    id: int
    group_no: str
    inquiry_id: int
    customer_id: int
    customer: str
    project_name: str
    status: str
    quote_path: str
    tooling_type: Optional[str]
    tooling_cost: Decimal = Field(description="Final customer tooling price in yuan")
    development_tooling_cost: Optional[Decimal] = Field(
        description="Read-only engineering snapshot total in yuan; shared left/right tooling counted once; null if incomplete",
    )
    tooling_lead_time: int
    tooling_life: int
    material_name: Optional[str]
    material_density: Optional[Decimal]
    material_unit_price: Decimal
    material_scrap_price: Optional[Decimal]
    surface_treatment_fee: Decimal
    inspection_fee: Decimal
    packaging_fee: Decimal
    freight_fee: Decimal
    management_fee: Decimal
    profit_margin: Decimal
    material_adjustment: Decimal
    quote_note: Optional[str]
    updated_at: datetime
    items: list[QuoteGroupItemResponse]

    model_config = {"from_attributes": True}
