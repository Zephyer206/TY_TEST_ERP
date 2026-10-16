"""Pydantic contracts for the customer-first gaibo archive."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


GaiboCustomFieldType = Literal["text", "number", "date", "boolean", "select"]
GaiboCustomFieldScope = Literal["single_part", "installation_package", "both"]


class GaiboCustomFieldDefinition(BaseModel):
    key: str = Field(pattern=r"^custom_[a-z0-9_]{8,64}$", max_length=72)
    label: str = Field(min_length=1, max_length=50)
    data_type: GaiboCustomFieldType = "text"
    scope: GaiboCustomFieldScope = "both"
    default_visible: bool = True
    width: int = Field(default=120, ge=56, le=420)
    sequence: int = Field(default=0, ge=0, le=100)
    is_active: bool = True
    options: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段名称不能为空")
        return normalized

    @field_validator("options")
    @classmethod
    def normalize_options(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            option = value.strip()
            if not option:
                continue
            if len(option) > 50:
                raise ValueError("选项名称不能超过 50 个字符")
            if option not in normalized:
                normalized.append(option)
        return normalized

    @model_validator(mode="after")
    def validate_select_options(self):
        if self.data_type == "select" and not self.options:
            raise ValueError("单选字段至少需要一个选项")
        if self.data_type != "select":
            self.options = []
        return self


class GaiboWorkspaceViewConfig(BaseModel):
    visible: list[str] = Field(default_factory=list, max_length=40)
    order: list[str] = Field(default_factory=list, max_length=40)
    widths: dict[str, int] = Field(default_factory=dict)
    density: Literal["compact", "standard"] = "compact"
    sortKey: str = Field(default="updatedAt", max_length=72)
    sortOrder: Literal["asc", "desc"] = "desc"

    @field_validator("visible", "order")
    @classmethod
    def unique_column_keys(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @field_validator("widths")
    @classmethod
    def validate_widths(cls, values: dict[str, int]) -> dict[str, int]:
        if len(values) > 40:
            raise ValueError("列宽配置不能超过 40 列")
        return {key: max(56, min(420, int(width))) for key, width in values.items()}


class GaiboWorkspaceColumnConfigUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    field_labels: dict[str, str] = Field(default_factory=dict)
    detail_section_labels: dict[str, str] = Field(default_factory=dict)
    custom_fields: list[GaiboCustomFieldDefinition] = Field(default_factory=list, max_length=24)
    default_view_config: GaiboWorkspaceViewConfig


class GaiboWorkspaceColumnConfigResponse(BaseModel):
    workspace_id: int
    version: int
    field_labels: dict[str, str]
    detail_section_labels: dict[str, str]
    custom_fields: list[GaiboCustomFieldDefinition]
    default_view_config: GaiboWorkspaceViewConfig


class GaiboWorkspaceCreate(BaseModel):
    after_sales_customer_name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    field_labels: dict[str, str] = Field(default_factory=dict)
    extra_field_definitions: dict[str, Any] = Field(default_factory=dict)


class GaiboWorkspaceUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    field_labels: Optional[dict[str, str]] = None
    extra_field_definitions: Optional[dict[str, Any]] = None


class GaiboWorkspaceResponse(BaseModel):
    id: int
    after_sales_customer_id: int
    after_sales_customer_name: str
    slug: str
    display_name: str
    is_active: bool
    field_labels: dict[str, str]
    extra_field_definitions: dict[str, Any]
    default_view_config: dict[str, Any]
    column_config_version: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GaiboSinglePartCreate(BaseModel):
    part_id: Optional[int] = Field(default=None, gt=0)
    tianyue_internal_part_no: Optional[str] = Field(default=None, max_length=100)
    name: Optional[str] = Field(default=None, max_length=300)
    drawing_reference: Optional[str] = Field(default=None, max_length=500)


class GaiboSinglePartUpdate(GaiboSinglePartCreate):
    is_active: Optional[bool] = None


class GaiboSinglePartResponse(BaseModel):
    id: int
    part_id: Optional[int] = None
    tianyue_internal_part_no: Optional[str] = None
    name: Optional[str] = None
    drawing_reference: Optional[str] = None
    drawing_preview_url: Optional[str] = None
    is_active: bool
    requirement_count: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GaiboRequirementCreate(BaseModel):
    workspace_id: int = Field(gt=0)
    single_part_id: int = Field(gt=0)
    customer_part_number: str = Field(min_length=1, max_length=200)
    ibi: str = Field(min_length=1)
    tianyue_internal_composition: str = Field(min_length=1)
    price: Decimal = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    extra_data: dict[str, Any] = Field(default_factory=dict)
    remark: Optional[str] = None


class GaiboRequirementUpdate(BaseModel):
    expected_updated_at: Optional[datetime] = None
    customer_part_number: Optional[str] = Field(default=None, min_length=1, max_length=200)
    ibi: Optional[str] = Field(default=None, min_length=1)
    tianyue_internal_composition: Optional[str] = Field(default=None, min_length=1)
    price: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    extra_data: Optional[dict[str, Any]] = None
    remark: Optional[str] = None
    is_active: Optional[bool] = None


class GaiboRequirementDossierUpdate(GaiboRequirementUpdate):
    """One transactional detail-editor request.

    ``single_part_name`` belongs to the shared single-part master while the
    remaining values belong to the customer requirement.  Keeping both in one
    payload lets the dossier save atomically without exposing source metadata.
    """

    single_part_name: Optional[str] = Field(default=None, max_length=300)


class GaiboRequirementResponse(BaseModel):
    id: int
    workspace_id: int
    single_part_id: int
    customer_part_number: str
    ibi: str
    tianyue_internal_composition: str
    price: Decimal
    currency: str
    extra_data: dict[str, Any]
    remark: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GaiboPackageCreate(BaseModel):
    workspace_id: int = Field(gt=0)
    package_number: str = Field(min_length=1, max_length=200)
    name: Optional[str] = Field(default=None, max_length=300)
    priority: Optional[int] = Field(default=None, ge=1, le=3)
    d_code: Optional[str] = Field(default=None, max_length=100)
    tianyue_pn: Optional[str] = Field(default=None, max_length=100)
    price: Optional[Decimal] = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    extra_data: dict[str, Any] = Field(default_factory=dict)
    remark: Optional[str] = None


class GaiboPackageResponse(BaseModel):
    id: int
    workspace_id: int
    package_number: str
    name: Optional[str] = None
    priority: Optional[int] = None
    d_code: Optional[str] = None
    tianyue_pn: Optional[str] = None
    price: Optional[Decimal] = None
    price_mismatch: bool = False
    currency: str
    extra_data: dict[str, Any]
    remark: Optional[str] = None
    source_data: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GaiboPackageUpdate(BaseModel):
    expected_updated_at: Optional[datetime] = None
    package_number: Optional[str] = Field(default=None, min_length=1, max_length=200)
    name: Optional[str] = Field(default=None, max_length=300)
    priority: Optional[int] = Field(default=None, ge=1, le=3)
    d_code: Optional[str] = Field(default=None, max_length=100)
    tianyue_pn: Optional[str] = Field(default=None, max_length=100)
    price: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    extra_data: Optional[dict[str, Any]] = None
    remark: Optional[str] = None
    is_active: Optional[bool] = None


class GaiboPackageItemCreate(BaseModel):
    requirement_id: Optional[int] = Field(default=None, gt=0)
    unlinked_customer_part_number: Optional[str] = Field(default=None, max_length=200)
    ibi: Optional[str] = Field(default=None, min_length=1)
    tianyue_internal_composition: str = Field(min_length=1)
    quantity: Decimal = Field(default=1, gt=0)
    sequence: int = Field(default=1, ge=1)
    status: Optional[str] = Field(default=None, max_length=30)
    remark: Optional[str] = None


class GaiboPackageItemUpdate(BaseModel):
    expected_updated_at: Optional[datetime] = None
    requirement_id: Optional[int] = Field(default=None, gt=0)
    unlinked_customer_part_number: Optional[str] = Field(default=None, max_length=200)
    ibi: Optional[str] = Field(default=None, min_length=1)
    tianyue_internal_composition: Optional[str] = Field(default=None, min_length=1)
    quantity: Optional[Decimal] = Field(default=None, gt=0)
    sequence: Optional[int] = Field(default=None, ge=1)
    status: Optional[str] = Field(default=None, max_length=30)
    remark: Optional[str] = None


class GaiboPackageItemResponse(GaiboPackageItemCreate):
    id: int
    package_id: int
    match_state: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class GaiboDocumentStatusCreate(BaseModel):
    document_type: str = Field(min_length=1, max_length=50)
    status: str = Field(default="not_started", min_length=1, max_length=30)
    submitted_at: Optional[datetime] = None
    concluded_at: Optional[datetime] = None
    remark: Optional[str] = None


class GaiboDocumentEventResponse(BaseModel):
    event_type: str
    label: str
    date_text: Optional[str] = None
    raw_text: Optional[str] = None


class GaiboDocumentStatusUpdate(BaseModel):
    expected_updated_at: Optional[datetime] = None
    document_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)
    submitted_at: Optional[datetime] = None
    concluded_at: Optional[datetime] = None
    remark: Optional[str] = None


class GaiboDocumentStatusResponse(GaiboDocumentStatusCreate):
    id: int
    requirement_id: Optional[int] = None
    package_id: Optional[int] = None
    events: list[GaiboDocumentEventResponse] = Field(default_factory=list)
    latest_event: Optional[GaiboDocumentEventResponse] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class GaiboDrawingCreate(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    file_key: str = Field(min_length=1, max_length=500)
    status: str = Field(default="not_started", min_length=1, max_length=30)
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    remark: Optional[str] = None


class GaiboDrawingUpdate(GaiboDrawingCreate):
    expected_updated_at: Optional[datetime] = None
    version: Optional[str] = Field(default=None, min_length=1, max_length=50)
    file_key: Optional[str] = Field(default=None, min_length=1, max_length=500)
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    remark: Optional[str] = None


class GaiboDrawingResponse(GaiboDrawingCreate):
    id: int
    requirement_id: int
    preview_url: Optional[str] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class GaiboProcessStepCreate(BaseModel):
    sequence: int = Field(default=1, ge=1)
    operation_name: str = Field(min_length=1, max_length=200)
    machine_id: Optional[int] = Field(default=None, gt=0)
    tooling_id: Optional[int] = Field(default=None, gt=0)
    key_parameters: dict[str, Any] = Field(default_factory=dict)
    quality_checkpoints: dict[str, Any] = Field(default_factory=dict)
    remark: Optional[str] = None


class GaiboProcessStepResponse(GaiboProcessStepCreate):
    id: int
    route_id: int
    model_config = ConfigDict(from_attributes=True)


class GaiboProcessRouteCreate(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    status: str = Field(default="draft", min_length=1, max_length=30)
    is_current: bool = False
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    remark: Optional[str] = None
    steps: list[GaiboProcessStepCreate] = Field(default_factory=list)


class GaiboProcessRouteUpdate(BaseModel):
    expected_updated_at: Optional[datetime] = None
    version: Optional[str] = Field(default=None, min_length=1, max_length=50)
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)
    is_current: Optional[bool] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    remark: Optional[str] = None
    steps: Optional[list[GaiboProcessStepCreate]] = None


class GaiboProcessRouteResponse(BaseModel):
    id: int
    requirement_id: int
    version: str
    status: str
    is_current: bool
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    remark: Optional[str] = None
    steps: list[GaiboProcessStepResponse] = Field(default_factory=list)
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class GaiboChangeLogResponse(BaseModel):
    id: int
    workspace_id: int
    entity_type: str
    entity_id: int
    action: str
    changed_fields: list[str]
    change_data: dict[str, Any]
    summary: str
    actor_user_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GaiboPackageDetailResponse(GaiboPackageResponse):
    items: list[GaiboPackageItemResponse] = Field(default_factory=list)
    documents: list[GaiboDocumentStatusResponse] = Field(default_factory=list)
    change_history: list[GaiboChangeLogResponse] = Field(default_factory=list)


class GaiboRequirementDetailResponse(GaiboRequirementResponse):
    single_part: Optional[GaiboSinglePartResponse] = None
    drawings: list[GaiboDrawingResponse] = Field(default_factory=list)
    process_routes: list[GaiboProcessRouteResponse] = Field(default_factory=list)
    documents: list[GaiboDocumentStatusResponse] = Field(default_factory=list)
    change_history: list[GaiboChangeLogResponse] = Field(default_factory=list)


class GaiboSearchComponent(BaseModel):
    sequence: int
    # Source Excel rows may contain the internal composition before an IBI is assigned.
    ibi: Optional[str] = None
    tianyue_internal_composition: str
    quantity: Decimal
    status: Optional[str] = None


class GaiboSearchItem(BaseModel):
    record_type: Literal["single_part", "installation_package"]
    record_id: int
    workspace_id: int
    workspace_name: str
    customer_part_number: Optional[str] = None
    priority: Optional[int] = None
    d_code: Optional[str] = None
    tianyue_pn: Optional[str] = None
    ibi: Optional[str] = None
    tianyue_internal_composition: Optional[str] = None
    price: Optional[Decimal] = None
    price_mismatch: bool = False
    display_name: Optional[str] = None
    remark: Optional[str] = None
    extra_data: dict[str, Any] = Field(default_factory=dict)
    drawing_status: Optional[str] = None
    sample_status: Optional[str] = None
    ppap_status: Optional[str] = None
    drawing_latest_event: Optional[GaiboDocumentEventResponse] = None
    sample_latest_event: Optional[GaiboDocumentEventResponse] = None
    ppap_latest_event: Optional[GaiboDocumentEventResponse] = None
    component_items: list[GaiboSearchComponent] = Field(default_factory=list)
    updated_at: datetime


class GaiboSearchSummary(BaseModel):
    total_records: int
    priced_records: int
    missing_price_records: int
    drawing_ok_records: int
    sample_ok_records: int
    ppap_ok_records: int


class GaiboSearchPage(BaseModel):
    items: list[GaiboSearchItem]
    total: int
    page: int
    page_size: int
    summary: GaiboSearchSummary


class GaiboFilterOption(BaseModel):
    value: str
    label: str
    count: int


class GaiboFilterOptionsResponse(BaseModel):
    column_key: str
    options: list[GaiboFilterOption]


class GaiboViewPreferenceUpdate(BaseModel):
    config: dict[str, Any]


class GaiboViewPreferenceResponse(BaseModel):
    view_key: str
    config: dict[str, Any]
    updated_at: Optional[datetime] = None
