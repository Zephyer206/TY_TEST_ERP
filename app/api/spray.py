"""
app/api/spray.py
喷涂部路由 — 喷涂扫码报工 / 配方管理 / 看板
前缀: /spray
"""
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.db_service import (
    get_all_parts_for_spraying,
    get_spraying_today_summary,
    submit_spraying_log_worker,
    submit_spraying_log_manager,
    get_spraying_recipe,
    get_all_spraying_recipes,
    upsert_spraying_recipe,
    sync_spraying_consumption,
    recalculate_spraying_consumption,
    get_spraying_material_summary,
    get_spraying_part_summary,
    get_spraying_process_kanban,
    get_spraying_material_balance,
    batch_sync_spraying_consumption,
    get_parts_without_recipe,
    get_spraying_uncalc_parts,
)

router = APIRouter(prefix="/spray", tags=["spray"])


# ── 喷涂扫码报工 ─────────────────────────────────────────────────
@router.get("/scan", response_class=HTMLResponse)
def spray_scan_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["department"] not in ("spraying", "admin") and user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    parts = get_all_parts_for_spraying()
    summary = get_spraying_today_summary()
    return templates.TemplateResponse("spray/spray_scan.html", {
        "request": request, "user": user,
        "parts": parts, "summary": summary,
    })


@router.post("/scan/submit")
def spray_scan_submit(request: Request,
                       part_id: int = Form(...),
                       quantity: int = Form(...),
                       actual_date: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 1:
        raise HTTPException(status_code=403, detail="权限不足")
    try:
        submit_spraying_log_worker(
            part_id=part_id,
            quantity=quantity,
            operator_id=user["id"],
            actual_date=actual_date if actual_date else None,
        )
        return JSONResponse({"ok": True, "message": "报工成功"})
    except Exception as e:
        return JSONResponse({"ok": False, "detail": str(e)}, status_code=400)


# ── 喷涂配方管理 ─────────────────────────────────────────────────
@router.get("/recipe", response_class=HTMLResponse)
def spray_recipe_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["department"] not in ("spraying", "admin") and user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    parts = get_all_parts_for_spraying()
    recipes = get_all_spraying_recipes()
    mat_summary = get_spraying_material_summary()
    part_summary = get_spraying_part_summary()
    return templates.TemplateResponse("spray/spray_recipe.html", {
        "request": request, "user": user,
        "parts": parts, "recipes": recipes,
        "material_summary": mat_summary,
        "part_summary": part_summary,
    })


@router.post("/recipe/save")
def spray_recipe_save(request: Request,
                      part_id: int = Form(...),
                      sand_material: str = Form(""),
                      sand_dosage: float = Form(0),
                      coating_material: str = Form(""),
                      coating_dosage: float = Form(0),
                      surface_type: str = Form("single"),
                      coating_color: str = Form(""),
                      trigger_recalc: str = Form("false")):
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse({"ok": False, "detail": "权限不足"}, status_code=403)
    try:
        recipe_id = upsert_spraying_recipe(
            part_id=part_id,
            sand_material=sand_material,
            sand_dosage=sand_dosage,
            coating_material=coating_material,
            coating_dosage=coating_dosage,
            surface_type=surface_type,
            coating_color=coating_color,
        )
        if trigger_recalc.lower() == "true":
            batch_sync_spraying_consumption(part_id)
        uncalc = get_spraying_uncalc_parts()
        return JSONResponse({
            "ok": True,
            "has_uncalc": len(uncalc) > 0,
            "uncalc_count": len(uncalc),
            "recipe_id": recipe_id,
        })
    except Exception as e:
        return JSONResponse({"ok": False, "detail": str(e)}, status_code=400)


@router.get("/recipe/{part_id}")
def spray_recipe_get(request: Request, part_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    recipe = get_spraying_recipe(part_id)
    return JSONResponse(recipe or {"exists": False})


@router.post("/recipe/sync")
def spray_recipe_sync(request: Request, part_id: int = Form(...)):
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse({"ok": False, "detail": "权限不足"}, status_code=403)
    try:
        sync_spraying_consumption(part_id)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "detail": str(e)}, status_code=400)


# ── 喷涂看板 ──────────────────────────────────────────────────────
@router.get("/kanban", response_class=HTMLResponse)
def spray_kanban_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    kanban = get_spraying_process_kanban()
    summary = get_spraying_today_summary()
    return templates.TemplateResponse("spray/spray_kanban.html", {
        "request": request, "user": user,
        "kanban": kanban, "summary": summary,
    })


# ── 喷涂零件详情 ──────────────────────────────────────────────────
@router.get("/part/{part_id}", response_class=HTMLResponse)
def spray_part_detail(request: Request, part_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    from app.services.db_service import get_spraying_logs_by_part, get_spraying_recipe
    logs = get_spraying_logs_by_part(part_id)
    recipe = get_spraying_recipe(part_id)
    return templates.TemplateResponse("spray/spray_part_detail.html", {
        "request": request, "user": user,
        "part_id": part_id, "logs": logs, "recipe": recipe,
    })


# ── 喷涂经理端 ───────────────────────────────────────────────────
@router.get("/manager", response_class=HTMLResponse)
def spray_manager_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["department"] not in ("spraying", "admin") and user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="权限不足")
    mat_summary = get_spraying_material_summary()
    part_summary = get_spraying_part_summary()
    return templates.TemplateResponse("spray/spray_manager.html", {
        "request": request, "user": user,
        "material_summary": mat_summary,
        "part_summary": part_summary,
    })


@router.post("/manager/submit")
def spray_manager_submit(request: Request,
                         part_id: int = Form(...),
                         quantity: int = Form(...),
                         actual_date: str = Form(...)):
    user = get_current_user(request)
    if not user or user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="权限不足")
    try:
        submit_spraying_log_manager(
            part_id=part_id,
            quantity=quantity,
            actual_date=actual_date,
            manager_id=user["id"],
        )
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "detail": str(e)}, status_code=400)


# ── 喷涂物料平衡 ─────────────────────────────────────────────────
@router.get("/material", response_class=HTMLResponse)
def spray_material_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    mat_summary = get_spraying_material_summary()
    part_summary = get_spraying_part_summary()
    return templates.TemplateResponse("spray/spray_material.html", {
        "request": request, "user": user,
        "material_summary": mat_summary,
        "part_summary": part_summary,
    })


# ── 喷涂物料余额 API ─────────────────────────────────────────────
@router.get("/balance")
def spray_balance(request: Request, start_date: str = "", end_date: str = ""):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    rows = get_spraying_material_balance(
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
    )
    return JSONResponse(rows)
