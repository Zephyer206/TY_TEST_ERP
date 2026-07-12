"""Schemas for customer parts and prices."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CustomerPartPriceInfo(BaseModel):
    """Customer part with price information."""
    part_id: int
    internal_name: Optional[str] = None
    customer_part_no: str
    customer_part_name: Optional[str] = None
    material_name: Optional[str] = None
    has_price_account: bool
    material_unit_price: Optional[float] = None
    scrap_price: Optional[float] = None
    surface_treatment_cost: Optional[float] = None
    material_cost: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerPartsWithPricesResponse(BaseModel):
    """Response for customer parts with prices."""
    customer_id: int
    customer_name: str
    customer_code: Optional[str] = None
    parts_count: int
    parts: list[CustomerPartPriceInfo]

    model_config = ConfigDict(from_attributes=True)


class PriceAdjustmentInfo(BaseModel):
    """Price adjustment history information."""
    id: int
    adjustment_type: str
    old_price: Optional[float] = None
    new_price: float
    reason: Optional[str] = None
    status: str
    requested_by: int
    requested_at: datetime
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    effective_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
