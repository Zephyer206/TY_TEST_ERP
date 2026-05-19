"""
app/api/pkg.py
包装部路由 — 包装报工 / 扫码 / 进度 / 发货
前缀: /pkg
"""
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.db_service import (
    get_pkg_ready_inventory,
    get_pkg_today_summary,
    get_pkg_error_logs,
    get_pkg_blocked_parts,
    submit_packaging_log,
    submit_shipping_log,
    log_pkg_error,
    get_pkg_progress_view,
    get_pkg_parts_pending_inspection,
    get_pkg_reconciliation,
    submit_pkg_entry,
    get_all_parts_for_pkg_entry,
    get_pkg_daily_summary,
    check_pkg_shipping_eligibility,
    check_pkg_packaging_eligibility,
    # ── 阶段五：发货与 QA ──
    get_all_delivery_notes,
    get_delivery_note_detail,
    create_delivery_note,
    cancel_delivery_note,
    get_shipping_eligibility,
    get_customer_alias,
    upsert_customer_alias,
    get_all_customers,
)
from app.services.delivery_service import (
    get_delivery_items,
    confirm_delivery,
    get_delivery_notes_with_alias_status,
)
from app.services.pkg_service import (
    pack_and_stock,
    get_wip_overview,
    get_defect_logs,
)

router = APIRouter(prefix="/pkg", tags=["pkg"])


# ── 包装扫码 ──────────────────────────────────────────────────────
@router.get("/scan", response_class=HTMLResponse)
def pkg_scan_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    inventory = get_pkg_ready_inventory()
    summary = get_pkg_today_summary()
    return templates.TemplateResponse("pkg/pkg_scan.html", {
        "request": request, "user": user,
        "inventory": inventory, "summary": summary,
    })


@router.post("/pkg/scan")
def pkg_scan(request: Request,
             part_id: int = Form(...),
             qty_checked: int = Form(...),
             qty_passed: int = Form(...)):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    submit_packaging_log(part_id=part_id,
                         operator_id=user["id"],
                         qty_checked=qty_checked,
                         qty_passed=qty_passed,
                         actual_date=None)
    return RedirectResponse("/pkg/scan", 303)


# ── 包装进度 ──────────────────────────────────────────────────────
@router.get("/progress", response_class=HTMLResponse)
def pkg_progress_page(request: Request, target_date: str = ""):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    rows = get_pkg_progress_view(target_date=target_date if target_date else None)
    summary = get_pkg_daily_summary(target_date=target_date if target_date else None)
    return templates.TemplateResponse("pkg/pkg_progress.html", {
        "request": request, "user": user,
        "rows": rows, "summary": summary,
        "target_date": target_date,
    })


# ── 包装发货 ──────────────────────────────────────────────────────
@router.get("/shipping", response_class=HTMLResponse)
def pkg_shipping_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    ready = get_pkg_ready_inventory()
    return templates.TemplateResponse("pkg/pkg_shipping.html", {
        "request": request, "user": user,
        "ready_inventory": ready,
    })


