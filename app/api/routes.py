"""
app/api/routes.py - All FastAPI route handlers
"""

from fastapi import APIRouter, Form, Request, Response, Depends, HTTPException, UploadFile, File
router = APIRouter()
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import quote, unquote
import re, datetime, os, uuid, qrcode, io

from app.core.auth import get_current_user, can_bypass_dept, require_login
from app.services.db_service import (
    audit_production_log,
    batch_audit_production_log,
    check_machine_active_plan,
    check_material_qualified,
    count_mold_status_all,
    count_oqc_reports,
    count_pending_quotes,
    ensure_inbound_orders_table,
    get_all_machines,
    get_all_parts,
    get_all_urgent_parts,
    get_all_material_base_prices,
    get_blocked_parts,
    get_daily_dashboard_stats,
    get_factory_utilization,
    get_inbound_summary,
    get_machine_by_id,
    get_machine_plans,
    get_machines_with_faults,
    get_material_alerts,
    get_oqc_reports,
    get_overdue_summary,
    get_boss_kpi,
    get_part_by_id,
    get_part_progress,
    get_pending_inbound_orders,
    get_pending_logs_for_dashboard,
    get_period_summary,
    get_pkg_blocked_parts,
    get_pkg_error_logs,
    get_pkg_ready_inventory,
    get_pkg_today_summary,
    get_production_logs,
    get_production_logs_for_audit,
    get_production_summary,
    get_progress_dashboard,
    get_qc_today_summary,
    get_slow_moving_materials,
    get_spraying_today_summary,
    get_team_production_summary,
    get_today_output_yoy,
    get_today_patrol_logs,
    get_today_scrap_logs,
    get_tonnage_dashboard,
    get_whse_inventory_overview,
    resolve_machine_id_by_key,
    resolve_material_id_by_number,
    submit_packaging,
    submit_production_log,
    submit_shipping,
    toggle_urgent,
    update_machine,
    verify_user,
    get_my_assigned_parts,
    get_my_parts,
)
from app.core.templates import templates

# Route handlers:

