"""
app/api/pkg_api.py
==================
包装结案路由层 — 全检入库 + 倒推结案（JSON API）

职责：接参 → Pydantic 校验 → 调用 Service → JSONResponse
禁止在 Router 层写 SQL 或 if-else 业务逻辑。

路由清单
--------
POST /pkg/stock/in                 — 全检入库（JSON，valid_qty > 0）
POST /pkg/stock/force-close       — 倒推结案（JSON，强制关闭包装阶段）
GET  /pkg/stock/wip                — 待检库存视图（JSON）
GET  /pkg/stock/defects            — 不良品记录查询（JSON）
GET  /pkg/stock/wip/{wo_id}       — 工单级待检详情（JSON）

前缀: /pkg
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user
from app.services.pkg_service import (
    pack_and_stock,
    force_close_packing,
    get_wip_overview,
    get_defect_logs,
)
from app.models.schemas import (
    StockInRequest,
    StockInData,
    ForceClosePackingRequest,
    ForceClosePackingData,
    PkgWipRow,
    DefectLogRow,
)

router = APIRouter(prefix="/pkg", tags=["pkg_api"])


# ============================================================================
# §8.3 全检入库（Pack & Stock — 流水线终点）
# ============================================================================

@router.post("/stock/in")
def api_stock_in(request: Request, body: StockInRequest):
    """
    全检入库 — 流水线终点核心操作（JSON，Pydantic 校验 gt=0）。

    执行链路（Service 层）：
      1. 校验工单状态（RUNNING / COMPLETED）
      2. 校验 wip_pcs >= valid_qty（防止超额入库）
      3. work_orders.wip_pcs -= valid_qty（扣除待检）
      4. parts.stock_pcs += valid_qty（增加成品库存）
      5. INSERT defect_logs（如有 reject_qty）
      6. INSERT stock_in_logs（入库流水追溯）

    入库条件：
      - valid_qty > 0（Pydantic gt=0 硬性校验）
      - 工单状态：RUNNING / COMPLETED
      - wip_pcs >= valid_qty

    权限：role_level >= 3（包装部）

    返回（失败）
    -------
    - 400：wip_pcs 不足 / 状态不允许入库 / valid_qty <= 0
    - 403：权限不足
    - 404：工单不存在
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 3:
        return JSONResponse({"code": 1, "message": "权限不足（需包装部）"}, status_code=403)

    result = pack_and_stock(
        work_order_id=body.work_order_id,
        valid_qty=body.valid_qty,
        operator_id=user["id"],
        reject_qty=body.reject_qty,
    )

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "不存在" in msg:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# §8.3 倒推结案（Force Close Packing）
# ============================================================================

@router.post("/stock/force-close")
def api_force_close_packing(request: Request, body: ForceClosePackingRequest):
    """
    倒推结案 — 强制关闭工单包装阶段（JSON）。

    业务场景：工单处于失控状态（WIP 散落在各工序，无法追回），
    由管理员强制关闭，系统将剩余 WIP 静默转入 defect_logs。

    执行链路：
      1. 读取 work_orders.wip_pcs（FOR UPDATE 行锁）
      2. UPDATE work_orders SET wip_pcs=0, is_pkg_closed=TRUE
      3. 若 wip_before > 0：INSERT defect_logs（source='Auto_Deduction'）

    静默转损耗：操作不留弹窗，不发通知，确保生产数据闭环。

    权限：role_level >= 5（高级主管）

    返回（失败）
    -------
    - 400：工单不存在
    - 403：权限不足
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 5:
        return JSONResponse({"code": 1, "message": "权限不足（需高级主管）"}, status_code=403)

    result = force_close_packing(
        work_order_id=body.work_order_id,
        operator_id=user["id"],
    )

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "不存在" in msg:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# §8.3 辅助查询：待检库存 + 不良品
# ============================================================================

@router.get("/stock/wip")
def api_wip_overview(request: Request, work_order_id: int = 0):
    """
    查询待检库存（wip_pcs）视图。

    参数
    ----
    work_order_id : int  按工单过滤（0 = 返回全部有 WIP 的工单）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_wip_overview(
        work_order_id=work_order_id if work_order_id else None,
    )
    return JSONResponse({"code": 0, "data": rows})


@router.get("/stock/wip/{work_order_id}")
def api_wip_detail(request: Request, work_order_id: int):
    """
    查询指定工单的待检库存详情。

    权限：登录即可
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_wip_overview(work_order_id=work_order_id)
    if not rows:
        return JSONResponse({"code": 0, "data": None})
    return JSONResponse({"code": 0, "data": rows[0]})


@router.get("/stock/defects")
def api_defect_logs(
    request: Request,
    work_order_id: int = 0,
    limit: int = 50,
):
    """
    查询不良品记录（defect_logs）。

    参数
    ----
    work_order_id : int  按工单过滤（0 = 全部）
    limit         : int  返回条数上限（默认 50）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_defect_logs(
        work_order_id=work_order_id if work_order_id else None,
        limit=limit,
    )
    return JSONResponse({"code": 0, "data": rows})
