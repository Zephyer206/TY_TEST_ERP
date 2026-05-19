"""
app/api/tech_api.py
===================
打样与源头建档路由层 — 技术部专项（JSON API）

职责：接参 → Pydantic 校验 → 调用 Service → JSONResponse
禁止在 Router 层写 SQL 或 if-else 业务逻辑。

路由清单
--------
POST /tech/part/profile          — 源头建档（录入 T/W/P + 模具参数）
GET  /tech/part/{id}            — 读取零件主档
POST /tech/prototype/start       — 连续模打样开机
POST /tech/prototype/report      — 连续模打样报工（填入即生效）
POST /tech/simple-prototype      — 简易模打样（完全线下）
GET  /tech/sample-inventory      — 样件虚拟库视图
GET  /tech/qa-audit             — QA 审计记录查询

前缀: /tech
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user
from app.services.tech_service import (
    create_part_profile,
    get_part_profile,
    start_prototype,
    report_prototype,
    report_simple_prototype,
    get_sample_inventory,
)
from app.services.qa_service import get_qa_audit_logs
from app.models.schemas import (
    PartProfileCreateRequest,
    PartProfileData,
    PrototypeStartRequest,
    PrototypeStartData,
    PrototypeReportRequest,
    PrototypeReportData,
    SimplePrototypeReportRequest,
    SimplePrototypeData,
    SampleInventoryRow,
    QAAuditLogRow,
)

router = APIRouter(prefix="/tech", tags=["tech_api"])


# ============================================================================
# §Tech 源头建档
# ============================================================================

@router.post("/part/profile")
def api_create_part_profile(request: Request, body: PartProfileCreateRequest):
    """
    源头建档 — 录入零件物理基因参数（T/W/P + 模具参数）。

    INSERT parts（mold_cost 已在 quotes 层，parts 表不存金额字段）。

    权限：role_level >= 4（技术部）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需技术部）"}, status_code=403)

    result = create_part_profile(
        part_number=body.part_number,
        internal_name=body.internal_name,
        material_name=body.material_name,
        thickness=body.thickness,
        width=body.width,
        press_stroke=body.press_stroke,
        cavity_count=body.cavity_count,
        mold_tonnage=body.mold_tonnage,
        created_by=user["id"],
    )

    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


@router.get("/part/{part_id}")
def api_get_part_profile(request: Request, part_id: int):
    """
    读取零件主档（含 T/W/P + 模具参数）。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    profile = get_part_profile(part_id)
    if not profile:
        return JSONResponse({"error": f"零件 #{part_id} 不存在"}, status_code=404)

    return JSONResponse({"code": 0, "data": profile})


# ============================================================================
# §Tech 连续模打样（需扫机台 → PROTOTYPING → 填入即生效）
# ============================================================================

@router.post("/prototype/start")
def api_start_prototype(request: Request, body: PrototypeStartRequest):
    """
    连续模打样开机 — 机台进入 PROTOTYPING 状态。

    防呆规则：
      - 机台必须为 IDLE 态
      - 禁止重复 PROTOTYPING 会话

    权限：role_level >= 2（组长）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = start_prototype(machine_id=body.machine_id)

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "不存在" in msg:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


@router.post("/prototype/report")
def api_report_prototype(request: Request, body: PrototypeReportRequest):
    """
    连续模打样报工 — 填入即生效（.cursorrules 打样双轨）。

    执行链路：
      1. 找 PROTOTYPING 会话
      2. 查 cavity_count → 成品量 = qty × cavity_count
      3. 原料扣减：零（打样不计料耗）
      4. sample_inventory.sample_qty += 成品量
      5. 会话 CLOSED + 机台 → IDLE

    权限：role_level >= 2
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = report_prototype(
        machine_id=body.machine_id,
        qty=body.qty,
        operator_id=body.operator_id or user["id"],
    )

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "不存在" in msg:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# §Tech 简易模打样（完全线下，无需扫机台）
# ============================================================================

@router.post("/simple-prototype")
def api_simple_prototype(request: Request, body: SimplePrototypeReportRequest):
    """
    简易模打样 — 完全线下隐形，直接累加 sample_inventory。

    执行链路：
      1. 读取零件 cavity_count
      2. 成品量 = qty × cavity_count
      3. 原料扣减：零
      4. sample_inventory.sample_qty += 成品量
      5. 不写入 production_sessions（完全线下，无系统机台占用）

    权限：role_level >= 2
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = report_simple_prototype(
        part_id=body.part_id,
        qty=body.qty,
        operator_id=body.operator_id or user["id"],
    )

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "不存在" in msg:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# §Tech 辅助查询
# ============================================================================

@router.get("/sample-inventory")
def api_sample_inventory(request: Request, part_id: int = 0):
    """
    查询样件虚拟库（sample_inventory）。

    参数
    ----
    part_id : int 按零件过滤（0 = 全部有库存的零件）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_sample_inventory(
        part_id=part_id if part_id else None,
    )
    return JSONResponse({"code": 0, "data": rows})


@router.get("/qa-audit")
def api_qa_audit(
    request: Request,
    work_order_id: int = 0,
    action_type: str = "",
    limit: int = 50,
):
    """
    查询 QA 审计记录（黑匣子）。

    参数
    ----
    work_order_id : int  按工单过滤（0 = 不限）
    action_type  : str  按动作类型过滤（如 first_piece_release）
    limit        : int  返回条数上限（默认 50）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 3:
        return JSONResponse({"error": "权限不足"}, status_code=403)

    rows = get_qa_audit_logs(
        work_order_id=work_order_id if work_order_id else None,
        action_type=action_type if action_type else None,
        limit=limit,
    )
    return JSONResponse({"code": 0, "data": rows})
