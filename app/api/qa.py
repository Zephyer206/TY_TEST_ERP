"""
app/api/qa.py
=============
品质路由 — 常规首件放行 + 强行特赦（EMERGENCY_RELEASE）

前缀: /qa
"""

from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.qa_service import (
    approve_first_piece,
    emergency_release,
    get_qa_audit_logs,
)

router = APIRouter(prefix="/qa", tags=["qa"])


# ── 常规首件放行页面 ──────────────────────────────────────────────
@router.get("/first-piece", response_class=HTMLResponse)
def first_piece_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("qa/first_piece.html", {
        "request": request, "user": user,
    })


# ── 常规首件放行 API ─────────────────────────────────────────────
@router.post("/first-piece/release")
def qa_first_piece_release(request: Request,
                            work_order_id: int = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 3:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = approve_first_piece(
        work_order_id=work_order_id,
        inspector_id=user["id"],
    )
    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


# ── 强行特赦放行页面 ─────────────────────────────────────────────
@router.get("/emergency-release", response_class=HTMLResponse)
def emergency_release_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("role_level", 0) < 6:
        return HTMLResponse("权限不足：需 admin 级别（role_level >= 6）", status_code=403)
    return templates.TemplateResponse("qa/emergency_release.html", {
        "request": request, "user": user,
    })


# ── 强行特赦放行 API ─────────────────────────────────────────────
@router.post("/emergency-release")
def qa_emergency_release(request: Request,
                         work_order_id: int = Form(...),
                         machine_id: int = Form(0),
                         reason: str = Form(...)):
    """
    强行特赦放行（EMERGENCY_RELEASE）。

    权限：role_level >= 6（admin 级别）
    强制解锁首件限制，同事务写入 qa_audit_logs 黑匣子。

    参数
    ----
    work_order_id : int  工单 ID
    machine_id    : int  关联机台 ID（可传 0，表示无）
    reason        : str  特赦原因（必填，不可为空）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 6:
        return JSONResponse({"code": 1, "message": "权限不足：需 admin 级别"}, status_code=403)

    result = emergency_release(
        work_order_id=work_order_id,
        machine_id=machine_id if machine_id else None,
        admin_id=user["id"],
        reason=reason,
    )
    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


# ── QA 审计日志查询 ─────────────────────────────────────────────
@router.get("/audit-logs/json")
def qa_audit_logs_json(request: Request,
                        work_order_id: int = 0,
                        action_type: str = ""):
    """
    查询 QA 审计黑匣子记录（支持按工单/动作类型过滤）。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    logs = get_qa_audit_logs(
        work_order_id=work_order_id if work_order_id else None,
        action_type=action_type if action_type else None,
    )
    return JSONResponse({"code": 0, "data": logs})
