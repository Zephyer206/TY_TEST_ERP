"""Pydantic schemas for Quote and QuoteItem."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models.quote import FixPath, MoldFeeMode, NominationStatus, QuoteState


# --- Surface Treatment Schemas ---

class SurfaceTreatmentBase(BaseModel):
    """Base schema for surface treatment."""

    sequence: int = Field(default=1, ge=1)
    name: str = Field(max_length=100)
    fee: Decimal = Field(default=Decimal("0"))
    notes: Optional[str] = None


class SurfaceTreatmentCreate(SurfaceTreatmentBase):
    """Schema for creating a surface treatment."""

    pass


class SurfaceTreatmentResponse(SurfaceTreatmentBase):
    """Schema for surface treatment response."""

    id: int
    quote_id: int
    quote_item_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# --- QuoteItem Schemas ---

class QuoteItemBase(BaseModel):
    """Base schema for quote item."""

    part_name: str = Field(max_length=200)
    customer_part_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    drawing_no: Optional[str] = Field(default=None, max_length=100)
    material: Optional[str] = Field(default=None, max_length=100)
    thickness: Optional[float] = None
    width: Optional[float] = None
    weight_kg: Optional[float] = None
    unit_price: Optional[Decimal] = None
    moq: Optional[int] = None
    lead_time_days: Optional[int] = None


class QuoteItemCreate(QuoteItemBase):
    """Schema for creating a quote item."""

    pass


class QuoteItemUpdate(BaseModel):
    """Schema for updating a quote item."""

    part_name: Optional[str] = Field(default=None, max_length=200)
    customer_part_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    drawing_no: Optional[str] = Field(default=None, max_length=100)
    material: Optional[str] = Field(default=None, max_length=100)
    thickness: Optional[float] = None
    width: Optional[float] = None
    weight_kg: Optional[float] = None
    unit_price: Optional[Decimal] = None
    moq: Optional[int] = None
    lead_time_days: Optional[int] = None


class QuoteItemResponse(QuoteItemBase):
    """Schema for quote item response."""

    id: int
    quote_id: int
    surface_treatments: list[SurfaceTreatmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- Quote Schemas ---

class QuoteBase(BaseModel):
    """Base schema for quote."""

    title: str = Field(max_length=200)
    customer_id: int
    annual_usage: Optional[int] = None
    annual_avg_usage: Optional[int] = None


class QuoteCreate(QuoteBase):
    """Schema for creating a quote."""

    items: list[QuoteItemCreate] = Field(default_factory=list)


class QuoteUpdate(BaseModel):
    """Schema for updating a quote."""

    title: Optional[str] = Field(default=None, max_length=200)
    annual_usage: Optional[int] = None
    annual_avg_usage: Optional[int] = None


class TechReviewUpdate(BaseModel):
    """Schema for tech engineer to fill technical parameters."""

    thickness_t: Optional[float] = Field(default=None, ge=0)
    width_w: Optional[float] = Field(default=None, ge=0)
    press_p: Optional[int] = Field(default=None, ge=0)
    cavity_count: Optional[int] = Field(default=None, ge=0)
    tonnage: Optional[float] = Field(default=None, ge=0)
    mold_fee: Optional[Decimal] = Field(default=None, ge=0)
    mold_fee_mode: Optional[MoldFeeMode] = None
    mold_fee_discount: Optional[float] = Field(default=None, ge=0, le=1.0)


class PricingUpdate(BaseModel):
    """Schema for sales to fill pricing."""

    stamping_fee: Optional[Decimal] = Field(default=None, ge=0)
    surface_treatment_fee: Optional[Decimal] = Field(default=None, ge=0)
    profit_margin: Optional[Decimal] = Field(default=None, ge=0)


class BossApprovalUpdate(BaseModel):
    """Schema for boss approval."""

    approved: bool
    reject_reason: Optional[str] = Field(default=None, max_length=500)


class TechApprovalUpdate(BaseModel):
    """Schema for tech review approval."""

    approved: bool
    reject_reason: Optional[str] = Field(default=None, max_length=500)


class FixUpdate(BaseModel):
    """Schema for fix confirmation."""

    fix_path: FixPath
    final_price: Optional[Decimal] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=500)


class RevokeNominationUpdate(BaseModel):
    """Schema for revoking nomination (fix)."""

    revoke_reason: Optional[str] = Field(default=None, max_length=500)


class QuoteResponse(QuoteBase):
    """Schema for quote response."""

    id: int
    quote_no: str
    state: QuoteState
    creator_id: int
    creator_name: Optional[str] = None

    # Technical params
    thickness_t: Optional[float] = None
    width_w: Optional[float] = None
    press_p: Optional[int] = None
    cavity_count: Optional[int] = None
    tonnage: Optional[float] = None
    mold_fee: Optional[Decimal] = None
    mold_fee_mode: Optional[MoldFeeMode] = None
    mold_fee_discount: Optional[float] = None

    # Pricing
    stamping_fee: Optional[Decimal] = None
    surface_treatment_fee: Optional[Decimal] = None
    profit_margin: Optional[Decimal] = None

    # Snapshot & path
    price_snapshot: Optional[dict] = None
    final_price: Optional[Decimal] = None
    nomination_status: NominationStatus = NominationStatus.UNFIXED
    fix_path: Optional[FixPath] = None

    # Revocation
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[int] = None
    revoke_reason: Optional[str] = None

    # Rejection reasons
    reject_reason: Optional[str] = None
    tech_reject_reason: Optional[str] = None

    # State timestamps
    submitted_for_review_at: Optional[datetime] = None
    tech_reviewed_at: Optional[datetime] = None
    submitted_to_boss_at: Optional[datetime] = None
    boss_reviewed_at: Optional[datetime] = None
    fixed_at: Optional[datetime] = None

    # Items
    items: list[QuoteItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class QuoteListResponse(BaseModel):
    """Schema for quote list (summary)."""

    id: int
    quote_no: str
    title: str
    state: QuoteState
    customer_id: int
    customer_name: Optional[str] = None
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
