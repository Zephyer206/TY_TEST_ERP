"""
app/api/tech.py
模修部路由 — 两扫制维修流程 / 待修池 / 扫码 / 管理看板
前缀: /tech
"""
from fastapi import APIRouter, Form, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import Body
from pydantic import BaseModel, Field
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.db_service import (
    get_tech_task_pool,
    get_pending_repair_pool,
    tech_start_repair,
    tech_complete_repair,
    tech_get_current_repairing,
    tech_twoscan_process,
    get_realtime_radar_data,
    get_tech_manager_permission,
    get_tech_staff_monthly_efficiency,
    get_offline_molds_queue,
    get_mold_fault_analysis,
    get_tech_performance_stats,
    tech_confirm_mold_offline,
    get_machine_repair_log,
    get_tech_time_analytics,
    get_all_tooling_molds_for_review,
    count_mold_status_all,
    create_sample_task,
    signoff_sample_task,
    activate_mass_production,
    import_legacy_molds_from_csv,
    get_sample_task_by_id,
    # ── 车间执行 Stage 4 & 5 ──
    get_all_equipments,
    get_equipment_by_id,
    get_equipment_by_code,
    equipment_change_status,
    create_maintenance_log,
    complete_maintenance_log,
    get_maintenance_logs,
    get_open_maintenance,
)
from app.services.prod_service import (
    maintenance_trigger_with_decoupling,
    maintenance_resolve_with_coupling,
)

router = APIRouter(prefix="/tech", tags=["tech"])


# ── 两扫制：扫码处理 ───────────────────────────────────────────
@router.post("/scan/process")
def tech_scan_process(request: Request, mold_key: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)
    try:
        result = tech_twoscan_process(mold_key, user["id"])
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


