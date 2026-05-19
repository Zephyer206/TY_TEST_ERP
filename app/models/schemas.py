"""
app/models/schemas.py
====================
Pydantic 请求/响应模型 — 仅用于 FastAPI 参数校验。

规范
----
- 严禁在此文件执行任何数据库操作（零 SQL）
- 严禁引入 psycopg2 / SQLAlchemy
- FastAPI 路由使用这些 schema 做自动参数校验和 OpenAPI 文档
"""

from pydantic import BaseModel, Field
from typing import Optional
import datetime


# ============================================================================
# §8.1 报工相关
# ============================================================================

class ProductionReportRequest(BaseModel):
    work_order_id:  int      = Field(..., description="工单 ID")
    equipment_id:   int      = Field(..., description="机台 ID")
    strokes:        int      = Field(..., gt=0, description="冲压次数，必须 > 0")
    material_qr_uid: Optional[str] = Field(None, description="原料批次码（扫码，可选）")
    actual_date:    Optional[str]  = Field(None, description="业务发生日期（YYYY-MM-DD）")


class ProductionReportData(BaseModel):
    log_id:                 int     = Field(..., description="报工流水 ID")
    yield_qty:              int     = Field(..., description="本次产出件数")
    strokes:                int     = Field(..., description="冲压次数")
    cavity_count:           int     = Field(..., description="模具穴数")
    material_consumed_kg:   float   = Field(..., description="原料消耗 kg")
    produced_qty_total:     int     = Field(..., description="工单累计产出")
    target_qty:             int     = Field(..., description="工单目标量")
    is_completed:           bool    = Field(..., description="工单是否已完成")


class ProductionReportResponse(BaseModel):
    code:    int = Field(..., description="0=成功，1=拒绝")
    message: str = Field(..., description="返回说明")
    data:    Optional[ProductionReportData] = Field(None)


# ============================================================================
# §8.2 维修相关
# ============================================================================

class MaintenanceTriggerRequest(BaseModel):
    equipment_id: int      = Field(..., description="机台 ID")
    mold_id:      Optional[int] = Field(None, description="关联模具 ID（MOLD_* 模式必填）")
    repair_mode:  str      = Field(..., description="MOLD_DISMOUNTED | MOLD_ON_MACHINE | MACHINE_REPAIR")
    fault_reason: str      = Field("", description="故障描述")


class MaintenanceCompleteRequest(BaseModel):
    maintenance_log_id: int  = Field(..., description="维修记录 ID")
    resolved:           bool = Field(True, description="True=完成，False=撤销")
    remarks:            str  = Field("", description="维修备注")


class MaintenanceTriggerData(BaseModel):
    maintenance_log_id:    int          = Field(..., description="维修记录 ID")
    equipment_id:          int          = Field(..., description="机台 ID")
    mold_id:               Optional[int] = Field(None, description="模具 ID")
    repair_mode:           str          = Field(..., description="维修模式")
    new_equipment_status: str          = Field(..., description="机台新状态")
    new_mold_status:       Optional[str] = Field(None, description="模具新状态")


class MaintenanceResolveData(BaseModel):
    maintenance_log_id: int          = Field(..., description="维修记录 ID")
    maint_status:       str          = Field(..., description="维修记录状态 RESOLVED/CANCELLED")
    equipment_id:       Optional[int] = Field(None, description="机台 ID")
    equipment_status:    Optional[str] = Field(None, description="机台新状态")
    mold_id:            Optional[int] = Field(None, description="模具 ID")
    mold_status:        Optional[str] = Field(None, description="模具新状态")


class MaintenanceResponse(BaseModel):
    code:    int = Field(..., description="0=成功，1=失败")
    message: str = Field(..., description="返回说明")
    data:    Optional[dict] = Field(None, description="操作详情")


# ============================================================================
# §8.3 发货相关
# ============================================================================

class DeliveryItemRow(BaseModel):
    delivery_item_id:  int          = Field(..., description="发货明细 ID")
    part_id:           int          = Field(..., description="内部零件 ID")
    internal_part_no:   str          = Field(..., description="内部件号")
    internal_name:      str          = Field(..., description="内部零件名称")
    display_part_no:   str          = Field(..., description="展示件号（翻译后）")
    display_name:      str          = Field(..., description="展示名称（翻译后）")
    qty:               int          = Field(..., description="发货数量")
    lot_no:            Optional[str] = Field(None, description="批号")
    remark:            Optional[str] = Field(None, description="备注")
    alias_status: str = Field(..., description="ALIAS_OK | PENDING_CONFIG")


