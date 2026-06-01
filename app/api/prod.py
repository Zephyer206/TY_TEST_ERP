"""
app/api/prod.py
生产部路由 — 生产计划 / 进度看板 / 机台操作终端 / 报工
前缀: /prod
"""
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.db_service import (
    get_all_plans,
    get_plan_by_id,
    create_plan,
    assign_plan_to_machine,
    update_plan_order,
    cancel_plan,
    close_plan,
    get_plan_close_report,
    get_progress_dashboard,
    get_all_machines,
    get_machines_with_faults,
    get_manager_dashboard_data,
    intervene_machine,
    force_complete_machine,
    get_machine_repair_log,
    get_my_assigned_parts,
    get_scrap_logs,
    get_scrap_summary,
    # ── 车间执行 (Stage 4 & 5) ──
    get_all_equipments,
    get_equipment_by_id,
    get_equipment_by_code,
    create_equipment,
    update_equipment,
    equipment_change_status,
    get_all_work_orders,
    get_work_order_by_id,
    get_work_order_by_no,
    create_work_order,
    schedule_work_order,
    start_work_order,
    approve_first_piece,
    add_production_log,
    get_sf_production_logs,
    get_work_order_summary,
    first_piece_check,
)
from app.services.prod_service import (
    report_production_with_lock,
    check_all_production_gates,
)

router = APIRouter(prefix="/prod", tags=["prod"])


# ── 生产计划列表 ────────────────────────────────────────────────
@router.get("/plans", response_class=HTMLResponse)
def plans_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    plans = get_all_plans(user_role_level=user["role_level"])
    return templates.TemplateResponse("prod/plans.html", {
        "request": request, "user": user, "plans": plans,
    })


@router.post("/plans/add")
def plans_add(request: Request,
              part_id: int = Form(...),
              total_qty: int = Form(...),
              due_date: str = Form(...),
              urgency: str = Form("normal")):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    create_plan(part_id=part_id, total_qty=total_qty, due_date=due_date,
                urgency=urgency, created_by=user["id"])
    return RedirectResponse("/prod/plans", 303)


