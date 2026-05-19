"""
app/api/prod_api.py
===================
车间扫码报工路由层 — 高频 JSON API（prod_service 专用）

职责：接参 → Pydantic 校验 → 调用 Service → JSONResponse
禁止在 Router 层写 SQL 或 if-else 业务逻辑。

路由清单
--------
POST /prod/session/start          — 开启会话（连续模专用，Form）
POST /prod/session/close          — 结账会话（连续模专用，Form）
POST /prod/session/takeover       — 强制接班（Form）
POST /prod/simple/report          — 简易模直报（组长下班用，JSON）
GET  /prod/stroke/view            — 报工流水查询（JSON）
GET  /prod/stroke/machine/{id}    — 机台级报工查询（JSON）
GET  /prod/machine/{id}/sessions  — 机台会话历史
GET  /prod/machine/{id}/active-session — 机台当前活跃会话

前缀: /prod
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.services.prod_service_sessions import (
    start_session,
    close_session,
    force_takeover_session,
    get_session_by_machine,
    get_active_session_by_machine,
    report_simple_production,
)
from app.services.prod_service import report_production_with_lock
from app.services.db_service import get_sf_production_logs

router = APIRouter(prefix="/prod", tags=["prod_api"])


# ============================================================================
# §8.1 连续模会话三件套（Form，简易模禁止使用）
# ============================================================================

@router.post("/session/start")
def api_session_start(
    request: Request,
    machine_id: int = Form(...),
    material_qr_uid: str = Form(""),
    operator_id: int = Form(0),
    is_prototype: bool = Form(False),
    work_order_id: int = Form(0),
):
    """
    开启连续模会话（Form 接口，供扫码场景使用）。

    ⚠ 简易模（Simple Die）禁止调用此接口，请使用 /prod/simple/report 直报。

    权限：role_level >= 2（组长/班长）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = start_session(
        machine_id=machine_id,
        material_qr_uid=material_qr_uid if material_qr_uid else None,
        operator_id=operator_id if operator_id else user["id"],
        is_prototype=is_prototype,
        work_order_id=work_order_id if work_order_id else None,
    )

    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


@router.post("/session/close")
def api_session_close(
    request: Request,
    session_id: int = Form(...),
    reported_qty: int = Form(...),
    work_order_id: int = Form(0),
):
    """
    结账连续模会话（Form 接口，供扫码场景使用）。

    ⚠ 简易模（Simple Die）禁止调用此接口，请使用 /prod/simple/report 直报。

    权限：role_level >= 2
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = close_session(
        session_id=session_id,
        reported_qty=reported_qty,
        work_order_id=work_order_id if work_order_id else None,
    )

    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


@router.post("/session/takeover")
def api_session_takeover(
    request: Request,
    machine_id: int = Form(...),
    new_operator_id: int = Form(0),
):
    """
    强制接班（Form 接口）。

    权限：role_level >= 3（主管）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 3:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = force_takeover_session(
        machine_id=machine_id,
        new_operator_id=new_operator_id if new_operator_id else user["id"],
    )

    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


# ============================================================================
# §8.1 简易模直报（组长下班用，无需起机，不碰机台状态）
# ============================================================================

class SimpleProductionRequest(BaseModel):
    """简易模直报请求（组长下班事后录入）。"""
    machine_id:        int = Field(..., description="机台 ID（仅作记录用，不改机台状态）")
    material_batch_id: int = Field(..., gt=0, description="材料批次主键 ID（用于扣重）")
    work_order_id:    int = Field(..., gt=0, description="工单 ID（必须）")
    qty:            int = Field(..., gt=0, description="产出件数，必须 > 0")


class SimpleProductionData(BaseModel):
    """简易模直报响应数据。"""
    session_id:            int     = Field(..., description="会话 ID")
    qty:                  int     = Field(..., description="产出件数")
    wip_added:            int     = Field(..., description="待检库存增量")
    material_deducted_kg: float    = Field(..., description="原料扣减量 kg")


