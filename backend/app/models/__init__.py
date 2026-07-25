"""SQLAlchemy models."""

from .admin import AdminContextSwitch, ContextSwitchType
from .audit import AuditLog
from .customer import Customer
from .die import Die
from .machine import Machine, MachineState, MachineStatusLog
from .part import Part, PartState
from .part_customer_alias import PartCustomerAlias
from .price import (
    CustomerMaterialPrice,
    CustomerTreatmentPrice,
    PriceAccount,
    PriceAdjustment,
    PriceAdjustmentType,
    TreatmentDict,
)
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
from .quote import FixPath, MoldFeeMode, NominationStatus, Quote, QuoteState, SurfaceTreatment
# QuoteItem 暂时注释，云端数据库暂无此表
# from .quote import QuoteItem
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
from .tooling_shared_relation import ToolingSharedRelation
from .tooling_step import ToolingStep
from .tooling_customer_link import ToolingCustomerLink
from .excel_import import ImportBatch, ExcelImportRow
from .user import User  # Department 和 Position 已移除，因为与数据库不匹配
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
# Dictionary tables
from .part_name_dict import PartNameDict
from .material_dict import MaterialDict
from .machine_tonnage_dict import MachineTonnageDict
from .mold_type_dict import MoldTypeDict

__all__ = [
    "AdminContextSwitch",
    "AuditLog",
    "CustomerMaterialPrice",
    "CustomerTreatmentPrice",
    "BatchStatus",
    "BatchTransaction",
    "CoatingColor",
    "CoatingRecipe",
    "CoatingRecord",
    "CoatingType",
    "ContextSwitchType",
    "Customer",
    "Die",
    # "Department",  # 已移除，与数据库不匹配
    "ExcelImportRow",
    "ExemptionType",
    "FirstPieceInspection",
    "FixPath",
    "ImportBatch",
    "IQCResult",
    "InspectionResult",
    "Inventory",
    "InventoryTransaction",
    "Machine",
    "MachineState",
    "MachineStatusLog",
    "MachineTonnageDict",
    "Material",
    "MaterialBatch",
    "MaterialBatchChild",
    "MaterialDict",
    "MoldFeeMode",
    "MoldTypeDict",
    "NominationStatus",
    "OQCInspection",
    "PackagingRecord",
    "PackagingStatus",
    "Part",
    "PartCustomerAlias",
    "PartNameDict",
    "PartState",
    "PatrolInspection",
    "PlanMachineAssignment",
    "PlanStatus",
    # "Position",  # 已移除，与数据库不匹配
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
    # "QuoteItem",  # 暂时注释，云端数据库暂无此表
    "QuoteState",
    "SamplingTask",
    "SamplingTaskState",
    "ScanOperation",
    "ScanType",
    "SessionStatus",
    "Supplier",
    "SurfaceTreatment",
    "Tooling",
    "ToolingCustomerLink",
    "ToolingMaintenanceLog",
    "ToolingPart",
    "ToolingState",
    "ToolingSharedRelation",
    "ToolingStep",
    "TreatmentDict",
    "User",
]