@router.post("/pkg/shipping")
def pkg_shipping(request: Request,
                 part_id: int = Form(...),
                 qty: int = Form(...),
                 box_no: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    try:
        submit_shipping_log(part_id=part_id,
                            operator_id=user["id"],
                            qty=qty,
                            box_no=box_no)
    except ValueError as e:
        return HTMLResponse(
            f"<html><body><script>alert('{str(e)}'); history.back();</script></body></html>",
            status_code=400)
    return RedirectResponse("/pkg/shipping", 303)


# ── 包装补录 ──────────────────────────────────────────────────────
@router.get("/entry", response_class=HTMLResponse)
def pkg_entry_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    parts = get_all_parts_for_pkg_entry()
    return templates.TemplateResponse("pkg/pkg_entry.html", {
        "request": request, "user": user,
        "parts": parts,
    })


@router.post("/pkg/entry")
def pkg_entry(request: Request,
              part_id: int = Form(...),
              qty_passed: int = Form(...),
              date_str: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    submit_pkg_entry(part_id=part_id,
                     operator_id=user["id"],
                     date_str=date_str,
                     qty_passed=qty_passed)
    return RedirectResponse("/pkg/entry", 303)


# ============================================================================
# 阶段五：发货管理 (/pkg/delivery/*)
# 对应 .cursorrules V3.2 §2.4 "一内多外" 客户件号翻译 + §2.2 定点
# ============================================================================

@router.get("/delivery", response_class=HTMLResponse)
def delivery_list_page(request: Request,
                      customer_name: str = "",
                      status: str = ""):
    """发货单列表页（含客户过滤）。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    notes = get_all_delivery_notes(
        customer_name=customer_name or None,
        status=status or None,
    )
    customers = get_all_customers()
    return templates.TemplateResponse("pkg/delivery_list.html", {
        "request": request, "user": user,
        "notes": notes,
        "customers": customers,
        "filter_customer": customer_name,
        "filter_status": status,
    })


@router.get("/delivery/json")
def delivery_list_json(request: Request,
                     customer_name: str = "",
                     status: str = ""):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    return JSONResponse(get_all_delivery_notes(
        customer_name=customer_name or None,
        status=status or None,
    ))


@router.get("/delivery/{dn_id}", response_class=HTMLResponse)
def delivery_detail_page(request: Request, dn_id: int):
    """发货单详情（含客户件号翻译明细）。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    dn = get_delivery_note_detail(dn_id)
    if not dn:
        return HTMLResponse("发货单不存在", status_code=404)
    return templates.TemplateResponse("pkg/delivery_detail.html", {
        "request": request, "user": user,
        "dn": dn,
    })


@router.post("/delivery/create")
def delivery_create(request: Request,
                   customer_name: str = Form(...),
                   notes: str = Form(""),
                   shipped_at: str = Form(""),
                   # 明细通过 JSON body 传入
                   items_json: str = Form("[]")):
    """
    创建发货单。
    items_json: JSON 字符串 [{"part_id": int, "qty": int, "lot_no": str, "remark": str}, ...]
    """
    import json
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")

    try:
        items = json.loads(items_json)
    except json.JSONDecodeError:
        return HTMLResponse(
            "<html><body><script>alert('明细格式错误'); history.back();</script></body></html>",
            status_code=400)

    ship_ts = shipped_at if shipped_at else None
    result = create_delivery_note(
        customer_name=customer_name,
        created_by=user["id"],
        items=items,
        notes=notes,
        shipped_at=ship_ts,
    )
    if result.get("code") != 0:
        return HTMLResponse(
            f"<html><body><script>alert('{result['message']}'); history.back();</script></body></html>",
            status_code=400)
    return RedirectResponse("/pkg/delivery", 303)


@router.post("/delivery/{dn_id}/cancel")
def delivery_cancel(request: Request, dn_id: int):
    """取消发货单（仅限 SHIPPED 状态）。"""
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    result = cancel_delivery_note(dn_id, operator_id=user["id"])
    if result.get("code") != 0:
        return HTMLResponse(
            f"<html><body><script>alert('{result['message']}'); history.back();</script></body></html>",
            status_code=400)
    return RedirectResponse("/pkg/delivery", 303)


# ── 客户件号别名管理 ────────────────────────────────────────────────────

@router.post("/alias/upsert")
def alias_upsert(request: Request,
                part_id: int = Form(...),
                customer_name: str = Form(...),
                customer_part_no: str = Form(...),
                customer_part_name: str = Form("")):
    """新增或更新客户件号别名映射。"""
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    upsert_customer_alias(
        part_id=part_id,
        customer_name=customer_name,
        customer_part_no=customer_part_no,
        customer_part_name=customer_part_name,
    )
    return JSONResponse({"code": 0, "message": "别名已保存"})


@router.get("/alias/{part_id}")
def alias_query(request: Request, part_id: int, customer_name: str = ""):
    """查询零件的客户件号别名。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    alias = get_customer_alias(part_id, customer_name or None)
    return JSONResponse(alias if alias else {})


# ============================================================================
# §8.3 增强端点：带别名状态感知的发货明细 + 发货确认
# ============================================================================

@router.get("/delivery/{dn_id}/items")
def delivery_items_with_alias(request: Request, dn_id: int, customer_name: str = ""):
    """
    发货明细（含客户件号翻译 + 别名状态感知，§8.3 核心 API）。

    前端据此判断：
      - alias_status = 'ALIAS_OK'        → display_* 正常显示
      - alias_status = 'PENDING_CONFIG'  → display_* = None，UI 必须显示警告并引导配置
      - alias_status = 'INTERNAL_ONLY'   → 内部件，不触发告警
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    if not customer_name:
        return JSONResponse({"error": "缺少参数 customer_name"}, status_code=400)

    items = get_delivery_items(dn_id=dn_id, customer_name=customer_name)
    pending_count = sum(
        1 for it in items if it["alias_status"] == "PENDING_CONFIG"
    )
    return JSONResponse({
        "code": 0,
        "data": {
            "items": items,
            "pending_alias_count": pending_count,
            "has_pending_alias": pending_count > 0,
        },
    })


@router.get("/delivery/notes/with-alias-status")
def delivery_notes_with_alias_status(
    request: Request,
    customer_name: str = "",
    status: str = "",
):
    """
    发货单列表（附加别名待配统计，§8.3 辅助 API）。
    返回每个发货单的 pending_alias_count，前端据此显示告警徽章。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    notes = get_delivery_notes_with_alias_status(
        customer_name=customer_name,
        status_filter=status,
    )
    return JSONResponse({"code": 0, "data": notes})


@router.post("/delivery/{dn_id}/confirm")
def delivery_confirm(request: Request, dn_id: int):
    """
    发货确认（§8.3）：扣减成品库存 + 更新发货单状态。

    权限：role_level >= 4
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"error": "权限不足"}, status_code=403)

    result = confirm_delivery(dn_id=dn_id, operator_id=user["id"])
    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


