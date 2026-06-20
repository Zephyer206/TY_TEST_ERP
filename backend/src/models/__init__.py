"""SQLAlchemy models."""

from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.machine import Machine, MachineState, MachineStatusLog
from app.models.part import Part, PartState
from app.models.price import AnnualPriceRecord, PriceAccount, PriceAdjustment, PriceAdjustmentType
from app.models.production import (
    MachineAssignment,
    PlanMachineAssignment,
    PlanState,
    ProcessFlowCard,
    ProductionPlan,
    ProductionReport,
    ProductionSession,
    SessionState,
)
from app.models.quote import FixPath, MoldFeeMode, Quote, QuoteItem, QuoteState, SurfaceTreatment
from app.models.sampling import SamplingTask, SamplingTaskState
from app.models.tooling import (
    Tooling,
    ToolingCavityStatus,
    ToolingMaintenanceLog,
    ToolingMaintenanceType,
    ToolingPart,
    ToolingState,
)
from app.models.user import Department, Position, User
from app.models.warehouse import (
    IQCResult,
    MaterialBatch,
    MaterialBatchChild,
    MaterialConsumptionLog,
    MaterialStatus,
    Supplier,
)
from app.models.quality import (
    FirstPieceInspection,
    FirstPieceStatus,
    InspectionResult,
    OQCInspection,
    OQCResult,
    QAExemption,
    PatrolInspection,
)
from app.models.packaging import (
    FinishedGoodsInventory,
    InspectionResult as PkgInspectionResult,
    InventoryTransaction,
    PackagingRecord,
    PackagingStatus,
)
from app.models.coating import (
    CoatingMaterialInventory,
    CoatingRecipe,
    CoatingRecord,
    RecipeStatus,
    RecordStatus,
)
from app.models.admin import (
    AdminAuditLog,
    AdminContextSwitch,
    SwitchTargetRole,
)

__all__ = [
    "AdminAuditLog",
    "AdminContextSwitch",
    "AnnualPriceRecord",
    "AuditLog",
    "CoatingMaterialInventory",
    "CoatingRecipe",
    "CoatingRecord",
    "Customer",
    "Department",
    "FixPath",
    "IQCResult",
    "Machine",
    "MachineAssignment",
    "MachineState",
    "MachineStatusLog",
    "MaterialBatch",
    "MaterialBatchChild",
    "MaterialConsumptionLog",
    "MaterialStatus",
    "MoldFeeMode",
    "Part",
    "PartState",
    "PlanMachineAssignment",
    "PlanState",
    "Position",
    "FirstPieceInspection",
    "FirstPieceStatus",
    "FinishedGoodsInventory",
    "InspectionResult",
    "InventoryTransaction",
    "OQCInspection",
    "OQCResult",
    "PackagingRecord",
    "PackagingStatus",
    "PriceAccount",
    "PriceAdjustment",
    "PriceAdjustmentType",
    "ProcessFlowCard",
    "ProductionPlan",
    "ProductionReport",
    "ProductionSession",
    "QAExemption",
    "PatrolInspection",
    "Quote",
    "QuoteItem",
    "QuoteState",
    "RecipeStatus",
    "RecordStatus",
    "SamplingTask",
    "SamplingTaskState",
    "SessionState",
    "Supplier",
    "SurfaceTreatment",
    "SwitchTargetRole",
    "Tooling",
    "ToolingCavityStatus",
    "ToolingMaintenanceLog",
    "ToolingMaintenanceType",
    "ToolingPart",
    "ToolingState",
    "User",
]