class DeliveryConfirmRequest(BaseModel):
    dn_id:        int = Field(..., description="发货单 ID")
    operator_id: int = Field(..., description="操作人用户 ID")


class DeliveryConfirmData(BaseModel):
    dn_id:            int = Field(..., description="发货单 ID")
    shipped_count:    int = Field(..., description="实际发货件数")
    stock_deducted:   int = Field(..., description="库存扣减件数")


# ============================================================================
# §8.1 QA 首件与特赦
# ============================================================================

class FirstPieceReleaseRequest(BaseModel):
    work_order_id: int = Field(..., description="工单 ID")


class EmergencyReleaseRequest(BaseModel):
    work_order_id: int = Field(..., description="工单 ID")
    machine_id:    Optional[int] = Field(None, description="关联机台 ID")
    reason:        str = Field(..., description="特赦原因（必填）")


class QAAuditLogRow(BaseModel):
    id:           int = Field(..., description="审计日志 ID")
    work_order_id: int = Field(..., description="工单 ID")
    machine_id:   Optional[int] = Field(None, description="机台 ID")
    operator_id:  Optional[int] = Field(None, description="操作员 ID")
    action_type:  str = Field(..., description="动作类型")
    reason:       Optional[str] = Field(None, description="原因")
    created_at:   datetime.datetime = Field(..., description="操作时间")


# ============================================================================
# §8.1 生产会话
# ============================================================================

class SessionStartRequest(BaseModel):
    """开启会话请求（连续模专用，简易模请用 SimpleProductionRequest）。"""
    machine_id:       int  = Field(..., description="机台 ID")
    material_qr_uid: Optional[str] = Field(None, description="原料批次二维码")
    operator_id:    Optional[int] = Field(None, description="操作工 ID")
    is_prototype:   bool = Field(False, description="True=打样（连续模打样）")
    work_order_id:  Optional[int] = Field(None, description="绑定工单 ID")


class SessionStartData(BaseModel):
    session_id:    int = Field(..., description="会话 ID")
    machine_id:   int = Field(..., description="机台 ID")
    session_type:  str = Field(..., description="Continuous | Simple")
    status:        str = Field(..., description="会话状态")
    start_time:    Optional[str] = Field(None, description="开始时间 ISO")


class SessionCloseRequest(BaseModel):
    session_id:     int = Field(..., description="会话 ID")
    reported_qty:  int = Field(..., ge=0, description="本次产出件数")
    work_order_id: Optional[int] = Field(None, description="工单 ID（料耗溯源）")


class SessionCloseData(BaseModel):
    session_id:            int = Field(..., description="会话 ID")
    reported_qty:         int = Field(..., description="产出件数")
    wip_added:            int = Field(..., description="待检库存增量")
    material_deducted_kg: float = Field(..., description="原料扣减量 kg")


class ForceTakeoverRequest(BaseModel):
    machine_id:       int = Field(..., description="机台 ID")
    new_operator_id: int = Field(..., description="新接班人 ID")


# ============================================================================
# §8.3 全检入库
# ============================================================================

class StockInRequest(BaseModel):
    work_order_id: int = Field(..., description="工单 ID")
    valid_qty:    int = Field(..., gt=0, description="合格入库件数（>0）")
    reject_qty:  int = Field(0, ge=0, description="不良品件数")


class StockInData(BaseModel):
    work_order_id:  int = Field(..., description="工单 ID")
    valid_qty:     int = Field(..., description="入库件数")
    reject_qty:    int = Field(..., description="不良件数")
    wip_remaining: int = Field(..., description="入库后剩余待检量")
    stock_added:   int = Field(..., description="成品库存新增量")
    defect_log_id: Optional[int] = Field(None, description="不良品日志 ID")


class DefectLogRow(BaseModel):
    id:             int = Field(..., description="不良品日志 ID")
    work_order_id:  int = Field(..., description="工单 ID")
    defect_qty:     int = Field(..., description="不良件数")
    reason:         Optional[str] = Field(None, description="不良原因")
    reporter_id:    Optional[int] = Field(None, description="填报人 ID")
    created_at:     datetime.datetime = Field(..., description="记录时间")


class WipRow(BaseModel):
    work_order_id:  int = Field(..., description="工单 ID")
    order_no:       str = Field(..., description="工单号")
    part_id:        int = Field(..., description="零件 ID")
    part_number:    str = Field(..., description="件号")
    internal_name:  str = Field(..., description="零件名称")
    wip_pcs:        int = Field(..., description="待检库存")
    produced_qty:   int = Field(..., description="累计产出")
    target_qty:     int = Field(..., description="目标量")
    order_status:   str = Field(..., description="工单状态")


