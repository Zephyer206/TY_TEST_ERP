"""Schemas for the after-sales installation kit archive."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ComponentStatus = Literal["external_purchase", "no_mold", "developing"]
ComponentMatchState = Literal["paired", "non_part", "unmatched"]


class InstallationKitComponentResponse(BaseModel):
    source_kind: str
    sequence: int
    part_number: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[Decimal] = None
    raw_text: str
    model_config = ConfigDict(from_attributes=True)


class InstallationKitComponentPairResponse(BaseModel):
    sequence: int
    ibi: Optional[InstallationKitComponentResponse] = None
    internal: Optional[InstallationKitComponentResponse] = None
    status: Optional[ComponentStatus] = None
    match_state: ComponentMatchState
    status_updated_at: Optional[datetime] = None


class InstallationKitComponentStatusUpdate(BaseModel):
    status: Optional[ComponentStatus] = None


class InstallationKitUpdate(BaseModel):
    """Editable business fields shown in the installation-kit dossier."""

    fmg_code: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=300)
    priority: Optional[int] = Field(default=None, ge=1, le=3)
    d_code: Optional[str] = Field(default=None, max_length=100)
    tianyue_pn: Optional[str] = Field(default=None, max_length=100)
    ibi_spec: Optional[str] = None
    internal_kit_spec: Optional[str] = None
    drawing_status: Optional[str] = Field(default=None, max_length=300)
    sample_status: Optional[str] = Field(default=None, max_length=300)
    ppap_status: Optional[str] = Field(default=None, max_length=300)
    price: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    remark: Optional[str] = None


class InstallationKitComponentUpdate(BaseModel):
    """Editable values shown for one IBI/internal component row."""

    sequence: Optional[int] = Field(default=None, ge=1)
    part_number: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=300)
    quantity: Optional[Decimal] = Field(default=None, ge=0)
    raw_text: Optional[str] = None


class InstallationKitListItem(BaseModel):
    fmg_code: str
    description: Optional[str] = None
    priority: Optional[int] = None
    d_code: Optional[str] = None
    tianyue_pn: Optional[str] = None
    ibi_spec: Optional[str] = None
    internal_kit_spec: Optional[str] = None
    component_pairs: list[InstallationKitComponentPairResponse] = Field(default_factory=list)
    drawing_status: Optional[str] = None
    sample_status: Optional[str] = None
    ppap_status: Optional[str] = None
    document_complete: bool
    price: Optional[Decimal] = None
    price_mismatch: bool = False
    currency: str = "USD"
    remark: Optional[str] = None


class InstallationKitSummary(BaseModel):
    total_records: int
    priced_records: int
    missing_price_records: int
    drawing_ok_records: int
    sample_ok_records: int
    ppap_ok_records: int


class InstallationKitPage(BaseModel):
    items: list[InstallationKitListItem]
    total: int
    page: int
    page_size: int
    summary: InstallationKitSummary


class InstallationKitHistoryResponse(BaseModel):
    action: str
    summary: str
    changed_fields: list[str] = Field(default_factory=list)
    change_data: dict[str, Any] = Field(default_factory=dict)
    actor_user_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InstallationKitDetail(InstallationKitListItem):
    internal_kit_spec: Optional[str] = None
    components: list[InstallationKitComponentResponse] = Field(default_factory=list)
    component_pairs: list[InstallationKitComponentPairResponse] = Field(default_factory=list)
    change_history: list[InstallationKitHistoryResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