@router.get("/admin/switch-view")
def admin_switch_view(request: Request, dept: str = ""):
    """管理员切换展示视图（不影响实际权限）"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("real_role_level", 0) < 9:
        raise HTTPException(status_code=403, detail="仅超级管理员可使用此功能")
    referer = request.headers.get("referer", "/")
    res = RedirectResponse(referer, status_code=303)
    if dept in ("sales", "prod", "tech", "qc", "pkg", "admin", "whse", "spraying",
                "prod-op", "prod-lead", "dev-mold", "dev-design", "sales-mgr", ""):
        if dept:
            res.set_cookie("view_as", dept, max_age=60*60*8, httponly=True, samesite="lax")
        else:
            res.delete_cookie("view_as")
    return res


def can_see_all_molds(user):
    """Level 9（老板）、Level 5（业务经理/组长）、Level 2（开发）可见全部模具"""
    return user and user.get("role_level", 0) in (9, 5, 2)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("common/login.html", {"request": request})

@router.post("/login")
def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        user = verify_user(username, password)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;padding:40px;'>"
            "<h2>系统错误</h2><p>请检查数据库连接</p><p>" + str(e) + "</p>"
            "<a href='/login'>返回登录</a></body></html>",
            status_code=500)
    if not user:
        return templates.TemplateResponse(
            "common/login.html",
            {"request": request, "error": "用户名或密码错误"})
    res = RedirectResponse("/", status_code=303)
    res.set_cookie("user_id", str(user["id"]),max_age=60*60*8, httponly=True, samesite="lax")
    res.set_cookie("username", quote(user.get("username", "")), max_age=60*60*8, httponly=True, samesite="lax")
    res.set_cookie("real_name", quote(user.get("real_name", "")), max_age=60*60*8, httponly=True, samesite="lax")
    res.set_cookie("role_level", str(user.get("role_level", 1)), max_age=60*60*8, httponly=True, samesite="lax")
    dept = user.get("department") or user.get("dept") or "prod"
    res.set_cookie("department", dept, max_age=60*60*8, httponly=True, samesite="lax")
    res.set_cookie("dept", dept, max_age=60*60*8, httponly=True, samesite="lax")
    pos = user.get("position") or ""
    if pos:
        res.set_cookie("position", quote(pos),max_age=60*60*8, httponly=True, samesite="lax")
    else:
        if user.get("role_level", 1) >= 9:
            res.set_cookie("position", quote("老板"),max_age=60*60*8, httponly=True, samesite="lax")
            res.set_cookie("view_as", "admin", max_age=60*60*8, httponly=True, samesite="lax")
        elif user.get("role_level", 1) == 5:
            res.set_cookie("position", quote("经理"),max_age=60*60*8, httponly=True, samesite="lax")
        else:
            res.set_cookie("position", quote("操作工"),max_age=60*60*8, httponly=True, samesite="lax")
    return res

@router.get("/logout")
def logout():
    res = RedirectResponse("/login")
    for key in ["user_id", "username", "role_level", "dept", "department", "position", "real_name", "view_as"]:
        res.delete_cookie(key)
    return res


# ============================================================================
# ── 2. 主看板 (Department 分流核心) ──────────────────────────
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")

    print(f"DEBUG: User={user.get('username')}, Dept={user.get('department')}, Real={user.get('real_department')}, Level={user.get('role_level')}, Position={user.get('position')}, view_as={user.get('view_as')}")
    print(f"DEBUG Cookies: dept={request.cookies.get('dept')}, department={request.cookies.get('department')}, view_as={request.cookies.get('view_as')}")

    context = {"request": request, "user": user}
    display_dept = user.get('department')
    real_dept    = user.get('real_department', display_dept)
    bypass = can_bypass_dept(user)

    # ── 老板 (Level 9 / is_superadmin)：始终加载完整经营看板 ──
    if bypass:
        context["period_summary"]  = get_period_summary()
        context["urgent_parts"]  = get_all_urgent_parts()
        context["parts"]         = get_all_parts(user['role_level'])
        context["today_output"]  = get_today_output_yoy()
        context["utilization"]   = get_factory_utilization()
        context["tonnage_groups"]= get_tonnage_dashboard()
        context["overdue_summary"]= get_overdue_summary()
        context["pending_quote_count"] = count_pending_quotes()
        context["boss_kpi"]      = get_boss_kpi()

    if bypass or display_dept == 'whse':
        context["material_alerts"] = get_material_alerts()
        if bypass or user['role_level'] >= 5:
            ensure_inbound_orders_table()
            context["inbound_summary"]    = get_inbound_summary()
            context["pending_inbounds"]   = get_pending_inbound_orders()
            context["inventory_overview"]  = get_whse_inventory_overview()
            context["slow_materials"]     = get_slow_moving_materials()

    if bypass or display_dept == 'sales':
        context["dashboard_stats"] = get_daily_dashboard_stats()
        context["urgent_parts"]   = get_all_urgent_parts()

    if bypass or display_dept == 'qc':
        context["qc_summary"] = get_qc_today_summary()
        if bypass or user['role_level'] >= 5:
            context["oqc_reports"]        = get_oqc_reports(limit=10)
            context["oqc_pending_count"]  = count_oqc_reports('pending_approve')
            context["patrol_logs"]        = get_today_patrol_logs()
            context["blocked_parts"]       = get_blocked_parts()
        else:
            context["patrol_logs"] = get_today_patrol_logs()

    if bypass or display_dept == 'pkg':
        context["pkg_summary"]   = get_pkg_today_summary()
        context["pkg_inventory"] = get_pkg_ready_inventory()
        if bypass or user['role_level'] >= 5:
            context["pkg_error_logs"] = get_pkg_error_logs(limit=20)
            context["pkg_blocked"]    = get_pkg_blocked_parts()

    if bypass or display_dept == 'spraying':
        context["spray_summary"] = get_spraying_today_summary()

    if bypass or display_dept == 'prod':
        parts = get_my_parts(user['id'])
        context["my_parts"] = parts
        context["worker_today_good"] = sum(p.get('today_good') or 0 for p in parts)
        if bypass or user['role_level'] >= 5:
            context["team_summary"]     = get_team_production_summary()
            context["pending_logs"]    = get_pending_logs_for_dashboard()
            context["scrap_alerts"]    = get_today_scrap_logs()
            context["my_assigned_parts"] = get_my_assigned_parts(user['id'])

    if bypass or (display_dept == 'admin' and not bypass):
        if user['role_level'] == 5 and user.get('position') == '组长':
            context["scrap_alerts"]      = get_today_scrap_logs()
            context["pending_logs"]      = get_pending_logs_for_dashboard()
            context["my_assigned_parts"] = get_my_assigned_parts(user['id'])
            context["dashboard_stats"]   = get_daily_dashboard_stats()

    return templates.TemplateResponse("common/index.html", context, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})


# ── 调试路由 ──────────────────────────────────────────────
@router.get("/debug_lv1")
def debug_lv1(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    if user['role_level'] != 1:
        return HTMLResponse(f"Role level = {user['role_level']}, not Lv.1", status_code=200)
    parts = get_my_parts(user['id'])
    total_good = sum(p.get('today_good') or 0 for p in parts)
    lines_out = [f"role_level: {user['role_level']}", f"my_parts count: {len(parts)}", f"worker_today_good: {total_good}"]
    for p in parts:
        lines_out.append(f"  - id={p['id']}, pn={p['part_number']}, today_good={p.get('today_good')}")
    return HTMLResponse("\n".join(lines_out), media_type="text/plain")


# ── 3. 业务经理提报价 (Level 4) ───────────────────────────────────
# ── 4. 老板审批 (Level 9) ─────────────────────────────────────────# ── 每日进度看板 ────────────────────────────────────────────────
@router.get("/progress", response_class=HTMLResponse)
def progress_page(request: Request, date: str = ''):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    if not can_bypass_dept(user) and user.get('department') not in ('prod', 'sales', 'admin'):
        raise HTTPException(status_code=403, detail="仅生产/业务/管理员可访问")
    target_date = date if date else None
    rows = get_progress_dashboard(target_date)
    machines = get_all_machines()
    fault_machines = get_machines_with_faults()
    return templates.TemplateResponse("prod/progress.html", {
        "request": request, "user": user, "rows": rows, "machines": machines,
        "fault_machines": fault_machines, "target_date": target_date or datetime.date.today().isoformat(),
    })


# ── 机台操作终端 ────────────────────────────────────────────────
@router.get("/operator", response_class=HTMLResponse)
def operator_page(request: Request, machine_id: int = None, machine_key: str = None):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    if not machine_id and machine_key:
        mid = resolve_machine_id_by_key(machine_key)
        if mid: return RedirectResponse(f"/operator?machine_id={mid}", 302)
    if not machine_id:
        return templates.TemplateResponse("prod/operator_scan.html", {"request": request, "user": user})
    machine = get_machine_by_id(machine_id)
    if not machine: return HTMLResponse("机台不存在", status_code=404)
    queue = get_machine_plans(machine_id)
    update_machine(machine_id, current_operator_id=user['id'])
    return templates.TemplateResponse("prod/operator_ui.html", {
        "request": request, "user": user, "machine": machine, "queue": queue,
        "active_plan": queue[0] if queue else None,
    })


@router.post("/operator/report")
def operator_report(request: Request, machine_id: int = Form(...), part_id: int = Form(...),
                    good_count: float = Form(...), scrap_count: float = Form(0),
                    scrap_reason: str = Form(""), plan_id: int = Form(None),
                    remark: str = Form(""), material_id: str = Form(None), actual_date: str = Form(None)):
    user = get_current_user(request)
    if not user or user['role_level'] < 1: raise HTTPException(status_code=403, detail="无报工权限")
    if scrap_count > 0 and not scrap_reason.strip():
        raise HTTPException(status_code=400, detail="有报废必须填写原因")
    ok, err = check_machine_active_plan(machine_id, part_id)
    if not ok: raise HTTPException(status_code=400, detail=err)
    resolved_mat_id = None
    if material_id:
        try: resolved_mat_id = int(material_id)
        except (ValueError, TypeError):
            rid, _ = resolve_material_id_by_number(str(material_id))
            if not rid: raise HTTPException(status_code=400, detail=f"未找到物料卷号：{material_id}")
            resolved_mat_id = rid
        ok2, err2 = check_material_qualified(resolved_mat_id)
        if not ok2: raise HTTPException(status_code=400, detail=err2)
    try:
        submit_production_log(part_id=part_id, worker_id=user['id'], good_count=good_count,
                                       scrap_count=scrap_count, scrap_reason=scrap_reason.strip(),
                                       remark=remark.strip(), machine_id=machine_id, plan_id=plan_id,
                                       material_id=resolved_mat_id,
                                       actual_date=actual_date if actual_date else None)
    except Exception as ex:
        raise HTTPException(status_code=409, detail=str(ex))
    return RedirectResponse(f"/operator?machine_id={machine_id}", 303)


@router.get("/debug/user")
def debug_user(request: Request):
    user = get_current_user(request)
    if not user: return {"error": "未登录"}
    return {"user": user, "cookies": dict(request.cookies)}


# ── 材料参数中心 ───────────────────────────────────────────────
@router.get("/material-prices", response_class=HTMLResponse)
def material_prices_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    prices = get_all_material_base_prices()
    return templates.TemplateResponse("material_prices.html", {
        "request": request, "user": user, "prices": prices,
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)