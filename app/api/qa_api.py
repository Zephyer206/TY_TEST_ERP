"""
app/api/qa_api.py
=================
品质放行路由层 — 常规首件 + 强行特赦（JSON API）

职责：接参 → Pydantic 校验 → 调用 Service → JSONResponse
禁止在 Router 层写 SQL 或 if-else 业务逻辑。

路由清单
--------
POST /qa/first-piece/approve       — 常规首件放行（JSON）
GET  /qa/first-piece/{wo_id}      — 查询工单首件状态
POST /qa/emergency/release         — 强行特赦放行（JSON，含 reason 必填）
GET  /qa/audit/logs               — QA 审计记录查询

前缀: /qa
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user
from app.services.qa_service import (
    approve_first_piece,
    emergency_release,
    get_qa_audit_logs,
)
from app.models.schemas import (
    FirstPieceApproveRequest,
    FirstPieceApproveData,
    EmergencyReleaseRequest,
    EmergencyReleaseData,
    QAAuditLogRow,
)

router = APIRouter(prefix="/qa", tags=["qa_api"])


# ============================================================================
# §8.1 常规首件放行
# ============================================================================

@router.post("/first-piece/approve")
def api_first_piece_approve(request: Request, body: FirstPieceApproveRequest):
    """
    常规首件合格放行（JSON，Pydantic 校验）。

    执行链路：
      1. 校验工单存在，未重复放行
      2. UPDATE work_orders SET first_piece_passed_at = NOW()
      3. INSERT qa_audit_logs（记录放行动作）

    权限：role_level >= 3（品质部）

    返回（失败）
    -------
    - 400：工单不存在 / 已放行
    - 403：权限不足
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 3:
        return JSONResponse({"code": 1, "message": "权限不足（需品质部）"}, status_code=403)

    result = approve_first_piece(
        work_order_id=body.work_order_id,
        inspector_id=user["id"],
    )

    if result.get("code") == 1:
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# §8.1 强行特赦放行（Emergency Release）
# ============================================================================

@router.post("/emergency/release")
def api_emergency_release(request: Request, body: EmergencyReleaseRequest):
    """
    强行特赦放行 — 无视原状态解锁报工限制（JSON，Pydantic 校验）。

    业务场景：首件检验未完成或品质存疑，但因紧急交期等特殊原因，
    由管理员强行解锁报工限制。

    执行链路：
      1. 校验 reason 非空（.cursorrules §8.1 审计黑匣子不留白）
      2. 强制 SET first_piece_passed_at = NOW()
      3. INSERT qa_audit_logs（含 reason 字段）

    权限：role_level >= 6（admin）

    返回（失败）
    -------
    - 400：reason 为空 / 工单不存在
    - 403：权限不足
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 6:
        return JSONResponse({"code": 1, "message": "权限不足（需 admin）"}, status_code=403)

    result = emergency_release(
        work_order_id=body.work_order_id,
        machine_id=body.machine_id,
        admin_id=user["id"],
        reason=body.reason,
    )

    if result.get("code") == 1:
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# 辅助查询：QA 审计日志
# ============================================================================

@router.get("/audit/logs")
def api_audit_logs(
    request: Request,
    work_order_id: int = 0,
    action_type: str = "",
    limit: int = 50,
):
    """
    查询 QA 审计日志（黑匣子，支持溯源）。

    参数
    ----
    work_order_id : int  按工单过滤（0 = 不限）
    action_type  : str  按动作类型过滤
                   合法值：first_piece_release | emergency_release
    limit        : int  返回条数上限（默认 50）

    权限：role_level >= 3（品质部）
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
