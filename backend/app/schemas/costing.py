"""Typed inputs shared by quotation and simple costing; unknown is never zero."""
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, le=Decimal('1000000000'), allow_inf_nan=False)]
Positive = Annotated[Decimal, Field(gt=0, le=Decimal('1000000000'), allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TreatmentItem(StrictModel):
    item_key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    requirements: str = Field(default='', max_length=2000)
    source: str = Field(default='', max_length=500)

    @model_validator(mode='after')
    def meaningful_name(self):
        if not self.name.strip():
            raise ValueError('处理方式不能为空')
        return self


class SurfaceTreatment(StrictModel):
    status: Literal['pending', 'none', 'required'] = 'pending'
    revision: int = Field(default=0, ge=0)
    items: list[TreatmentItem] = Field(default_factory=list, max_length=50)

    @model_validator(mode='after')
    def consistent(self):
        if self.status == 'none' and self.items:
            raise ValueError('无需处理时不能保留处理项')
        if self.status == 'required' and not self.items:
            raise ValueError('需要处理时请填写至少一个处理项目')
        keys = [item.item_key for item in self.items]
        if len(set(keys)) != len(keys):
            raise ValueError('处理项目标识重复')
        return self


class TreatmentSave(StrictModel):
    expected_revision: int = Field(ge=0)
    surface_treatment: SurfaceTreatment
    source: str = Field(default='零件维护', min_length=1, max_length=200)


class MaterialCalculation(StrictModel):
    thickness: Positive | None = None
    width: Positive | None = None
    pitch: Positive | None = None
    density: Positive | None = None
    pieces_per_blank: Positive = Decimal('1')
    gross_weight_g: Positive | None = None
    net_weight_g: Money | None = None
    quoted_gross_weight_g: Positive | None = None
    utilization_pct: Annotated[Decimal, Field(gt=0, le=100, allow_inf_nan=False)] | None = None
    material_price: Money | None = None
    scrap_price: Money | None = None


class TreatmentCharge(StrictModel):
    item_key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    rule_id: int | None = None
    method: Literal['piece', 'net_kg', 'batch'] = 'piece'
    rate: Money | None = None
    quantity: Positive | None = None
    source: str = Field(default='', max_length=500)


class OptionalCost(StrictModel):
    selected: bool = False
    name: str = Field(default='', max_length=150)
    amount: Money | None = None
    source: str = Field(default='', max_length=500)


class SimpleCalculation(StrictModel):
    mode: Literal['basic'] = 'basic'
    material: MaterialCalculation = Field(default_factory=MaterialCalculation)
    treatment_status: Literal['pending', 'none', 'required'] = 'pending'
    treatments: list[TreatmentCharge] = Field(default_factory=list, max_length=50)
    special_costs: list[OptionalCost] = Field(default_factory=list, max_length=50)
    tooling_amortization: OptionalCost = Field(default_factory=OptionalCost)
    reference_price: Money | None = None
    comparison_basis: Literal['unknown','both_tax_included','both_tax_excluded'] = 'unknown'


class CostingInput(StrictModel):
    calculation: SimpleCalculation
    material_id: int | None = None
    quote_item_id: int | None = None
    price_source: Literal['catalog', 'quote', 'supplement'] = 'catalog'
    source_note: str = Field(default='', max_length=1000)
    expected_source_token: str | None = None


class SurfaceRuleSnapshot(StrictModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    rate: Money | None = None
    method: Literal['piece', 'net_kg']
    unit: Literal['元/件', '元/kg']
    updated_at: str | None = None


class QuotationPreview(StrictModel):
    material: MaterialCalculation
    surface_fee: Money | None = None
    surface_rule_id: int | None = None
    surface_rule_snapshot: SurfaceRuleSnapshot | None = None


class TaskCreate(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    customer_id: int = Field(gt=0)


class ItemCreate(StrictModel):
    alias_id: int = Field(gt=0)
    part_id: int = Field(gt=0)
    tooling_id: int = Field(gt=0)
    spec_id: int | None = None
    source_reference: dict | None = None


class RevisionCreate(CostingInput):
    expected_version: int = Field(ge=0)
    request_id: str = Field(min_length=8, max_length=100)
    reason: str = Field(default='', max_length=500)