# ============================================================================
# §Tech 打样相关（tech_api.py）
# ============================================================================

class PartProfileCreateRequest(BaseModel):
    """源头建档：录入 T/W/P + 模具参数。"""
    part_number:  str   = Field(..., min_length=1, description="零件号（必须唯一）")
    internal_name: str  = Field(..., min_length=1, description="内部名称")
    material_name: str  = Field(..., min_length=1, description="材料牌号")
    thickness:     float = Field(..., gt=0, description="料厚 T（mm），必须 > 0")
    width:         float = Field(..., gt=0, description="宽度 W（mm），必须 > 0")
    press_stroke: float = Field(..., gt=0, description="步距 P（mm），必须 > 0")
    cavity_count: int   = Field(1, ge=1, description="出数（≥1），默认 1")
    mold_tonnage: float  = Field(0.0, ge=0, description="要求吨位（≥0）")


# ============================================================================
# §Sales 销售新建零件（part_create.html → POST /api/parts/create）
# ============================================================================

class PartCreateRequest(BaseModel):
    """销售部新建零件 → 双表事务（parts + molds + quotes）。

    字段名与前端 part_create.html 表单的 name= 属性严格对齐。
    """
    part_number:          str   = Field(..., min_length=1, description="零件图号（唯一）")
    internal_name:        str   = Field(..., min_length=1, description="内部件号名称")
    material_name:        str   = Field("", description="材料牌号")
    pricing_mode:         str   = Field("independent", description="报价模式: independent / reference")
    referenced_part_id:   Optional[int] = Field(None, description="关联参考件 ID（路径 A）")
    thickness:            Optional[float] = Field(None, description="厚度 T (mm)")
    width:                Optional[float] = Field(None, description="宽度 W (mm)")
    press_stroke:         Optional[float] = Field(None, description="冲压行程 P (mm)")
    cavity_count:         int   = Field(1, ge=1, description="穴数（≥1）")
    material_utilization: float = Field(100.0, ge=0, le=100, description="材料利用率 (%)")
    machine_type:         Optional[str] = Field(None, max_length=50, description="设备吨位/型号")
    press_tonnage:        int   = Field(0, ge=0, description="模具吨位 (整数吨)")
    stamping_fee:         Optional[float] = Field(None, ge=0, description="冲压费（元/件）")
    surface_fee:          Optional[float] = Field(None, ge=0, description="表面处理费（元/件）")
    profit_margin:        Optional[float] = Field(None, ge=0, le=100, description="利润率 (%)")
    final_price_override: Optional[float] = Field(None, ge=0, description="手动覆盖总价（元/件）")
    customer_id:          Optional[int] = Field(None, description="客户 ID")
    alias_part_number:    Optional[str] = Field("", description="客户件号别名")
    operator_id:          Optional[int] = Field(None, description="操作员 ID")


class PartProfileData(BaseModel):
    part_id:       int    = Field(..., description="零件 ID")
    part_number:   str    = Field(..., description="零件号")
    internal_name: str    = Field(..., description="内部名称")


class PrototypeStartRequest(BaseModel):
    """连续模打样开机。"""
    machine_id: int = Field(..., description="机台 ID")


class PrototypeStartData(BaseModel):
    session_id:    int    = Field(..., description="会话 ID")
    machine_id:   int    = Field(..., description="机台 ID")
    session_type: str    = Field(..., description="Prototype")
    status:       str    = Field(..., description="RUNNING")
    start_time:   Optional[str] = Field(None, description="开始时间 ISO")


class PrototypeReportRequest(BaseModel):
    """连续模打样报工（填入即生效）。"""
    machine_id:  int = Field(..., description="机台 ID")
    qty:        int = Field(..., gt=0, description="冲次，必须 > 0")
    operator_id: Optional[int] = Field(None, description="操作工 ID")


class PrototypeReportData(BaseModel):
    session_id:    int = Field(..., description="会话 ID")
    qty:          int = Field(..., description="冲次")
    cavity_count: int = Field(..., description="穴数")
    sample_added: int = Field(..., description="样件入库件数")