# ============================================================================
# §8.3 全检入库 — pack_and_stock
# ============================================================================

@router.get("/wip", response_class=HTMLResponse)
def wip_page(request: Request):
    """待检库存（wip_pcs）看板页面。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("pkg/wip.html", {
        "request": request, "user": user,
    })


@router.post("/wip/stock-in")
def stock_in(request: Request,
             work_order_id: int = Form(...),
             valid_qty: int = Form(...),
             reject_qty: int = Form(0)):
    """
    全检入库（.cursorrules §8.3 流水线终点）。

    执行链路：
      1. 校验工单 wip_pcs 充足
      2. work_orders.wip_pcs -= valid_qty（扣除待检）
      3. parts.stock_pcs += valid_qty（增加成品库存）
      4. INSERT defect_logs（如有不良品）
      5. INSERT stock_in_logs（入库流水追溯）

    权限：role_level >= 3
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 3:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)

    result = pack_and_stock(
        work_order_id=work_order_id,
        valid_qty=valid_qty,
        operator_id=user["id"],
        reject_qty=reject_qty,
    )
    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


@router.get("/wip/json")
def wip_json(request: Request, work_order_id: int = 0):
    """查询待检库存视图。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_wip_overview(
        work_order_id=work_order_id if work_order_id else None,
    )
    return JSONResponse({"code": 0, "data": rows})


@router.get("/defects/json")
def defect_logs_json(request: Request, work_order_id: int = 0):
    """查询不良品记录。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_defect_logs(
        work_order_id=work_order_id if work_order_id else None,
    )
    return JSONResponse({"code": 0, "data": rows})
