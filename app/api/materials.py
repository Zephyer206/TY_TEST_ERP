"""
app/api/materials.py
仓库/物料路由 — 台账 / IQC / 入库 / 分条 / 报废
前缀: /materials
"""
from fastapi import APIRouter, Form, Request, HTTPException, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.db_service import (
    get_all_materials,
    count_materials,
    get_material_by_id,
    get_material_children,
    get_material_summary,
    add_material,
    update_material,
    scrap_material,
    slit_material,
    execute_material_slitting,
    process_slitting,
    get_materials_for_iqc,
    get_materials_for_iqc_incoming,
    submit_iqc,
    confirm_material_whse,
    get_materials_for_whse_confirmation,
    get_scrap_logs,
    count_scrap_logs,
    get_scrap_summary,
    receive_material,
    slit_mother_coil,
    consume_aux_material,
    get_material_batch,
    list_material_batches,
)

router = APIRouter(prefix="/materials", tags=["materials"])


# ── 物料台账 ────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
def materials_page(request: Request, keyword: str = "", material_type: str = "",
                  show_closed: int = 0, page: int = 1):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    limit, offset = 50, (page - 1) * 50
    materials = get_all_materials(filters={
        "keyword": keyword, "material_type": material_type,
        "show_closed": bool(show_closed)}, limit=limit, offset=offset)
    total = count_materials(filters={
        "keyword": keyword, "material_type": material_type,
        "show_closed": bool(show_closed)})
    summary = get_material_summary()
    return templates.TemplateResponse("whse/materials.html", {
        "request": request, "user": user,
        "materials": materials, "total": total,
        "keyword": keyword, "material_type": material_type,
        "show_closed": show_closed,
        "page": page,
        "total_pages": max(1, (total + limit - 1) // limit),
        "summary": summary,
    })


@router.get("/api/list")
def materials_api_list(request: Request, keyword: str = "",
                       material_type: str = "", page: int = 1):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "Unauthorized"}, status_code=401)
    limit, offset = 50, (page - 1) * 50
    materials = get_all_materials(filters={
        "keyword": keyword, "material_type": material_type,
        "show_closed": False}, limit=limit, offset=offset)
    total = count_materials(filters={
        "keyword": keyword, "material_type": material_type,
        "show_closed": False})
    return JSONResponse({"code": 0, "message": "ok",
                         "data": {"materials": materials, "total": total}})