class SimplePrototypeReportRequest(BaseModel):
    """简易模打样（完全线下，不扫机台）。"""
    part_id:     int = Field(..., description="零件 ID")
    qty:        int = Field(..., gt=0, description="产出件数，必须 > 0")
    operator_id: Optional[int] = Field(None, description="操作人 ID")


class SimplePrototypeData(BaseModel):
    part_id:      int = Field(..., description="零件 ID")
    qty:         int = Field(..., description="输入件数")
    cavity_count: int = Field(..., description="穴数")
    sample_added: int = Field(..., description="入库件数")
    sample_total: int = Field(..., description="累计样件库存")


class SampleInventoryRow(BaseModel):
    part_id:      int    = Field(..., description="零件 ID")
    part_number:  str    = Field(..., description="零件号")
    internal_name: str   = Field(..., description="零件名称")
    sample_qty:  int    = Field(..., description="样件库存")
    updated_at:  datetime.datetime = Field(..., description="更新时间")


# ============================================================================
# §QA 品质放行相关（qa_api.py）
# ============================================================================

class FirstPieceApproveRequest(BaseModel):
    """常规首件放行。"""
    work_order_id: int = Field(..., description="工单 ID")


class FirstPieceApproveData(BaseModel):
    work_order_id: int    = Field(..., description="工单 ID")
    released_at:   str    = Field(..., description="放行时间 ISO")


class EmergencyReleaseRequest(BaseModel):
    """强行特赦放行（Emergency Release）。"""
    work_order_id: int  = Field(..., description="工单 ID")
    machine_id:    Optional[int] = Field(None, description="关联机台 ID")
    reason:        str  = Field(..., min_length=1, description="特赦原因（必填）")


class EmergencyReleaseData(BaseModel):
    work_order_id: int    = Field(..., description="工单 ID")
    released_at:   str    = Field(..., description="放行时间 ISO")
    audit_log_id:  int    = Field(..., description="审计日志 ID")


class QAAuditLogRow(BaseModel):
    """QA 审计日志行。"""
    id:            int     = Field(..., description="日志 ID")
    work_order_id: int    = Field(..., description="工单 ID")
    machine_id:    Optional[int] = Field(None, description="机台 ID")
    operator_id:   Optional[int] = Field(None, description="操作员 ID")
    operator_name: Optional[str] = Field(None, description="操作员姓名")
    action_type:   str    = Field(..., description="动作类型")
    reason:        Optional[str] = Field(None, description="原因")
    created_at:    datetime.datetime = Field(..., description="操作时间")


# ============================================================================
# §PKG 包装结案相关（pkg_api.py）
# ============================================================================

class ForceClosePackingRequest(BaseModel):
    """倒推结案：强制关闭工单包装阶段。"""
    work_order_id: int = Field(..., description="工单 ID")


class ForceClosePackingData(BaseModel):
    work_order_id:  int            = Field(..., description="工单 ID")
    wip_remaining:  int            = Field(..., description="结案前剩余 WIP")
    defect_log_id: Optional[int]   = Field(None, description="静默转入 defect_logs 的记录 ID")
    is_pkg_closed: bool           = Field(..., description="是否已关闭")


class StockInData(BaseModel):
    """全检入库响应数据。"""
    work_order_id:  int            = Field(..., description="工单 ID")
    valid_qty:     int            = Field(..., description="合格入库件数")
    reject_qty:    int            = Field(..., description="不良件数")
    wip_remaining:  int            = Field(..., description="入库后剩余待检量")
    stock_added:   int            = Field(..., description="成品库存新增量")
    stock_total:   int            = Field(..., description="成品库存总量")
    defect_log_id: Optional[int]   = Field(None, description="不良品日志 ID")


class StockInRequest(BaseModel):
    """全检入库请求（用于 JSON API）。"""
    work_order_id: int = Field(..., description="工单 ID")
    valid_qty:    int = Field(..., gt=0, description="合格入库件数，必须 > 0")
    reject_qty:  int = Field(0, ge=0, description="不良品件数（≥0）")


class PkgWipRow(BaseModel):
    """待检库存视图行（pkg_api 用）。"""
    work_order_id: int    = Field(..., description="工单 ID")
    order_no:      str    = Field(..., description="工单号")
    part_id:       int    = Field(..., description="零件 ID")
    part_number:   str    = Field(..., description="件号")
    internal_name: str    = Field(..., description="零件名称")
    wip_pcs:       int    = Field(..., description="待检库存")
    produced_qty:  int    = Field(..., description="累计产出")
    target_qty:   int    = Field(..., description="目标量")
    order_status:  str    = Field(..., description="工单状态")
