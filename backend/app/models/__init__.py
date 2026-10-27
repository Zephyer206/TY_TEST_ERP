"""SQLAlchemy models."""

from .admin import AdminContextSwitch, ContextSwitchType
from .after_sales import (
    AfterSalesInstallationKit,
    AfterSalesKitChangeLog,
    AfterSalesKitComponent,
    AfterSalesKitComponentAnnotation,
)
from .gaibo import (
    GaiboAfterSalesCustomer,
    GaiboChangeLog,
    GaiboCustomerRequirement,
    GaiboCustomerWorkspace,
    GaiboDocumentStatus,
    GaiboDrawing,
    GaiboInstallationPackage,
    GaiboPackageItem,
    GaiboProcessRoute,
    GaiboProcessStep,
    GaiboSinglePart,
    GaiboViewPreference,
)
from .audit import AuditLog
from .product_box import (
    ProductRouteRevision, ProductOrderContext, ProductOrderProduct,
    MachineOrderProcessState, MachineProductionContext, ProductQrPoolItem,
    ProductBox, BoxProcessQuantity, ProductOutputAllocation, ProductFlowEvent,
    ProductBoxRelation, CoilSpecException, ProductConversionRecord,
    QrCapabilitySet, QrCapabilityGrant, QrPrintJob, QrPrintJobItem,
    QrPrintConfirmation, QrIdempotencyRecord, ExceptionRecipientGroup,
    NotificationOutbox, QrNotification, QrNotificationAttempt,
)
from .customer import Customer
from .customer_inquiry import CustomerInquiry, CustomerInquiryAttachment
from .quote_group import QuoteGroup, QuoteGroupItem
from .die import Die
from .machine import Machine, MachineState, MachineStatusLog
from .part import Part, PartBOM, PartState
from .part_customer_alias import PartCustomerAlias
from .part_identity_issue import PartIdentityMigrationIssue
from .part_display_group import (
    PartDisplayGroupDef,
    PartDisplayGroupMember,
    SharedFieldGroupDef,
    SharedFieldGroupMember,
)
from .part_tooling_spec import PartToolingSpec
from .price import (
    CustomerMaterialPrice,
    CustomerTreatmentPrice,
    PriceAccount,
    PriceAdjustment,
    PriceAdjustmentType,
    PriceYear,
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
from .nonconforming import NonconformingRecord, NonconformingImportBatch, NonconformingReworkMold
from .shipping_order import (
    ShippingOrder, ShippingOrderLine, ShippingLabelConfirmation,
    ShippingCancellationConsent, ShippingShipment, ShippingShipmentLine,
    ShippingLogistics,
)
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
    "ProductRouteRevision", "ProductOrderContext", "ProductOrderProduct",
    "MachineOrderProcessState", "MachineProductionContext", "ProductQrPoolItem",
    "ProductBox", "BoxProcessQuantity", "ProductOutputAllocation", "ProductFlowEvent",
    "ProductBoxRelation", "CoilSpecException", "ProductConversionRecord",
    "QrCapabilitySet", "QrCapabilityGrant", "QrPrintJob", "QrPrintJobItem",
    "QrPrintConfirmation", "QrIdempotencyRecord", "ExceptionRecipientGroup",
    "NotificationOutbox", "QrNotification", "QrNotificationAttempt",
    "NonconformingImportBatch",
    "NonconformingRecord",
    "NonconformingReworkMold",
    "AdminContextSwitch",
    "AfterSalesInstallationKit",
    "AfterSalesKitChangeLog",
    "AfterSalesKitComponent",
    "AfterSalesKitComponentAnnotation",
    "GaiboAfterSalesCustomer",
    "GaiboChangeLog",
    "GaiboCustomerRequirement",
    "GaiboCustomerWorkspace",
    "GaiboDocumentStatus",
    "GaiboDrawing",
    "GaiboInstallationPackage",
    "GaiboPackageItem",
    "GaiboProcessRoute",
    "GaiboProcessStep",
    "GaiboSinglePart",
    "GaiboViewPreference",
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
    "CustomerInquiry",
    "CustomerInquiryAttachment",
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
    "PartBOM",
    "PartCustomerAlias",
    "PartIdentityMigrationIssue",
    "PartDisplayGroupDef",
    "PartDisplayGroupMember",
    "PartToolingSpec",
    "PartNameDict",
    "PartState",
    "PatrolInspection",
    "PlanMachineAssignment",
    "PlanStatus",
    # "Position",  # 已移除，与数据库不匹配
    "PriceAccount",
    "PriceAdjustment",
    "PriceAdjustmentType",
    "PriceYear",
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
    "SharedFieldGroupDef",
    "SharedFieldGroupMember",
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
    "ShippingOrder",
    "ShippingOrderLine",
    "ShippingLabelConfirmation",
    "ShippingCancellationConsent",
    "ShippingShipment",
    "ShippingShipmentLine",
    "ShippingLogistics",
]

# PPAP metadata is included in Alembic discovery without changing legacy exports.
from app.models.ppap import PpapArchive, PpapFolder, PpapDocument, PpapFileVersion, PpapSubmission, PpapAuditLog

from app.models.workbench_assignment import WorkbenchAssignment, WorkbenchAssignmentEvent