@router.post("/simple/report")
def api_simple_production(request: Request, body: SimpleProductionRequest):
    """
    简易模直报 — 组长下班时事后录入（JSON，Pydantic 校验 qty > 0）。

    ⚠ 核心特征：
      - 无需起机，不改机台状态
      - 直接 INSERT production_sessions (status='CLOSED')
      - 累加 work_orders.wip_pcs
      - 原料扣减（按 material_batch_id）

    执行链路：
      1. 校验工单存在
      2. 读取 material_batches（获取 qr_uid）
      3. INSERT production_sessions (session_type='Simple', status='CLOSED')
      4. 原料扣减
      5. work_orders.wip_pcs += qty

    权限：role_level >= 2（组长）

    返回（失败）
    -------
    - 400：工单/材料批次不存在 / qty <= 0
    - 403：权限不足
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = report_simple_production(
        machine_id=body.machine_id,
        material_batch_id=body.material_batch_id,
        work_order_id=body.work_order_id,
        qty=body.qty,
        leader_id=user["id"],
    )

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "不存在" in msg:
            return JSONResponse(result, status_code=400)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# §8.1 高频冲次报工（JSON，Pydantic 校验 strokes gt=0）
# ============================================================================

class StrokeReportRequest(BaseModel):
    """冲次报工请求。"""
    work_order_id:   int  = Field(..., description="工单 ID")
    equipment_id:    int  = Field(..., description="机台 ID")
    strokes:         int  = Field(..., gt=0, description="冲压次数，必须 > 0")
    material_qr_uid: str | None = Field(None, description="原料批次二维码（扫码，可选）")


@router.post("/stroke/report")
def api_stroke_report(request: Request, body: StrokeReportRequest):
    """
    冲次报工（JSON 接口，Pydantic 校验 strokes > 0）。

    执行链路（Service 层）：
      1. check_all_production_gates() — 4 重门控
      2. strokes × cavity_count → yield_qty
      3. deduct_material_for_report() — 原料扣重
      4. deduct_part_stock() — 成品库存累加
      5. INSERT sf_production_logs
      6. work_orders.produced_qty 累加

    权限：role_level >= 2

    返回（失败）
    -------
    code=1, HTTP 403（首件未放行）/ 409（会话冲突）/ 404（资源不存在）/ 400
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = report_production_with_lock(
        work_order_id=body.work_order_id,
        equipment_id=body.equipment_id,
        strokes=body.strokes,
        operator_id=user["id"],
        material_qr_uid=body.material_qr_uid,
    )

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "首件" in msg or "未放行" in msg:
            return JSONResponse(result, status_code=403)
        if "会话" in msg or "RUNNING" in msg:
            return JSONResponse(result, status_code=409)
        if "不存在" in msg:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# §8.1 报工流水查询
# ============================================================================

@router.get("/stroke/view")
def api_stroke_view(
    request: Request,
    work_order_id: int = 0,
    target_date: str = "",
):
    """
    报工流水视图（JSON）。

    参数
    ----
    work_order_id : int  按工单过滤（0 = 不限）
    target_date   : str  按日期过滤（YYYY-MM-DD，空 = 不限）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_sf_production_logs(
        wo_id=work_order_id if work_order_id else None,
        limit=200,
    )
    return JSONResponse({"code": 0, "data": rows})


@router.get("/stroke/machine/{machine_id}")
def api_stroke_by_machine(request: Request, machine_id: int, limit: int = 50):
    """
    查询某机台的报工记录（JSON）。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_sf_production_logs(
        equipment_id=machine_id,
        limit=limit,
    )
    return JSONResponse({"code": 0, "data": rows})


# ============================================================================
# 辅助查询：机台会话状态
# ============================================================================

@router.get("/machine/{machine_id}/sessions")
def api_machine_sessions(request: Request, machine_id: int):
    """查询某机台的最近会话记录。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    sessions = get_session_by_machine(machine_id)
    return JSONResponse({"code": 0, "data": sessions})


@router.get("/machine/{machine_id}/active-session")
def api_machine_active_session(request: Request, machine_id: int):
    """查询某机台的当前活跃会话。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    session = get_active_session_by_machine(machine_id)
    return JSONResponse({"code": 0, "data": session})
