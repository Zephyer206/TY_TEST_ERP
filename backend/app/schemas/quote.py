"""Pydantic schemas for Quote."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.quote import FixPath, MoldFeeMode, NominationStatus, QuoteState


class QuoteCreate(BaseModel):
    part_id: int
    customer_id: Optional[int] = None
    customer_product_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    annual_usage: Optional[int] = None


class QuoteUpdate(BaseModel):
    customer_product_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    annual_usage: Optional[int] = None


class TechReviewUpdate(BaseModel):
    thickness: Optional[float] = Field(default=None, ge=0)
    width: Optional[float] = Field(default=None, ge=0)
    press_stroke: Optional[float] = Field(default=None, ge=0)
    cavity_count: Optional[int] = Field(default=None, ge=1)
    press_tonnage: Optional[int] = Field(default=None, ge=0)
    mold_cost: Optional[Decimal] = Field(default=None, ge=0)
    mold_discount_mode: Optional[MoldFeeMode] = None
    mold_discount_rate: Optional[float] = Field(default=None, ge=0, le=1.0)


class PricingUpdate(BaseModel):
    stamping_fee: Optional[Decimal] = Field(default=None, ge=0)
    surface_fee: Optional[Decimal] = Field(default=None, ge=0)
    treatment_fee: Optional[Decimal] = Field(default=None, ge=0)
    profit_margin: Optional[Decimal] = Field(default=None, ge=0)
    final_price: Optional[Decimal] = Field(default=None, ge=0)


class BossApprovalUpdate(BaseModel):
    approved: bool
    reject_reason: Optional[str] = Field(default=None, max_length=500)


class TechApprovalUpdate(BaseModel):
    approved: bool
    reject_reason: Optional[str] = Field(default=None, max_length=500)
    # optional tech params alongside approval
    thickness: Optional[float] = None
    width: Optional[float] = None
    press_stroke: Optional[float] = None
    cavity_count: Optional[int] = None
    press_tonnage: Optional[int] = None
    mold_cost: Optional[Decimal] = None


class FixUpdate(BaseModel):
    fix_path: FixPath
    final_price: Optional[Decimal] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=500)


class RevokeNominationUpdate(BaseModel):
    revoke_reason: Optional[str] = Field(default=None, max_length=500)


class SurfaceTreatmentCreate(BaseModel):
    name: str = Field(max_length=100)
    fee: Decimal = Field(default=Decimal("0"))
    sequence: int = Field(default=1, ge=1)
    notes: Optional[str] = None


class QuoteListResponse(BaseModel):
    id: int
    quote_no: str
    part_name: str
    part_number: str
    customer_name: Optional[str] = None
    customer_product_no: Optional[str] = None
    vehicle_model: Optional[str] = None
    final_price: Optional[Decimal] = None
    approval_status: str
    nomination_status: Optional[str] = None
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuoteResponse(BaseModel):
    id: int
    quote_no: str
    part_id: int
    part_name: Optional[str] = None
    part_number: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_product_no: Optional[str] = None
    vehicle_model: Optional[str] = None
    annual_usage: Optional[int] = None
    approval_status: str
    nomination_status: Optional[str] = None
    rejection_reason: Optional[str] = None
    price_snapshot: Optional[dict] = None
    # Tech params
    thickness: Optional[float] = None
    width: Optional[float] = None
    press_stroke: Optional[float] = None
    cavity_count: int = 1
    press_tonnage: Optional[int] = None
    mold_cost: Optional[Decimal] = None
    mold_discount_mode: Optional[str] = None
    mold_discount_rate: Optional[float] = None
    # Pricing
    stamping_fee: Optional[Decimal] = None
    surface_fee: Optional[Decimal] = None
    treatment_fee: Optional[Decimal] = None
    profit_margin: Optional[Decimal] = None
    final_price: Optional[Decimal] = None
    # Timestamps
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    nomination_confirmed_at: Optional[datetime] = None
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
