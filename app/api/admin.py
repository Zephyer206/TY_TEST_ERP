"""
app/api/admin.py
管理部路由 — 机台管理 / 审核
前缀: /admin, /machines, /audit
"""
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.db_service import (
    get_all_machines,
    get_machine_by_id,
    add_machine,
    update_machine,
    tech_intervene,
    tech_complete_fix,
    tech_confirm_mold_offline,
    set_machine_pending_check,
    bind_mold_to_machine,
    set_machine_active_plan,
    get_production_logs_for_audit,
    get_production_summary,
    audit_production_log,
    batch_audit_production_log,
    get_pending_logs_for_dashboard,
    get_tech_time_analytics,
)

router = APIRouter(prefix="", tags=["admin"])


# ── 机台管理 ──────────────────────────────────────────────────────
@router.get("/machines", response_class=HTMLResponse)
def admin_machines_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 3 and user["department"] not in ("tech", "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    machines = get_all_machines()
    return templates.TemplateResponse("admin/machines.html", {
        "request": request, "user": user,
        "machines": machines,
    })


@router.post("/machines/add")
def admin_machines_add(request: Request,
                      machine_number: str = Form(...),
                      machine_name: str = Form(""),
                      press_tonnage: str = Form(""),
                      remark: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="权限不足")
    add_machine(machine_number, machine_name=machine_name,
                press_tonnage=press_tonnage, remark=remark)
    return RedirectResponse("/machines", 303)


@router.post("/machines/{machine_id}/update")
def admin_machines_update(request: Request, machine_id: int,
                         machine_name: str = Form(""),
                         press_tonnage: str = Form(""),
                         status: str = Form(""),
                         remark: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    update_machine(machine_id, machine_name=machine_name,
                   press_tonnage=press_tonnage, status=status, remark=remark)
    return RedirectResponse("/machines", 303)


@router.post("/machines/{machine_id}/tech-intervene")
def machine_tech_intervene(request: Request, machine_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 2 and user["department"] not in ("tech", "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    tech_intervene(machine_id, user["id"])
    return RedirectResponse(request.headers.get("referer", "/machines"), 303)


@router.post("/machines/{machine_id}/tech-complete")
def machine_tech_complete(request: Request, machine_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 2 and user["department"] not in ("tech", "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    tech_complete_fix(machine_id)
    return RedirectResponse(request.headers.get("referer", "/machines"), 303)


@router.post("/machines/{machine_id}/pending-check")
def machine_pending_check(request: Request, machine_id: int):
    user = get_current_user(request)
    if not user or user["role_level"] < 2:
        raise HTTPException(status_code=403, detail="权限不足")
    set_machine_pending_check(machine_id)
    return RedirectResponse(request.headers.get("referer", "/machines"), 303)


# ── 生产报工审核 ─────────────────────────────────────────────────
@router.get("/audit", response_class=HTMLResponse)
def admin_audit_page(request: Request, status_filter: str = "pending"):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    summary = get_production_summary()
    logs = get_production_logs_for_audit(
        status_filter=status_filter if status_filter != "all" else None)
    return templates.TemplateResponse("admin/audit.html", {
        "request": request, "user": user,
        "summary": summary, "logs": logs,
        "status_filter": status_filter,
    })


@router.post("/audit/submit")
def admin_audit_submit(request: Request,
                       log_id: int = Form(...),
                       approved: bool = Form(True)):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    audit_production_log(log_id, user["id"], approved)
    return RedirectResponse("/audit", 303)


@router.post("/audit/batch")
def admin_audit_batch(request: Request,
                      log_ids: str = Form(...),
                      approved: bool = Form(True)):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    ids = [int(x.strip()) for x in log_ids.split(",") if x.strip().isdigit()]
    batch_audit_production_log(ids, user["id"], approved)
    return RedirectResponse("/audit", 303)


# ============================================================================
# 价格管理页面（老板/业务）
# ============================================================================
@router.get("/price-management", response_class=HTMLResponse)
def price_management_page(request: Request):
    """价格管理系统主页面"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    return templates.TemplateResponse("admin/price_management.html", {
        "request": request, "user": user,
    })
