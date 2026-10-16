"""Pydantic schemas for price account management."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.price import PriceAdjustmentType


# ============= 新增：客户价格历史 Schemas (T016-T017) =============


class CustomerMaterialPriceCreate(BaseModel):
    """Schema for creating customer material price record - T016."""

    customer_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, description="材料单价（元/kg）")
    scrap_price: Optional[Decimal] = Field(default=None, ge=0, description="废料回收价")
    quote_id: Optional[int] = Field(default=None, description="关联报价单ID")


class CustomerMaterialPriceResponse(BaseModel):
    """Schema for customer material price response - T016."""

    id: int
    customer_id: int
    material_id: int
    unit_price: Decimal
    scrap_price: Optional[Decimal] = None
    quote_id: Optional[int] = None
    quoted_at: datetime
    created_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerTreatmentPriceCreate(BaseModel):
    """Schema for creating customer treatment price record - T017."""

    customer_id: int = Field(gt=0)
    treatment_id: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, description="工序价格")
    calc_mode_snapshot: Optional[str] = Field(default=None, description="快照：计价方式")
    unit_snapshot: Optional[str] = Field(default=None, description="快照：单位")
    quote_id: Optional[int] = Field(default=None, description="关联报价单ID")


class CustomerTreatmentPriceResponse(BaseModel):
    """Schema for customer treatment price response - T017."""

    id: int
    customer_id: int
    treatment_id: int
    unit_price: Decimal
    calc_mode_snapshot: Optional[str] = None
    unit_snapshot: Optional[str] = None
    quote_id: Optional[int] = None
    quoted_at: datetime
    created_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerPriceAdjustmentCreate(BaseModel):
    """Request for the customer/material/treatment approval workflow."""

    customer_id: int = Field(gt=0)
    part_id: Optional[int] = Field(default=None, gt=0)
    material_id: Optional[int] = Field(default=None, gt=0)
    treatment_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    adjustment_type: Literal["material", "treatment", "part"]
    old_price: Optional[Decimal] = Field(default=None, ge=0)
    new_price: Decimal = Field(gt=0)
    reason: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_target_fields(self) -> "CustomerPriceAdjustmentCreate":
        required_by_type = {
            "material": ("material_id", self.material_id),
            "treatment": ("treatment_name", self.treatment_name),
            "part": ("part_id", self.part_id),
        }
        field_name, value = required_by_type[self.adjustment_type]
        if value is None:
            raise ValueError(f"{field_name} is required for {self.adjustment_type} adjustments")
        return self


class CustomerPriceAdjustmentApprovalRequest(BaseModel):
    """Request to approve or reject a customer price adjustment."""

    status: Literal["approved", "rejected"]
    rejection_reason: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_rejection_reason(self) -> "CustomerPriceAdjustmentApprovalRequest":
        if self.status == "rejected" and not self.rejection_reason:
            raise ValueError("rejection_reason is required when status is rejected")
        return self


class CustomerPriceAdjustmentResponse(BaseModel):
    """Response mapped to the current customer price adjustment table."""

    id: int
    customer_id: int
    part_id: Optional[int] = None
    material_id: Optional[int] = None
    treatment_name: Optional[str] = None
    adjustment_type: str
    old_price: Optional[Decimal] = None
    new_price: Decimal
    reason: Optional[str] = None
    status: str
    requested_by: int
    requested_at: datetime
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    effective_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============= 以下保留原有 schemas =============


# --- Annual Price Record Schemas ---

class AnnualPriceRecordBase(BaseModel):
    """Base schema for annual price record."""

    year: int = Field(ge=2000, le=2100)
    unit_price: Decimal = Field(ge=0)
    annual_qty: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class AnnualPriceRecordCreate(AnnualPriceRecordBase):
    """Schema for creating an annual price record."""

    pass


class AnnualPriceRecordResponse(AnnualPriceRecordBase):
    """Schema for annual price record response."""

    id: int
    price_account_id: int
    created_by: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Price Adjustment Schemas ---

class PriceAccountAdjustmentResponse(BaseModel):
    """Response for the legacy price-account adjustment endpoint."""

    id: int
    price_account_id: int
    old_price: Decimal
    new_price: Decimal
    adjustment_type: PriceAdjustmentType
    reason: Optional[str] = None
    created_by: int
    creator_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Price Account Schemas ---

class PriceAccountBase(BaseModel):
    """Base schema for price account."""

    part_id: int
    customer_id: int
    material: Optional[str] = Field(default=None, max_length=100)
    net_weight_kg: Optional[float] = Field(default=None, ge=0)
    gross_weight_kg: Optional[float] = Field(default=None, ge=0)
    material_unit_price: Optional[Decimal] = Field(default=None, ge=0)
    scrap_price: Optional[Decimal] = Field(default=None, ge=0)
    reduction_pct: float = Field(default=0.0, ge=0, le=1.0)
    notes: Optional[str] = None


class PriceAccountCreate(PriceAccountBase):
    """Schema for creating a price account."""

    pass


class PriceAccountUpdate(BaseModel):
    """Schema for updating a price account."""

    material: Optional[str] = Field(default=None, max_length=100)
    net_weight_kg: Optional[float] = Field(default=None, ge=0)
    gross_weight_kg: Optional[float] = Field(default=None, ge=0)
    material_unit_price: Optional[Decimal] = Field(default=None, ge=0)
    scrap_price: Optional[Decimal] = Field(default=None, ge=0)
    reduction_pct: Optional[float] = Field(default=None, ge=0, le=1.0)
    notes: Optional[str] = None


class PriceAccountAdjustmentCreate(BaseModel):
    """Request for the legacy price-account adjustment endpoint."""

    new_price: Decimal = Field(ge=0)
    adjustment_type: PriceAdjustmentType = Field(default=PriceAdjustmentType.MANUAL)
    reason: Optional[str] = Field(default=None, max_length=500)


class PriceAccountResponse(PriceAccountBase):
    """Schema for price account response."""

    id: int
    base_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    price_year: Optional[int] = None
    is_active: bool
    annual_records: list[AnnualPriceRecordResponse] = []
    adjustments: list[PriceAccountAdjustmentResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PriceAccountListResponse(BaseModel):
    """Schema for price account list (summary)."""

    id: int
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    customer_id: int
    customer_name: Optional[str] = None
    current_price: Optional[Decimal] = None
    price_year: Optional[int] = None
    reduction_pct: float
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CurrentPriceResponse(BaseModel):
    """Schema for computed current price."""

    price: Decimal
    year: int
    is_computed: bool  # True if from formula, False if from record
    formula: Optional[str] = None  # Description of how price was computed


# Compatibility names used by older price-account consumers. New approval code
# must use the explicit CustomerPriceAdjustment* classes above.
PriceAdjustmentCreate = PriceAccountAdjustmentCreate
PriceAdjustmentResponse = PriceAccountAdjustmentResponse
PriceAdjustmentApprovalRequest = CustomerPriceAdjustmentApprovalRequest
