"""SQLAlchemy models."""

from app.models.admin import AdminContextSwitch, ContextSwitchType
from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.machine import Machine, MachineState, MachineStatusLog
from app.models.part import Part, PartState
from app.models.price import AnnualPriceRecord, PriceAccount, PriceAdjustment, PriceAdjustmentType
from app.models.production import (
    PlanMachineAssignment,
    PlanStatus,
    ProcessFlowCard,
    ProcessFlowStatus,
    ProductionPlan,
    ProductionReport,
    ProductionSession,
    SessionStatus,
)
from app.models.coating import CoatingColor, CoatingRecipe, CoatingRecord, CoatingType
from app.models.packaging import (
    Inventory,
    InventoryTransaction,
    PackagingRecord,
    PackagingStatus,
)
from app.models.quote import FixPath, MoldFeeMode, Quote, QuoteItem, QuoteState, SurfaceTreatment
from app.models.quality import (
    ExemptionType,
    FirstPieceInspection,
    InspectionResult,
    OQCInspection,
    QAExemption,
    PatrolInspection,
)
from app.models.sampling import SamplingTask, SamplingTaskState
from app.models.tooling import Tooling, ToolingPart, ToolingMaintenanceLog, ToolingState
from app.models.user import Department, Position, User
from app.models.warehouse import (
    BatchStatus,
    BatchTransaction,
    IQCResult,
    Material,
    MaterialBatch,
    MaterialBatchChild,
    Supplier,
)

__all__ = [
    "AdminContextSwitch",
    "AnnualPriceRecord",
    "AuditLog",
    "BatchStatus",
    "BatchTransaction",
    "CoatingColor",
    "CoatingRecipe",
    "CoatingRecord",
    "CoatingType",
    "ContextSwitchType",
    "Customer",
    "Department",
    "ExemptionType",
    "FirstPieceInspection",
    "FixPath",
    "IQCResult",
    "InspectionResult",
    "Inventory",
    "InventoryTransaction",
    "Machine",
    "MachineState",
    "MachineStatusLog",
    "Material",
    "MaterialBatch",
    "MaterialBatchChild",
    "MoldFeeMode",
    "OQCInspection",
    "PackagingRecord",
    "PackagingStatus",
    "Part",
    "PartState",
    "PatrolInspection",
    "PlanMachineAssignment",
    "PlanStatus",
    "Position",
    "PriceAccount",
    "PriceAdjustment",
    "PriceAdjustmentType",
    "ProcessFlowCard",
    "ProcessFlowStatus",
    "ProductionPlan",
    "ProductionReport",
    "ProductionSession",
    "QAExemption",
    "Quote",
    "QuoteItem",
    "QuoteState",
    "SamplingTask",
    "SamplingTaskState",
    "SessionStatus",
    "Supplier",
    "SurfaceTreatment",
    "Tooling",
    "ToolingMaintenanceLog",
    "ToolingPart",
    "ToolingState",
    "User",
]
