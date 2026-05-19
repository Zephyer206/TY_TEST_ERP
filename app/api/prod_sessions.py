"""
app/api/prod_sessions.py
=======================
生产会话路由 — 开启 / 结账 / 强制接班

前缀: /prod/sessions
"""

from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.prod_service_sessions import (
    start_session,
    close_session,
    force_takeover_session,
    get_session_by_machine,
    get_active_session_by_machine,
)

router = APIRouter(prefix="/prod/sessions", tags=["prod_sessions"])


# ── 开启会话页面 ─────────────────────────────────────────────────
@router.get("/start", response_class=HTMLResponse)
def session_start_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("prod/session_start.html", {
        "request": request, "user": user,
    })


# ── 开启会话 API ────────────────────────────────────────────────
@router.post("/start")
def api_start_session(request: Request,
                       machine_id: int = Form(...),
                       material_qr_uid: str = Form(""),
                       operator_id: int = Form(0),
                       is_prototype: bool = Form(False),
                       work_order_id: int = Form(0)):
    """
    开启连续模会话（.cursorrules §8.1 连续模专用）。

    ⚠ 简易模（Simple Die）请使用 /prod/simple/report 直报接口，禁止调用此接口。

    参数
    ----
    machine_id       : int   机台 ID
    material_qr_uid : str   原料批次二维码
    operator_id     : int   操作工 ID
    is_prototype    : bool  True = 打样（连续模打样）
    work_order_id   : int   工单 ID

    返回
    ----
    {"code": 0/1, "message": str,
     "data": {session_id, machine_id, session_type, status, start_time}}
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


# ── 结账会话 API ────────────────────────────────────────────────
@router.post("/close")
def api_close_session(request: Request,
                       session_id: int = Form(...),
                       reported_qty: int = Form(...),
                       work_order_id: int = Form(0)):
    """
    结账连续模会话（.cursorrules §8.1 连续模专用）。

    ⚠ 简易模（Simple Die）请使用 /prod/simple/report 直报，禁止调用此接口。

    参数
    ----
    session_id    : int  会话 ID
    reported_qty : int  本次报工产出件数
    work_order_id : int 工单 ID（用于料耗溯源，可传 0）

    返回
    ----
    {
        "code": 0/1,
        "message": str,
        "data": {session_id, reported_qty, wip_added, material_deducted_kg}
    }
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


# ── 强制接班 API ────────────────────────────────────────────────
@router.post("/takeover")
def api_force_takeover(request: Request,
                        machine_id: int = Form(...),
                        new_operator_id: int = Form(0)):
    """
    强制接班（将旧会话标记为 ABNORMAL_TERMINATED，开新会话）。

    参数
    ----
    machine_id      : int  机台 ID
    new_operator_id : int  新接班人 ID
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


# ── 查询机台会话状态 ───────────────────────────────────────────
@router.get("/machine/{machine_id}/sessions")
def machine_sessions(request: Request, machine_id: int):
    """查询某机台最近的 20 条会话记录。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    sessions = get_session_by_machine(machine_id)
    return JSONResponse({"code": 0, "data": sessions})


@router.get("/machine/{machine_id}/active")
def machine_active_session(request: Request, machine_id: int):
    """查询某机台的当前活跃会话（RUNNING 或 PENDING_REPORT）。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    session = get_active_session_by_machine(machine_id)
    return JSONResponse({"code": 0, "data": session})