# ── 模修师傅员工端 ─────────────────────────────────────────────
@router.get("/staff", response_class=HTMLResponse)
def tech_staff_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("role_level", 1) < 2 and user.get("department") not in ("tech", "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    pending = get_pending_repair_pool(tech_user_id=user["id"], search_key="")
    repairing = tech_get_current_repairing(user["id"])
    return templates.TemplateResponse("tech/tech_staff.html", {
        "request": request,
        "user": user,
        "pending_machines": pending,
        "repairing_machine": repairing,
    })


@router.post("/staff/scan")
def tech_staff_scan(request: Request, machine_key: str = Form("")):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    from app.services.db_service import resolve_mold_by_key, get_machine_by_qr
    # 先尝试用 mold_key 解析
    mold_result = resolve_mold_by_key(machine_key)
    if mold_result:
        machine_id = mold_result.get("machine_id")
        if machine_id:
            from app.services.db_service import tech_intervene
            try:
                tech_intervene(machine_id, user["id"])
            except Exception:
                pass
            return RedirectResponse(f"/tech/staff", status_code=303)
    # 再尝试机台二维码
    machine = get_machine_by_qr(machine_key)
    if machine:
        from app.services.db_service import tech_intervene
        try:
            tech_intervene(machine["id"], user["id"])
        except Exception:
            pass
    return RedirectResponse("/tech/staff", status_code=303)


# ── 待修池 ─────────────────────────────────────────────────────
@router.get("/pool", response_class=HTMLResponse)
def tech_pool_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("role_level", 1) < 2 and user.get("department") not in ("tech", "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    return templates.TemplateResponse("tech/tech_pool.html", {"request": request, "user": user})


@router.get("/pool/json")
def tech_pool_json(request: Request, search: str = ""):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)
    try:
        current = tech_get_current_repairing(user["id"])
        pending = get_pending_repair_pool(tech_user_id=user["id"], search_key=search)
        return JSONResponse({
            "success": True,
            "current": current,
            "pending": pending,
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@router.post("/pool/start")
def tech_pool_start(request: Request, record_id: int = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)
    try:
        result = tech_start_repair(record_id, user["id"])
        return JSONResponse({"success": True, "message": result.get("message", "已开始维修")})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/pool/complete")
def tech_pool_complete(request: Request, record_id: int = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)
    try:
        result = tech_complete_repair(record_id, user["id"])
        return JSONResponse({"success": True, "message": result.get("message", "维修完成")})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/pool/confirm-offline")
def tech_pool_confirm_offline(request: Request, machine_id: int = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)
    try:
        result = confirm_mold_offline_and_create_pending_record(machine_id, user["id"])
        return JSONResponse({"success": True, "message": "已加入待修池"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


# ── 技术部管理看板 ─────────────────────────────────────────────
@router.get("/manager", response_class=HTMLResponse)
def tech_manager_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if not get_tech_manager_permission(user["id"]):
        raise HTTPException(status_code=403, detail="权限不足")
    radar = get_realtime_radar_data()
    task_pool = get_tech_task_pool()
    performance = get_tech_performance_stats()
    tech_eff = get_tech_staff_monthly_efficiency()
    return templates.TemplateResponse("tech/tech_manager.html", {
        "request": request,
        "user": user,
        "summary": radar.get("summary", {}) if radar else {},
        "radar_data": radar.get("machines", []) if radar else [],
        "task_pool": task_pool,
        "performance": performance,
        "tech_staff_efficiency": tech_eff,
    })


@router.get("/manager/machine/{machine_id}/detail")
def tech_manager_machine_detail(request: Request, machine_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    if not get_tech_manager_permission(user["id"]):
        return JSONResponse({"error": "权限不足"}, status_code=403)
    try:
        from app.services.db_service import get_machine_by_id, get_machines_with_faults
        machine = get_machine_by_id(machine_id)
        repair_log = get_machine_repair_log(machine_id)
        tech_eff = get_tech_staff_monthly_efficiency()
        return JSONResponse({
            "machine": machine,
            "repair_log": repair_log,
            "tech_efficiency": tech_eff,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── 模修时效分析 ────────────────────────────────────────────────
@router.get("/analytics", response_class=HTMLResponse)
def tech_analytics_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("role_level", 1) < 2 and user.get("department") not in ("tech", "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    analysis = get_mold_fault_analysis(period="month")
    return templates.TemplateResponse("tech/tech_analytics.html", {
        "request": request,
        "user": user,
        "fault_analysis": analysis,
    })


# ── 内部辅助函数 ────────────────────────────────────────────────
def confirm_mold_offline_and_create_pending_record(machine_id, tech_user_id):
    from app.services.db_service import create_offline_mold_record
    return create_offline_mold_record(machine_id, tech_user_id)


# ═══════════════════════════════════════════════════════════════════
# 以下路由已从 app/api/routes.py 迁移至此处，按部门模块化管理
# 前缀: /tooling  /molds  /cavity_review
# ═══════════════════════════════════════════════════════════════════
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.db_service import (
    get_all_tooling_molds,
    count_tooling_molds,
    get_all_tooling_customers,
    get_tooling_mold_by_id,
    get_tooling_parts_by_mold,
    get_all_molds,
    get_mold_by_id,
    get_all_parts,
    get_parts_by_mold,
    add_mold,
    update_mold,
    delete_mold,
    link_mold_part,
    unlink_mold_part,
    update_cavity_status,
    update_mold_physical_params,
)

# ── 独立子路由（无前缀） ──────────────────────────────────────────
# /tooling/*  → 模具台账
# /molds/*    → 模具管理
# /cavity_review/* → 多穴审核
_mold_router = APIRouter()


@_mold_router.get("/tooling", response_class=HTMLResponse)
def tooling_page(request: Request, customer_id: int = None, keyword: str = None,
                 mold_status: str = None, page: int = 1):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    PAGE_SIZE = 50
    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE
    molds = get_all_tooling_molds(
        filters={"customer_id": customer_id, "keyword": keyword, "mold_status": mold_status},
        user_role_level=user["role_level"], limit=PAGE_SIZE, offset=offset)
    total = count_tooling_molds(
        filters={"customer_id": customer_id, "keyword": keyword, "mold_status": mold_status},
        user_role_level=user["role_level"])
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    status_counts = count_mold_status_all()
    customers = get_all_tooling_customers()
    sel_customer = next((c for c in customers if c["id"] == customer_id), None) if customer_id else None
    return templates.TemplateResponse("tech/tooling.html", {
        "request": request, "molds": molds, "customers": customers, "sel_customer": sel_customer,
        "keyword": keyword or "", "mold_status": mold_status or "", "status_counts": status_counts,
        "user": user, "page": page, "total_pages": total_pages, "total": total,
    })


@_mold_router.get("/tooling/{mold_id}", response_class=HTMLResponse)
def tooling_detail_page(request: Request, mold_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    mold = get_tooling_mold_by_id(mold_id, user_role_level=user["role_level"])
    if not mold:
        return HTMLResponse("Mold not found", status_code=404)
    parts = get_tooling_parts_by_mold(mold_id)
    return templates.TemplateResponse("tech/tooling_detail.html", {
        "request": request, "mold": mold, "parts": parts, "user": user,
    })


@_mold_router.get("/molds", response_class=HTMLResponse)
def mold_list_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    molds = get_all_molds()
    return templates.TemplateResponse("tech/molds.html", {
        "request": request, "molds": molds, "user": user,
    })


class MoldAddBody(BaseModel):
    mold_number: str
    mold_name: str = ""
    cavity_count: int = 1
    press_tonnage: str = ""
    remark: str = ""


class MoldUpdateBody(BaseModel):
    mold_name: str = ""
    cavity_count: int = 1
    press_tonnage: str = ""
    status: str = ""
    remark: str = ""
    thickness_mm: float = None
    width_mm: float = None
    pitch_mm: float = None


@_mold_router.post("/molds/add")
def mold_add(request: Request, body: MoldAddBody = None):
    user = get_current_user(request)
    if not user or user["role_level"] < 2:
        raise HTTPException(status_code=403, detail="权限不足")
    add_mold(body.mold_number, body.mold_name, body.cavity_count, body.press_tonnage, body.remark)
    return JSONResponse(jsonable_encoder({"code": 200, "message": "新增成功"}))


@_mold_router.post("/molds/{mold_id}/update")
def mold_update(request: Request, mold_id: int, body: MoldUpdateBody = None):
    user = get_current_user(request)
    if not user or user["role_level"] < 2:
        raise HTTPException(status_code=403, detail="权限不足")
    update_mold(mold_id, mold_name=body.mold_name, cavity_count=body.cavity_count,
                 press_tonnage=body.press_tonnage, status=body.status, remark=body.remark)
    if body.thickness_mm is not None or body.width_mm is not None or body.pitch_mm is not None:
        update_mold_physical_params(mold_id,
                                    thickness_mm=body.thickness_mm,
                                    width_mm=body.width_mm,
                                    pitch_mm=body.pitch_mm)
    return JSONResponse(jsonable_encoder({"code": 200, "message": "保存成功"}))


@_mold_router.post("/molds/{mold_id}/delete")
def mold_delete(request: Request, mold_id: int):
    user = get_current_user(request)
    if not user or user["role_level"] < 2:
        raise HTTPException(status_code=403, detail="权限不足")
    delete_mold(mold_id)
    return JSONResponse(jsonable_encoder({"code": 200, "message": "删除成功"}))


@_mold_router.get("/molds/{mold_id}/link", response_class=HTMLResponse)
def mold_link_page(request: Request, mold_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    mold = get_mold_by_id(mold_id)
    if not mold:
        return HTMLResponse("模具不存在", status_code=404)
    linked_parts = get_parts_by_mold(mold_id)
    all_parts = get_all_parts(user["role_level"])
    return templates.TemplateResponse("tech/mold_link.html", {
        "request": request, "mold": mold, "linked_parts": linked_parts,
        "all_parts": all_parts, "user": user,
    })


@_mold_router.post("/molds/{mold_id}/link")
def mold_link_part(request: Request, mold_id: int, part_id: int = Form(...),
                   product_number: str = Form(""), seq_order: int = Form(0)):
    user = get_current_user(request)
    if not user or user["role_level"] < 2:
        raise HTTPException(status_code=403, detail="权限不足")
    link_mold_part(mold_id, part_id, product_number, seq_order)
    return RedirectResponse(f"/molds/{mold_id}/link", 303)


@_mold_router.post("/molds/{mold_id}/unlink")
def mold_unlink_part(request: Request, mold_id: int, part_id: int = Form(...)):
    user = get_current_user(request)
    if not user or user["role_level"] < 2:
        raise HTTPException(status_code=403, detail="权限不足")
    unlink_mold_part(mold_id, part_id)
    return RedirectResponse(f"/molds/{mold_id}/link", 303)


@_mold_router.get("/cavity_review", response_class=HTMLResponse)
def cavity_review_page(request: Request, customer_id: int = None, keyword: str = None, status: str = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] not in (9, 4):
        return HTMLResponse("权限不足", status_code=403)
    molds = get_all_tooling_molds_for_review(
        filters={"customer_id": customer_id, "keyword": keyword, "status": status})
    customers = get_all_tooling_customers()
    sel_customer = next((c for c in customers if c["id"] == customer_id), None)
    return templates.TemplateResponse("tech/cavity_review.html", {
        "request": request, "molds": molds, "customers": customers,
        "sel_customer": sel_customer, "keyword": keyword or "", "status": status or "", "user": user,
    })


@_mold_router.post("/cavity_review/confirm")
def cavity_review_confirm(request: Request, mold_id: int = Form(...), new_status: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] not in (9, 4):
        raise HTTPException(status_code=403, detail="权限不足")
    update_cavity_status(mold_id, new_status)
    return RedirectResponse("/tooling", 303)


# ============================================================================
# 阶段二：打样与 PPAP 定型流  (v4_sample_molds_bom)
# ============================================================================
sample_router = APIRouter(prefix="/api/sample-tasks", tags=["sample_tasks"])
molds_api_router = APIRouter(prefix="/api/molds", tags=["molds"])  # molds JSON API


# ── 打样任务 CRUD ────────────────────────────────────────────────

class CreateSampleTaskBody(BaseModel):
    part_id: int
    quote_id: int | None = None
    sample_type: str = "FIRST_SAMPLE"
    sample_fee: float = 0
    remarks: str = ""


@sample_router.post("")
async def api_create_sample_task(body: CreateSampleTaskBody, request: Request):
    """
    创建打样 / PPAP 任务。

    权限：role_level >= 4（业务及以上）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需 role_level >= 4）",
                             "data": None}, status_code=403)

    result = create_sample_task(
        part_id=body.part_id,
        user_id=user["id"],
        quote_id=body.quote_id,
        sample_type=body.sample_type,
        sample_fee=body.sample_fee,
        remarks=body.remarks,
    )
    status = 200 if result["code"] == 0 else 400
    return JSONResponse(result, status_code=status)


@sample_router.get("/{task_id}")
async def api_get_sample_task(task_id: int, request: Request):
    """
    查询打样任务详情（含三方签到状态）。

    权限：role_level >= 1
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)

    from app.services.db_service import get_sample_task_by_id
    task = get_sample_task_by_id(task_id)
    if not task:
        return JSONResponse({"code": 1, "message": f"任务 #{task_id} 不存在",
                             "data": None}, status_code=404)
    return JSONResponse({"code": 0, "message": "ok", "data": task})


# ── 三方签到 ──────────────────────────────────────────────────────

class SignoffBody(BaseModel):
    dept_role: str = Field(..., description="签到部门角色，可选值：'tech' | 'qa' | 'sales'")
    # 枚举值由 db_service.signoff_sample_task 校验，此处用 str 以兼容前端灵活性


@sample_router.post("/{task_id}/signoff")
async def api_signoff(task_id: int, body: SignoffBody, request: Request):
    """
    三方会签：技术 / 质量 / 业务部门签到。

    权限：role_level >= 2
    三方全部签到后任务状态自动升级为 COMPLETED。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足（需 role_level >= 2）",
                             "data": None}, status_code=403)

    result = signoff_sample_task(
        task_id=task_id,
        dept_role=body.dept_role,
        user_id=user["id"],
    )
    status = 200 if result["code"] == 0 else 400
    return JSONResponse(result, status_code=status)


# ── 转量产激活（权限最高）────────────────────────────────────────

class ActivateMassProdBody(BaseModel):
    part_id: int


@sample_router.post("/{task_id}/activate-mass-prod")
async def api_activate_mass_prod(task_id: int, body: ActivateMassProdBody, request: Request):
    """
    正式放行转量产（极度核心商业接口）。

    权限：role_level >= 5（老板 / 业务主管）

    前置条件（db_service 层强制校验）：
      1. 三方（tech / qa / sales）全部签到
      2. 任务状态为 COMPLETED
      3. 零件当前状态为 DRAFT 或 SAMPLING
      4. 防重复激活（mass_prod_activated_at 不得已有值）

    写入：
      parts.part_status = 'MASS_PRODUCTION'
      sample_tasks.mass_prod_activated_by/at
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)

    # ── RBAC 权限卡点：role_level >= 5 ──────────────────────────
    if user.get("role_level", 0) < 5:
        return JSONResponse(
            {"code": 1,
             "message": "权限不足：转量产激活需 role_level >= 5（老板/业务主管），"
                        f"当前用户 {user.get('username')} (level={user.get('role_level')}) "
                        "无权执行此操作",
             "data": None},
            status_code=403
        )

    try:
        result = activate_mass_production(
            task_id=task_id,
            part_id=body.part_id,
            user_id=user["id"],
        )
        if result["code"] != 0:
            return JSONResponse(result, status_code=400)
        return JSONResponse(result, status_code=200)
    except Exception as e:
        return JSONResponse(
            {"code": 1, "message": f"转量产激活失败：{str(e)}", "data": None},
            status_code=500
        )


# ── 模具历史导入 ─────────────────────────────────────────────────

@molds_api_router.post("/import-legacy")
async def api_import_legacy_molds(request: Request, file: UploadFile = File(...)):
    """
    批量导入历史 Excel (CSV) 至 molds 表。

    权限：role_level >= 4（管理员 / 高级工程师）

    支持列名容错：
      本厂产品编号 / 模具编号 / 产品编号 → mold_number
      模具类型 → mold_type
      模数 → mold_set_count
      参考冲床吨位 → press_tonnage
      备注 → remarks（含 cavity_count 提取源）
      用料规格 (T*W*PH) → spec_text（含 cavity_count 提取源）

    Upsert 策略：
      ON CONFLICT (mold_number) DO UPDATE SET ...
      -- 白名单：part_id / mold_type / mold_set_count /
                 cavity_count / press_tonnage / remarks
      -- lifecycle_status：原值保留，不被 Excel 覆盖

    返回
    ----
    {
        "code": 0,
        "message": "导入完成，共处理 N 行",
        "data": {
            "total_rows": N, "inserted": N, "updated": N,
            "skipped": N, "part_not_found": [...], "errors": [...]
        }
    }
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)

    # ── RBAC 权限卡点：role_level >= 4 ──────────────────────────
    if user.get("role_level", 0) < 4:
        return JSONResponse(
            {"code": 1,
             "message": "权限不足：模具导入需 role_level >= 4（管理员/高级工程师），"
                        f"当前用户 {user.get('username')} (level={user.get('role_level')}) "
                        "无权执行此操作",
             "data": None},
            status_code=403
        )

    if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
        return JSONResponse(
            {"code": 1, "message": "仅支持 CSV / Excel 文件", "data": None},
            status_code=400
        )

    # 读取文件字节流
    file_bytes = await file.read()
    if not file_bytes:
        return JSONResponse(
            {"code": 1, "message": "上传文件为空", "data": None},
            status_code=400
        )

    try:
        result = import_legacy_molds_from_csv(file_bytes, created_by_user_id=user["id"])
        if result["code"] != 0:
            return JSONResponse(result, status_code=400)
        return JSONResponse(result, status_code=200)
    except Exception as e:
        return JSONResponse(
            {"code": 1, "message": f"模具导入异常：{str(e)}", "data": None},
            status_code=500
        )


# ── 注册子路由（无前缀，直接挂载到根路径） ──────────────────────
# 注意：_mold_router 自身不带 prefix，注册到 main.py 后路径为：
#   /tooling  /molds  /cavity_review  （不受 /tech 前缀影响）
# tech.router（/tech/*）继续处理待修池/扫码/管理看板
mold_router = _mold_router   # 导出，供 main.py 直接挂载到根路径


# ============================================================================
# 阶段四 & 五：双轨维修路由 (/tech/maintenance/*)
# 对应 .cursorrules V3.2 §2.3 "两扫制" + 双轨逻辑
# ============================================================================
maintenance_router = APIRouter(prefix="/tech/maintenance", tags=["maintenance"])


@maintenance_router.get("/list", response_class=HTMLResponse)
def maintenance_list_page(request: Request,
                          equipment_id: int = None,
                          status: str = ""):
    """维修记录列表页（支持按机台/状态过滤）。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    logs = get_maintenance_logs(equipment_id=equipment_id, status=status or None)
    return templates.TemplateResponse("tech/maintenance_list.html", {
        "request": request, "user": user,
        "logs": logs, "filter_equipment_id": equipment_id,
        "filter_status": status,
    })


@maintenance_router.get("/list/json")
def maintenance_list_json(request: Request,
                          equipment_id: int = None,
                          status: str = ""):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    return JSONResponse(get_maintenance_logs(
        equipment_id=equipment_id, status=status or None))


@maintenance_router.post("/report")
def maintenance_report(request: Request,
                      target_type: str = Form(...),
                      equipment_id: int = Form(...),
                      mold_id: int = Form(None),
                      repair_mode: str = Form(...),
                      remarks: str = Form("")):
    """
    报修入口（双轨）：
      repair_mode = 'MOLD_ON_MACHINE'     → 不拆模维修（机台锁定 MOLD_REPAIR_ON_MACHINE）
      repair_mode = 'MOLD_DISMOUNTED'     → 拆模维修（机台释放 IDLE）
      repair_mode = 'MACHINE_REPAIR'       → 设备维修（机台置 EQUIP_REPAIR）

    联动机台状态熔断（通过 equipment_change_status）。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"success": False, "message": "权限不足"},
                            status_code=403)

    if repair_mode not in ("MOLD_ON_MACHINE", "MOLD_DISMOUNTED", "MACHINE_REPAIR"):
        return JSONResponse({
            "success": False,
            "message": "repair_mode 必须为 MOLD_ON_MACHINE / MOLD_DISMOUNTED / MACHINE_REPAIR"
        }, status_code=400)

    try:
        result = maintenance_trigger_with_decoupling(
            equipment_id=equipment_id,
            mold_id=mold_id,
            repair_mode=repair_mode,
            reporter_id=user["id"],
            fault_reason=remarks,
        )
        if result.get("code") != 0:
            return JSONResponse({"success": False, "message": result["message"]},
                                status_code=400)
        return JSONResponse({
            "success": True,
            "message": result["message"],
            "data": result.get("data"),
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@maintenance_router.post("/complete")
def maintenance_complete(request: Request,
                       log_id: int = Form(...),
                       resolved: bool = Form(True),
                       remarks: str = Form("")):
    """
    维修完成：
      resolved=True  → 状态 RESOLVED，联动恢复机台状态（RUNNING/IDLE）
      resolved=False → 状态 CANCELLED
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"success": False, "message": "权限不足"},
                            status_code=403)

    result = maintenance_resolve_with_coupling(
        maintenance_log_id=log_id,
        resolver_id=user["id"],
        resolved=resolved,
        remarks=remarks,
    )
    if result.get("code") != 0:
        return JSONResponse({"success": False, "message": result["message"]},
                            status_code=400)
    return JSONResponse({"success": True, "message": result["message"], "data": result.get("data")})


@maintenance_router.get("/open/{equipment_id}")
def maintenance_open_json(request: Request, equipment_id: int):
    """查询指定机台当前未关闭的维修记录（用于前端弹窗预填）。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    log = get_open_maintenance(equipment_id)
    return JSONResponse(log if log else {})


@maintenance_router.get("/equipment/{equipment_id}", response_class=HTMLResponse)
def maintenance_equipment_page(request: Request, equipment_id: int):
    """指定机台的维修记录页面（维修看板穿透）。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    eq = get_equipment_by_id(equipment_id)
    if not eq:
        return HTMLResponse("机台不存在", status_code=404)
    logs = get_maintenance_logs(equipment_id=equipment_id)
    open_log = get_open_maintenance(equipment_id)
    return templates.TemplateResponse("tech/maintenance_dualtrack.html", {
        "request": request, "user": user,
        "equipment": eq,
        "logs": logs,
        "open_log": open_log,
    })


# ==============================================================================
# 打样双轨路由（Tech 新增，§Tech）
# ==============================================================================

from app.services.tech_service import (
    create_part_profile,
    start_prototype,
    report_prototype,
    report_simple_prototype,
    get_sample_inventory,
    get_part_profile,
)


# ── 源头建档 ──────────────────────────────────────────────────
@router.post("/parts/profile")
def api_create_part_profile(request: Request,
                            part_number: str = Form(...),
                            internal_name: str = Form(...),
                            material_name: str = Form(...),
                            thickness: float = Form(...),
                            width: float = Form(...),
                            press_stroke: float = Form(...),
                            cavity_count: int = Form(1),
                            mold_tonnage: float = Form(0.0)):
    """
    源头建档 — 录入零件 T/W/P 基因参数。

    权限：role_level >= 2
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = create_part_profile(
        part_number=part_number,
        internal_name=internal_name,
        material_name=material_name,
        thickness=thickness,
        width=width,
        press_stroke=press_stroke,
        cavity_count=cavity_count,
        mold_tonnage=mold_tonnage,
        created_by=user["id"],
    )
    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


# ── 连续模打样开机 ─────────────────────────────────────────────
@router.post("/prototype/start")
def api_start_prototype(request: Request,
                        machine_id: int = Form(...)):
    """
    连续模打样开机：机台设为 PROTOTYPING。

    权限：role_level >= 2
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = start_prototype(machine_id=machine_id)
    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


# ── 连续模打样报工 ─────────────────────────────────────────────
@router.post("/prototype/report")
def api_report_prototype(request: Request,
                         machine_id: int = Form(...),
                         qty: int = Form(...),
                         operator_id: int = Form(0)):
    """
    连续模打样报工：填入即生效，不扣料不入 wip，
    直接累加 sample_inventory。

    权限：role_level >= 2
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = report_prototype(
        machine_id=machine_id,
        qty=qty,
        operator_id=operator_id if operator_id else user["id"],
    )
    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


# ── 简易模打样（完全线下，无需扫机台）────────────────────────
@router.post("/prototype/simple")
def api_report_simple_prototype(request: Request,
                                part_id: int = Form(...),
                                qty: int = Form(...),
                                operator_id: int = Form(0)):
    """
    简易模打样：完全线下隐形，无需扫机台。
    直接原子累加 sample_inventory.sample_qty。

    权限：role_level >= 2
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = report_simple_prototype(
        part_id=part_id,
        qty=qty,
        operator_id=operator_id if operator_id else user["id"],
    )
    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


# ── 打样虚拟库查询 ────────────────────────────────────────────
@router.get("/prototype/inventory")
def api_sample_inventory(request: Request, part_id: int = 0):
    """查询打样虚拟库（sample_inventory）。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_sample_inventory(
        part_id=part_id if part_id else None,
    )
    return JSONResponse({"code": 0, "data": rows})


# ── 零件主档查询 ────────────────────────────────────────────
@router.get("/parts/{part_id}/profile")
def api_get_part_profile(request: Request, part_id: int):
    """读取零件主档（含 T/W/P + 模具参数）。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    profile = get_part_profile(part_id)
    if not profile:
        return JSONResponse({"error": f"零件 #{part_id} 不存在"}, status_code=404)
    return JSONResponse({"code": 0, "data": profile})

