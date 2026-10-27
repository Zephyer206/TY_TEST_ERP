"""Typed product QR requests and responses; reject coerced quantities/actors."""
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictInt, model_validator


def canonical_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("ID must be a positive decimal identity")
    if isinstance(value, str) and not re.fullmatch(r"[1-9][0-9]{0,18}", value):
        raise ValueError("ID must be a canonical decimal identity")
    identity = int(value)
    if not 0 < identity <= 9_223_372_036_854_775_807:
        raise ValueError("ID is outside the supported range")
    return identity


NewId = Annotated[int, BeforeValidator(canonical_id)]
RequestKey = Annotated[str, Field(min_length=8, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
Capability = Literal["qr.trace", "qr.production", "qr.split", "qr.print", "qr.bind", "qr.supervise",
                     "qr.generate", "qr.metadata", "qr.configure", "qr.admin"]


class QrModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateRequest(QrModel):
    count: Annotated[StrictInt, Field(ge=1, le=5000)]
    print_batch_no: Annotated[str, Field(min_length=1, max_length=50)] | None = None
    idempotency_key: RequestKey


class BindRequest(QrModel):
    qr_payload: Annotated[str, Field(min_length=1, max_length=200)]
    order_product_id: NewId
    context_id: NewId | None = None
    idempotency_key: RequestKey


class ScanRequest(QrModel):
    qr_payload: Annotated[str, Field(min_length=1, max_length=200)]
    split_parent_id: NewId | None = None


class PrintDataRequest(QrModel):
    item_ids: Annotated[list[NewId], Field(min_length=1, max_length=5000)]
    template_code: Literal["a4_3x7_v1"] = "a4_3x7_v1"
    idempotency_key: RequestKey


class ReprintRequest(QrModel):
    template_code: Literal["a4_3x7_v1"] = "a4_3x7_v1"
    idempotency_key: RequestKey


class PrintConfirmationRequest(QrModel):
    print_job_id: NewId
    confirmed_item_ids: Annotated[list[NewId], Field(min_length=1, max_length=5000)]
    idempotency_key: RequestKey


class CapabilitiesRequest(QrModel):
    capabilities: Annotated[list[Capability], Field(max_length=10)]
    expected_version: Annotated[StrictInt, Field(ge=0)]
    idempotency_key: RequestKey


class MetadataRequest(QrModel):
    customer_name_snapshot: Annotated[str, Field(max_length=200)] | None = None
    customer_part_no: Annotated[str, Field(max_length=150)] | None = None
    next_process_code: Annotated[str, Field(min_length=1, max_length=50)] | None = None
    expected_version: Annotated[StrictInt, Field(ge=1)]
    idempotency_key: RequestKey

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set & {"customer_name_snapshot", "customer_part_no", "next_process_code"}:
            raise ValueError("At least one editable metadata field is required")
        return self


class PoolItem(QrModel):
    id: str
    public_code: str
    qr_payload: str
    payload_version: Literal["v1"]
    pool_status: Literal["unused", "bound", "void"]
    print_batch_no: str | None
    print_count: int
    printed_at: str | None
    created_at: str
    bound_box_id: str | None


class ProductBox(QrModel):
    id: str
    qr_pool_item_id: str
    box_no: str
    order_id: int
    order_product_id: str
    part_id: int
    product_code: Literal["B", "C"]
    product_name_snapshot: str
    customer_id: int | None
    customer_name_snapshot: str | None
    customer_part_no: str | None
    route_revision_id: str
    current_process_code: str | None
    next_process_code: str | None
    current_qty: int
    version: int
    lifecycle_status: Literal["active", "empty", "closed", "scrapped"]
    bound_by: int
    bound_at: str
    public_code: str
    qr_payload: str


class PoolActor(QrModel):
    id: int
    dept: str
    role_level: int


class PoolPage(QrModel):
    items: list[PoolItem]
    total: int
    page: int
    page_size: int
    actor: PoolActor
    capabilities: list[Capability]
    batch_limit: int


class GeneratedBatch(QrModel):
    print_batch_no: str
    count: int
    items: list[PoolItem]


class FlowEvent(QrModel):
    id: str
    event_type: str
    process_code: str | None
    state_id: str | None
    operator_id: int
    operator_name: str | None
    machine_id: int | None
    machine_no: str | None
    material_batch_id: int | None
    before_qty: int
    after_qty: int
    before_snapshot: dict[str, Any]
    after_snapshot: dict[str, Any]
    remark: str | None
    occurred_at: str


class BoxScan(QrModel):
    pool_item: PoolItem
    box: ProductBox | None
    allowed_actions: list[Literal["bind", "trace"]]
    latest_event: FlowEvent | None = None


class PrintTemplate(QrModel):
    code: Literal["a4_3x7_v1"]
    paper_width_mm: int
    paper_height_mm: int
    margin_mm: int
    columns: int
    rows: int
    label_width_mm: int
    label_height_mm: int
    gap_mm: int
    quiet_zone_modules: int


class PrintedLabel(PoolItem):
    qr_image_base64: str
    box: ProductBox | None = None


class PrintJob(QrModel):
    print_job_id: str
    template: PrintTemplate
    items: list[PrintedLabel]


class PrintConfirmation(QrModel):
    print_job_id: str
    items: list[PoolItem]


class CapabilitiesResult(QrModel):
    user_id: int
    version: int
    capabilities: list[Capability]


class CapabilitiesItem(CapabilitiesResult):
    dept: str
    role_level: int


class CapabilitiesPage(QrModel):
    items: list[CapabilitiesItem]
    page: int
    page_size: int


class OrderRoute(QrModel):
    id: str
    route_code: str
    revision: int
    product_code: Literal["B", "C"]
    steps: list[dict[str, Any]]
    first_output_process_code: str
    is_published: bool


class OrderMachineTarget(QrModel):
    state_id: str
    assignment_id: int
    machine_id: int
    process_code: str
    target_qty: int
    production_status: Literal["pending", "in_progress", "completed"]
    version: int
    is_active: bool


class OrderProductConfiguration(QrModel):
    id: str
    part_id: int
    product_code: Literal["B", "C"]
    target_qty: int
    route_revision_id: str
    binding_allowed: bool
    conversion_source_id: str | None
    version: int
    part_name: str | None
    customer_part_no: str | None
    route: OrderRoute | None
    machine_process_targets: list[OrderMachineTarget]
    missing_configuration: list[str]
    can_bind: bool


class OrderQrContext(QrModel):
    order_id: int
    part_id: int | None
    paired_part_id: int | None
    is_left_right_pair: bool
    status: str | None
    total_qty: int | None
    business_owner_id: int | None
    version: int
    missing_configuration: list[str]
    products: list[OrderProductConfiguration]


Quantity = Annotated[StrictInt, Field(ge=0, le=2_147_483_647)]
Version = Annotated[StrictInt, Field(ge=1)]
LegacyId = Annotated[StrictInt, Field(ge=1, le=2_147_483_647)]


class RouteStepRequest(QrModel):
    code: Annotated[str, Field(min_length=1, max_length=50)]
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    machine_ids: list[LegacyId] = []
    machine_types: list[Annotated[str, Field(min_length=1, max_length=50)]] = []


class RouteRequest(QrModel):
    route_code: Annotated[str, Field(min_length=1, max_length=80)]
    revision: Version
    steps: Annotated[list[RouteStepRequest], Field(min_length=1, max_length=100)]
    first_output_process_code: Annotated[str, Field(min_length=1, max_length=50)]


class ConversionAuthorizationRequest(QrModel):
    target_key: Annotated[str, Field(min_length=1, max_length=50)]
    difference_process_codes: list[Annotated[str, Field(min_length=1, max_length=50)]]


class OrderProductRequest(QrModel):
    key: Annotated[str, Field(min_length=1, max_length=50)]
    id: NewId | None = None
    part_id: LegacyId
    product_code: Literal["B", "C"]
    target_qty: Quantity
    binding_allowed: StrictBool = True
    conversion_source_key: str | None = None
    route: RouteRequest
    pre_authorized_conversions: list[ConversionAuthorizationRequest] = []


class MachineTargetRequest(QrModel):
    product_key: str
    assignment_id: LegacyId
    process_code: str
    target_qty: Quantity


class OrderQrContextRequest(QrModel):
    business_owner_id: LegacyId
    products: Annotated[list[OrderProductRequest], Field(min_length=1, max_length=20)]
    machine_process_targets: Annotated[list[MachineTargetRequest], Field(min_length=1, max_length=2000)]
    expected_version: Quantity
    idempotency_key: RequestKey


class MachineScanRequest(QrModel):
    machine_qr: Annotated[str, Field(min_length=1, max_length=500)]
    context_id: NewId | None = None


class ProductionSelectRequest(QrModel):
    scan_ticket: Annotated[str, Field(min_length=20, max_length=120)]
    assignment_id: LegacyId
    order_product_id: NewId
    process_code: Annotated[str, Field(min_length=1, max_length=50)]
    state_id: NewId | None = None
    idempotency_key: RequestKey


class QuantityRequest(QrModel):
    context_id: NewId
    current_qty: Quantity
    expected_version: Version
    state_version: Version
    idempotency_key: RequestKey
    material_batch_id: LegacyId | None = None


class AdvanceRequest(QrModel):
    context_id: NewId
    expected_version: Version
    state_version: Version
    idempotency_key: RequestKey


class SplitRequest(QrModel):
    child_qr_payload: Annotated[str, Field(min_length=1, max_length=200)]
    quantity: Annotated[StrictInt, Field(ge=1, le=2_147_483_647)]
    order_qty: Quantity
    stock_qty: Quantity
    expected_version: Version
    allocation_version: Version
    target_order_product_id: NewId | None = None
    target_state_id: NewId | None = None
    target_state_version: Version | None = None
    idempotency_key: RequestKey

    @model_validator(mode="after")
    def explicit_receiving_state(self):
        if self.target_order_product_id is not None:
            if self.target_state_id is None or self.target_state_version is None:
                raise ValueError("Cross-order partition requires an explicit receiving process and version")
        elif self.target_state_id is not None or self.target_state_version is not None:
            raise ValueError("Same-order partition inherits its existing process")
        return self


class CorrectionRequest(QrModel):
    state_id: NewId
    current_qty: Quantity
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    expected_version: Version
    state_version: Version
    idempotency_key: RequestKey


class ProductionCompleteRequest(QrModel):
    context_id: NewId
    confirm_quantity_difference: StrictBool
    expected_version: Version
    idempotency_key: RequestKey


class AllocationRequest(QrModel):
    source_quantity_id: NewId
    order_qty: Quantity
    stock_qty: Quantity
    expected_version: Version
    idempotency_key: RequestKey


class ProductionContext(QrModel):
    id: str
    machine_id: int
    state_id: str | None
    order_id: int | None
    order_product_id: str | None
    assignment_id: int | None
    process_code: str | None
    expires_at: str
    closed_at: str | None
    completion_scan_at: str | None


class OutputAllocation(QrModel):
    id: str
    source_quantity_id: str
    origin_allocation_id: str | None = None
    box_id: str
    order_id: int
    order_product_id: str
    available_qty: int
    order_qty: int
    stock_qty: int
    remaining_order_qty_snapshot: int
    manually_adjusted: bool
    version: int
    has_downstream: bool
    allowed_actions: list[Literal["allocate"]]


class ProcessQuantity(QrModel):
    id: str
    state_id: str
    box_id: str
    current_qty: int
    input_qty: int
    source_quantity_id: str | None
    material_batch_id: int | None = None
    version: int
    updated_by: int
    updated_at: str


class ProductionBox(ProcessQuantity):
    quantity_id: str
    box_no: str
    box_version: int
    product_name: str
    customer_part_no: str | None
    allocation: OutputAllocation | None
    can_correct: bool = False
    quantity_locked: bool = False


class ProductionState(QrModel):
    id: str
    assignment_id: int
    machine_id: int
    machine_no: str
    machine_name: str
    order_id: int
    plan_no: str
    part_id: int
    part_name: str | None
    customer_part_no: str | None
    order_product_id: str
    product_code: Literal["B", "C"]
    route_revision_id: str
    route_code: str
    route_revision: int
    process_code: str
    target_qty: int
    current_qty: int
    difference_qty: int
    production_status: Literal["pending", "in_progress", "completed"]
    version: int
    completed_at: str | None
    completed_by: int | None
    blocked: bool
    allowed_actions: list[Literal["quantity", "complete", "bind", "correct"]]
    boxes: list[ProductionBox]


class ProductionSelection(QrModel):
    context: ProductionContext
    state: ProductionState


class ProductionQuantityResult(QrModel):
    context: ProductionContext | None
    state: ProductionState
    box: ProductBox
    quantity: ProcessQuantity
    allocation: OutputAllocation | None


class ProductionMachine(QrModel):
    id: int
    machine_no: str
    name: str


class MachineScan(QrModel):
    machine: ProductionMachine
    actor: PoolActor
    capabilities: list[Capability]
    scan_ticket: str | None
    context: ProductionContext | None
    state: ProductionState | None
    assignments: list[ProductionState]
    completion_intent: bool


class EventPage(QrModel):
    items: list[FlowEvent]
    next_cursor: str | None
    total: int


class TraceQuantity(ProcessQuantity):
    process_code: str
    machine_id: int
    machine_no: str
    operator_name: str | None


class TraceOrder(QrModel):
    id: int
    plan_no: str
    business_owner_id: int | None


class TraceRoute(QrModel):
    route_code: str
    revision: int
    steps: list[RouteStepRequest]
    first_output_process_code: str


class TraceMaterial(QrModel):
    id: int
    batch_no: str
    parent_batch_id: int | None
    qr_code: str | None
    current_weight: float | None
    thickness: float | None
    width: float | None
    status: str | None
    iqc_result: str | None
    material_name: str | None
    grade: str | None
    depth: int


class TraceRelation(QrModel):
    id: str
    relation_type: str
    parent_box_id: str
    child_box_id: str
    source_order_id: int
    target_order_id: int
    quantity: int
    order_qty: int
    stock_qty: int
    created_by: int
    created_at: str
    source_snapshot: dict[str, Any] = {}
    parent_box_no: str | None = None
    child_box_no: str | None = None
    parent_current_qty: int | None = None
    child_current_qty: int | None = None


class TraceException(QrModel):
    id: str
    status: str
    resolution: str | None
    material_batch_id: int
    created_by: int
    confirmed_by: int | None
    remark: str | None
    created_at: str


class TraceConversion(QrModel):
    id: str
    source_product_code: str
    target_product_code: str
    confirmation_status: str
    actual_qty: int | None
    created_by: int
    confirmed_by: int | None
    remark: str | None
    created_at: str


class SplitTarget(QrModel):
    order_product_id: str
    state_id: str
    state_version: int
    order_id: int
    plan_no: str
    product_name: str | None
    customer_part_no: str | None
    process_code: str
    machine_no: str
    remaining_qty: int


class SplitInfo(QrModel):
    allowed_actions: list[Literal["split", "cross_order_split"]]
    reason: str | None
    available_qty: int
    order_qty: int
    stock_qty: int
    allocation_version: int | None
    targets: list[SplitTarget]
    targets_total: int
    page: int
    page_size: int


class SplitResult(QrModel):
    parent: ProductBox
    child: ProductBox
    relation: TraceRelation
    parent_allocation: OutputAllocation
    child_allocation: OutputAllocation


class BoxTrace(QrModel):
    box: ProductBox
    order: TraceOrder
    route: TraceRoute
    quantities: list[TraceQuantity]
    quantities_total: int
    materials: list[TraceMaterial]
    missing_material_source: bool
    material_lineage_incomplete: bool
    latest_event: FlowEvent | None
    events: EventPage
    page: int
    page_size: int
    relations: list[TraceRelation]
    relations_total: int
    exceptions: list[TraceException]
    exceptions_total: int
    conversions: list[TraceConversion]
    conversions_total: int
    split: SplitInfo | None = None