@router.post("/plans/{plan_id}/reorder")
def plans_reorder(request: Request, plan_id: int,
                  new_order: int = Form(...), direction: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    update_plan_order(plan_id, new_order, updated_by=user["id"],
                      force=(direction == "force"))
    return RedirectResponse("/prod/plans", 303)


@router.post("/plans/{plan_id}/cancel")
def plans_cancel(request: Request, plan_id: int):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    cancel_plan(plan_id)
    return RedirectResponse("/prod/plans", 303)


@router.get("/plans/{plan_id}/close-report", response_class=HTMLResponse)
def plans_close_report(request: Request, plan_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    report = get_plan_close_report(plan_id)
    plan = get_plan_by_id(plan_id)
    return templates.TemplateResponse("prod/plan_close_report.html", {
        "request": request, "user": user,
        "report": report, "plan": plan,
    })


# ── 进度看板 ─────────────────────────────────────────────────────
@router.get("/progress", response_class=HTMLResponse)
def progress_page(request: Request, date: str = ""):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if not (user.get("role_level", 0) >= 5 or user.get("department") in ("prod", "sales", "admin")):
        raise HTTPException(status_code=403, detail="权限不足")
    import datetime
    target_date = date if date else None
    rows = get_progress_dashboard(target_date)
    machines = get_all_machines()
    faults = get_machines_with_faults()
    return templates.TemplateResponse("prod/progress.html", {
        "request": request, "user": user,
        "rows": rows, "machines": machines,
        "fault_machines": faults,
        "target_date": target_date or datetime.date.today().isoformat(),
    })


# ── 生产管理仪表盘 ───────────────────────────────────────────────
@router.get("/manager", response_class=HTMLResponse)
def prod_manager_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    import datetime as _dt
    import decimal as _dec
    data = get_manager_dashboard_data()
    _now = _dt.datetime.now()

    def _serialize_rows(rows, compute_elapsed=False):
        result = []
        for row in rows:
            d = dict(row)
            if compute_elapsed:
                ts = d.get('fault_reported_at') or d.get('tech_arrival_time')
                if ts and isinstance(ts, (_dt.datetime, _dt.date)):
                    d['elapsed_min'] = int((_now - ts).total_seconds() / 60)
                else:
                    d['elapsed_min'] = 0
            for k, v in d.items():
                if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
                    d[k] = v.isoformat()
                elif isinstance(v, _dec.Decimal):
                    d[k] = float(v)
            result.append(d)
        return result

    data['machines']        = _serialize_rows(data.get('machines', []), compute_elapsed=True)
    data['unassigned_plans'] = _serialize_rows(data.get('unassigned_plans', []))
    data['active_plans']    = _serialize_rows(data.get('active_plans', []))

    return templates.TemplateResponse("prod/prod_manager_dashboard.html", {
        "request": request, "user": user,
        "now": _now,
        **data,
    })


@router.get("/manager/json")
def prod_manager_json(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    if user["role_level"] < 3:
        return JSONResponse({"error": "权限不足"}, status_code=403)
    import datetime, decimal, json
    data = get_manager_dashboard_data()

    def _default(obj):
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return JSONResponse(json.loads(json.dumps(data, default=_default)))


@router.post("/manager/intervene")
def prod_manager_intervene(request: Request,
                           machine_id: int = Form(...),
                           action: str = Form(...),
                           fault_reason: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    intervene_machine(machine_id, action, fault_reason=fault_reason, remark="")
    return RedirectResponse(request.headers.get("referer", "/prod/manager"), 303)


@router.post("/manager/force-complete")
def prod_manager_force_complete(request: Request,
                                machine_id: int = Form(...),
                                plan_id: int = Form(None),
                                remark: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="权限不足")
    force_complete_machine(machine_id, plan_id, remark=remark)
    return RedirectResponse(request.headers.get("referer", "/prod/manager"), 303)


@router.get("/manager/repair-log/{machine_id}")
def prod_manager_repair_log(request: Request, machine_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    log = get_machine_repair_log(machine_id)
    return JSONResponse(log)


# ── 报废日志 ─────────────────────────────────────────────────────
@router.get("/scrap-logs", response_class=HTMLResponse)
def scrap_logs_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    logs = get_scrap_logs(limit=200)
    summary = get_scrap_summary()
    return templates.TemplateResponse("prod/scrap_logs.html", {
        "request": request, "user": user,
        "logs": logs, "summary": summary,
    })


# ── 机台操作终端（由 routes.py 注册）────────────────────────────

# ============================================================================
# 阶段四 & 五：车间执行 (equipments / work_orders / sf_production_logs)
# ============================================================================

# ── 机台台账管理 ──────────────────────────────────────────────────────────

@router.get("/machines", response_class=HTMLResponse)
def equip_list_page(request: Request):
    """机台台账列表页（含状态、当前工单、熔断状态）。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    equip_list = get_all_equipments()
    return templates.TemplateResponse("prod/equip_list.html", {
        "request": request, "user": user,
        "equipments": equip_list,
    })


@router.get("/machines/json")
def equip_list_json(request: Request):
    """机台列表 JSON 接口（AJAX 轮询）。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    return JSONResponse(get_all_equipments())


@router.post("/machines/add")
def equip_add(request: Request,
              equipment_code: str = Form(...),
              equipment_name: str = Form(""),
              tonnage: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    try:
        create_equipment(equipment_code, equipment_name, tonnage)
        return RedirectResponse("/prod/machines", 303)
    except ValueError as e:
        return HTMLResponse(
            f"<html><body><script>alert('{str(e)}'); history.back();</script></body></html>",
            status_code=400)


# ── 工单管理 ─────────────────────────────────────────────────────────────

@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    """工单列表页（含状态、完成率、首件状态）。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    orders = get_all_work_orders()
    return templates.TemplateResponse("prod/orders.html", {
        "request": request, "user": user,
        "orders": orders,
    })


@router.get("/orders/json")
def orders_json(request: Request,
                status: str = "",
                part_id: str = ""):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    filters = {}
    if status:
        filters["status"] = status
    if part_id:
        filters["part_id"] = int(part_id)
    return JSONResponse(get_all_work_orders(filters or None))


@router.post("/orders/add")
def order_add(request: Request,
              part_id: int = Form(...),
              target_qty: int = Form(...),
              priority: str = Form("NORMAL"),
              is_first_piece: bool = Form(False),
              equipment_id: int = Form(None)):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    try:
        create_work_order(
            part_id=part_id,
            target_qty=target_qty,
            priority=priority,
            is_first_piece_required=is_first_piece,
            created_by=user["id"],
            equipment_id=equipment_id,
        )
        return RedirectResponse("/prod/orders", 303)
    except ValueError as e:
        return HTMLResponse(
            f"<html><body><script>alert('{str(e)}'); history.back();</script></body></html>",
            status_code=400)


@router.post("/orders/{wo_id}/schedule")
def order_schedule(request: Request,
                   wo_id: int,
                   equipment_id: int = Form(...)):
    """排产上线：工单 PENDING → SCHEDULED，机台 IDLE → RUNNING。"""
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    result = schedule_work_order(wo_id, equipment_id, actor_id=user["id"])
    if result.get("code") != 0:
        return HTMLResponse(
            f"<html><body><script>alert('{result['message']}'); history.back();</script></body></html>",
            status_code=400)
    return RedirectResponse("/prod/orders", 303)


# ── 车间操作终端 ─────────────────────────────────────────────────────────

@router.get("/shopfloor", response_class=HTMLResponse)
def shopfloor_page(request: Request):
    """
    车间操作终端主页面。
    显示当前登录操作工关联的机台和工单。
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    equip_list = get_all_equipments()
    return templates.TemplateResponse("prod/operator_sf.html", {
        "request": request, "user": user,
        "equipments": equip_list,
    })


@router.get("/shopfloor/scan/{equipment_code}", response_class=HTMLResponse)
def shopfloor_scan_page(request: Request, equipment_code: str):
    """
    操作工扫码进入特定机台的终端。
    扫码码值为机台 equipment_code。
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")

    eq = get_equipment_by_code(equipment_code)
    if not eq:
        return HTMLResponse("机台不存在", status_code=404)

    # 查询该机台当前的工单
    wo = None
    if eq["id"]:
        from app.services.db_service import get_all_work_orders
        all_wo = get_all_work_orders({"equipment_id": eq["id"]})
        wo = all_wo[0] if all_wo else None

    # 读取报工流水
    logs = []
    if wo:
        logs = get_sf_production_logs(wo_id=wo["id"])

    return templates.TemplateResponse("prod/operator_sf_detail.html", {
        "request": request, "user": user,
        "equipment": eq,
        "work_order": wo,
        "recent_logs": logs[:20],
    })


@router.post("/shopfloor/report")
def shopfloor_report(request: Request,
                     equipment_id: int = Form(...),
                     work_order_id: int = Form(...),
                     strokes: int = Form(...),
                     material_qr: str = Form(""),
                     actual_date: str = Form("")):
    """
    冲压报工：strokes → yield_qty，自动首件校验 + 熔断校验。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)

    result = report_production_with_lock(
        work_order_id=work_order_id,
        equipment_id=equipment_id,
        strokes=strokes,
        operator_id=user["id"],
        material_qr_uid=material_qr or None,
    )
    if result.get("code") != 0:
        return JSONResponse({"success": False, "message": result["message"]},
                            status_code=400)
    return JSONResponse({
        "success": True,
        "message": result["message"],
        "data": result["data"],
    })


# ── 首件 QA 放行 ─────────────────────────────────────────────────────────

@router.post("/shopfloor/first-piece/approve")
def first_piece_approve(request: Request,
                         work_order_id: int = Form(...)):
    """操作工/质检确认首件放行。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)
    result = approve_first_piece(work_order_id, operator_id=user["id"])
    status = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status)


@router.get("/shopfloor/first-piece/check/{wo_id}")
def first_piece_check_api(request: Request, wo_id: int):
    """前端轮询首件状态。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    allowed, msg = first_piece_check(wo_id)
    return JSONResponse({"allowed": allowed, "message": msg})


# ── 工单详情 ─────────────────────────────────────────────────────────────

@router.get("/orders/{wo_id}", response_class=HTMLResponse)
def order_detail_page(request: Request, wo_id: int):
    """工单详情（含报工流水、汇总统计）。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    wo = get_work_order_by_id(wo_id)
    if not wo:
        return HTMLResponse("工单不存在", status_code=404)
    logs = get_sf_production_logs(wo_id=wo_id)
    summary = get_work_order_summary(wo_id)
    return templates.TemplateResponse("prod/order_detail.html", {
        "request": request, "user": user,
        "wo": wo, "logs": logs, "summary": summary,
    })