# ── 物料详情 ────────────────────────────────────────────────────
@router.get("/{material_id}", response_class=HTMLResponse)
def material_detail(request: Request, material_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    material = get_material_by_id(material_id)
    if not material:
        return HTMLResponse("Material not found", status_code=404)
    children = get_material_children(material_id)
    return templates.TemplateResponse("whse/material_detail.html", {
        "request": request, "user": user,
        "material": material, "children": children,
    })


# ── 物料添加 / 修改 ─────────────────────────────────────────────
@router.post("/add", name="material_add")
def material_add(request: Request,
                 material_name: str = Form(...),
                 material_type: str = Form(...),
                 specification: str = Form(""),
                 unit: str = Form("kg"),
                 initial_stock: float = Form(0),
                 min_stock: float = Form(0),
                 supplier_name: str = Form(""),
                 supplier_contact: str = Form(""),
                 supplier_phone: str = Form(""),
                 location: str = Form(""),
                 notes: str = Form("")):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("role_level", 0) < 3:
        return HTMLResponse("Insufficient permissions", status_code=403)
    add_material(material_name, material_type, specification, unit,
                 initial_stock, min_stock, supplier_name, supplier_contact,
                 supplier_phone, location, notes, user["id"])
    return RedirectResponse("/materials", status_code=303)


@router.post("/{material_id}/update", name="material_update")
def material_update(request: Request, material_id: int,
                    material_name: str = Form(...),
                    material_type: str = Form(...),
                    specification: str = Form(""),
                    unit: str = Form("kg"),
                    min_stock: float = Form(0),
                    supplier_name: str = Form(""),
                    supplier_contact: str = Form(""),
                    supplier_phone: str = Form(""),
                    location: str = Form(""),
                    notes: str = Form("")):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("role_level", 0) < 3:
        return HTMLResponse("Insufficient permissions", status_code=403)
    update_material(material_id, material_name, material_type, specification,
                   unit, min_stock, supplier_name, supplier_contact,
                   supplier_phone, location, notes)
    return RedirectResponse(f"/materials/{material_id}", status_code=303)


# ── 分条（钢带大卷切小卷）─────────────────────────────────────
@router.get("/{material_id}/slit", response_class=HTMLResponse)
def material_slit_page(request: Request, material_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    material = get_material_by_id(material_id)
    if not material:
        return HTMLResponse("Material not found", status_code=404)
    return templates.TemplateResponse("whse/slit.html", {
        "request": request, "user": user, "material": material,
    })


@router.post("/{material_id}/slit", name="material_slit")
def material_slit(request: Request, material_id: int,
                  child_weights: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("role_level", 0) < 3:
        return HTMLResponse("Insufficient permissions", status_code=403)
    material = get_material_by_id(material_id)
    if not material:
        return HTMLResponse("Material not found", status_code=404)
    weight_list = [float(w.strip()) for w in child_weights.split(',') if w.strip()]
    result = process_slitting(material_id, weight_list, user["id"])
    if result.get("code") == 1:
        return HTMLResponse(f"Slitting failed: {result.get('message')}", status_code=400)
    return RedirectResponse("/materials", status_code=303)


# ── IQC 来料检验 ────────────────────────────────────────────────
@router.get("/iqc/incoming", response_class=HTMLResponse)
def iqc_incoming_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    materials = get_materials_for_iqc_incoming()
    return templates.TemplateResponse("whse/iqc_incoming.html", {
        "request": request, "user": user, "materials": materials,
    })


@router.get("/iqc", response_class=HTMLResponse)
def iqc_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    materials = get_materials_for_iqc()
    return templates.TemplateResponse("whse/iqc.html", {
        "request": request, "user": user, "materials": materials,
    })


@router.post("/iqc/{material_id}/submit")
def iqc_submit(request: Request, material_id: int,
               iqc_result: str = Form(...), notes: str = Form("")):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("role_level", 0) < 3:
        return HTMLResponse("Insufficient permissions", status_code=403)
    submit_iqc(material_id, iqc_result, notes, user["id"])
    return RedirectResponse("/materials/iqc", status_code=303)


# ── 仓库确认 ────────────────────────────────────────────────────
@router.get("/whse", response_class=HTMLResponse)
def whse_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    materials = get_materials_for_whse_confirmation()
    return templates.TemplateResponse("whse/whse.html", {
        "request": request, "user": user, "materials": materials,
    })


@router.post("/whse/{material_id}/confirm")
def whse_confirm(request: Request, material_id: int,
                 confirmed_by: str = Form("")):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    confirm_material_whse(material_id, confirmed_by, user["id"])
    return RedirectResponse("/materials/whse", status_code=303)


# ── 报废日志 ─────────────────────────────────────────────────────
@router.get("/scrap-logs", response_class=HTMLResponse)
def materials_scrap_logs(request: Request, page: int = 1):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    limit, offset = 100, (page - 1) * 100
    logs = get_scrap_logs(limit=limit, offset=offset)
    total = count_scrap_logs()
    summary = get_scrap_summary()
    return templates.TemplateResponse("prod/scrap_logs.html", {
        "request": request, "user": user,
        "logs": logs, "summary": summary,
        "page": page,
        "total_pages": max(1, (total + limit - 1) // limit),
    })


# ============================================================================
# 阶段五：原料批次 QR 赋码与物流  (v5_material_qr_tracking)
# ============================================================================
# 新增 APIRouter，前缀 /api/materials，路径与现有 /materials HTML 路由完全隔离
material_api_router = APIRouter(prefix="/api/materials", tags=["material_qr"])


# ── Pydantic 接收模型 ─────────────────────────────────────────────

class ReceiveMaterialBody(BaseModel):
    material_category: str = Field(
        ..., description="PROD(主材/钢带) | AUX(辅料)")
    material_name: str
    initial_weight: float = Field(..., gt=0, description="入库数量（kg或单位）")
    spec: str | None = None
    supplier_name: str | None = None
    heat_number: str | None = None
    cert_file_path: str | None = None
    purchase_unit_price: float | None = None
    unit: str = Field(default='kg', description="计量单位：主材默认kg，辅料可传桶/升/个")


class SlitItemBody(BaseModel):
    weight: float = Field(..., gt=0)
    material_name: str | None = None
    spec: str | None = None
    unit: str | None = None


class SlitMotherCoilBody(BaseModel):
    slit_items: list[SlitItemBody] = Field(..., min_length=1)


class ConsumeAuxBody(BaseModel):
    consume_qty: float = Field(..., gt=0)
    related_work_order_id: int | None = None


# ── 扫码入库 ─────────────────────────────────────────────────────

@material_api_router.post("/receive")
async def api_receive_material(body: ReceiveMaterialBody, request: Request):
    """
    扫码入库（仓管扫码，一卷一码）。

    权限：role_level >= 3（仓库/生产可操作）

    极简入库：
    - 入库即 IN_STOCK，无需品质放行
    - 炉批号/采购单价均为可选字段
    - 自动生成 QR UID（MAT-YYMM-NNN）
    - 同步写入 RECEIVE 流水
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)
    if user.get("role_level", 0) < 3:
        return JSONResponse({"code": 1,
                             "message": f"权限不足（需 role_level >= 3），当前用户 {user.get('username')} (level={user.get('role_level')})",
                             "data": None}, status_code=403)
    try:
        result = receive_material(
            material_category=body.material_category,
            material_name=body.material_name,
            initial_weight=body.initial_weight,
            user_id=user["id"],
            spec=body.spec,
            supplier_name=body.supplier_name,
            heat_number=body.heat_number,
            cert_file_path=body.cert_file_path,
            purchase_unit_price=body.purchase_unit_price,
            unit=body.unit,
        )
        if result["code"] != 0:
            return JSONResponse(result, status_code=400)
        return JSONResponse(result, status_code=200)
    except Exception as e:
        return JSONResponse(
            {"code": 1, "message": f"入库异常：{str(e)}", "data": None},
            status_code=500
        )


# ── 分条操作 ─────────────────────────────────────────────────────

@material_api_router.post("/{mother_qr_uid}/slit")
async def api_slit_mother(mother_qr_uid: str, body: SlitMotherCoilBody, request: Request):
    """
    大卷分条为小卷（母子裂变溯源）。

    权限：role_level >= 3（仓库/生产可操作）

    原子事务：
    - SELECT FOR UPDATE 锁定母卷，防止并发超扣
    - 遍历生成子卷 QR UID
    - UPDATE 母卷 current_weight，扣减分条总重
    - 若扣减至 <= 0，自动置 DEPLETED
    - 写入 SLIT 流水（变化量为负数）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)
    if user.get("role_level", 0) < 3:
        return JSONResponse({"code": 1,
                             "message": f"权限不足（需 role_level >= 3），当前用户 {user.get('username')} (level={user.get('role_level')})",
                             "data": None}, status_code=403)

    slit_items = [item.model_dump() for item in body.slit_items]
    try:
        result = slit_mother_coil(
            mother_qr_uid=mother_qr_uid,
            slit_items=slit_items,
            user_id=user["id"],
        )
        if result["code"] != 0:
            return JSONResponse(result, status_code=400)
        return JSONResponse(result, status_code=200)
    except Exception as e:
        return JSONResponse(
            {"code": 1, "message": f"分条异常：{str(e)}", "data": None},
            status_code=500
        )


# ── 辅料快捷领用/消耗 ──────────────────────────────────────────

@material_api_router.post("/aux/{qr_uid}/consume")
async def api_consume_aux(qr_uid: str, body: ConsumeAuxBody, request: Request):
    """
    辅料快捷领用/消耗（仅 AUX 批次可用）。

    权限：role_level >= 2（生产/仓库可操作）

    校验链：
    1. 批次存在且 material_category == 'AUX'（非 AUX → 403）
    2. current_weight >= consume_qty（库存不足 → 400）
    3. UPDATE 扣减 current_weight，<= 0 → lifecycle_status = 'DEPLETED'
    4. 写入 CONSUME 流水

    返回
    ----
    {"code": 0, "message": "领用成功", "data": {
        "qr_uid": ..., "consumed": ..., "remaining": ...,
        "lifecycle_status": ..., "unit": ...}}
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1,
                             "message": f"权限不足（需 role_level >= 2），当前用户 {user.get('username')} (level={user.get('role_level')})",
                             "data": None}, status_code=403)
    try:
        result = consume_aux_material(
            qr_uid=qr_uid,
            consume_qty=body.consume_qty,
            user_id=user["id"],
            related_work_order_id=body.related_work_order_id,
        )
        if result["code"] != 0:
            return JSONResponse(result, status_code=400)
        return JSONResponse(result, status_code=200)
    except Exception as e:
        return JSONResponse(
            {"code": 1, "message": f"领用异常：{str(e)}", "data": None},
            status_code=500
        )


# ── 批次查询 ─────────────────────────────────────────────────────

@material_api_router.get("/{qr_uid}")
async def api_get_batch(qr_uid: str, request: Request):
    """
    查询单个原料批次详情。

    权限：role_level >= 1（登录即可）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)
    batch = get_material_batch(qr_uid)
    if not batch:
        return JSONResponse({"code": 1, "message": f"批次 #{qr_uid} 不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 0, "message": "ok", "data": batch})


@material_api_router.get("")
async def api_list_batches(
        request: Request,
        material_category: str | None = None,
        lifecycle_status: str | None = None,
        keyword: str = "",
        limit: int = 50,
        offset: int = 0,
):
    """
    分页查询原料批次列表。

    权限：role_level >= 1
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录", "data": None}, status_code=401)
    batches = list_material_batches(
        material_category=material_category,
        lifecycle_status=lifecycle_status,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return JSONResponse({"code": 0, "message": "ok", "data": batches})
