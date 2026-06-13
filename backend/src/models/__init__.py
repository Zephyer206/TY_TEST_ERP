"""SQLAlchemy models."""

from .admin import AdminContextSwitch, ContextSwitchType
from .audit import AuditLog
from .customer import Customer
from .machine import Machine, MachineState, MachineStatusLog
from .part import Part, PartState
from .price import AnnualPriceRecord, PriceAccount, PriceAdjustment, PriceAdjustmentType
from .production import (
    PlanMachineAssignment,
    PlanStatus,
    ProcessFlowCard,
    ProcessFlowStatus,
    ProductionPlan,
    ProductionReport,
    ProductionSession,
    SessionStatus,
)
from .coating import CoatingColor, CoatingRecipe, CoatingRecord, CoatingType
from .packaging import (
    Inventory,
    InventoryTransaction,
    PackagingRecord,
    PackagingStatus,
)
from .quote import FixPath, MoldFeeMode, NominationStatus, Quote, QuoteItem, QuoteState, SurfaceTreatment
from .quality import (
    ExemptionType,
    FirstPieceInspection,
    InspectionResult,
    OQCInspection,
    QAExemption,
    PatrolInspection,
)
from .sampling import SamplingTask, SamplingTaskState
from .tooling import Tooling, ToolingPart, ToolingMaintenanceLog, ToolingState
from .user import Department, Position, User
from .warehouse import (
    BatchStatus,
    BatchTransaction,
    IQCResult,
    Material,
    MaterialBatch,
    MaterialBatchChild,
    QRScanLog,
    ScanOperation,
    ScanType,
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
    "NominationStatus",
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
    "QRScanLog",
    "Quote",
    "QuoteItem",
    "QuoteState",
    "SamplingTask",
    "SamplingTaskState",
    "ScanOperation",
    "ScanType",
    "SessionStatus",
    "Supplier",
    "SurfaceTreatment",
    "Tooling",
    "ToolingMaintenanceLog",
    "ToolingPart",
    "ToolingState",
    "User",
]
