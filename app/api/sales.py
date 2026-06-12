"""
app/api/sales.py
业务部路由
  - api_router:  /api/*  (无前缀，直接挂根)
  - router:      /sales/* (页面路由)
"""
from fastapi import APIRouter, Form, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from urllib.parse import quote
import psycopg2
from psycopg2.extras import RealDictCursor
import re
import os
import io
import openpyxl

# 零件实物图目录（相对于 static/uploads/part_images/）
_PART_IMG_BASE = os.path.join("static", "uploads", "part_images")

def _get_image_url(customer_name: str, part_number: str) -> str | None:
    """根据客户名和零件号，查找已导出的实物图 URL（Windows 中文路径兼容）。

    支持图片共享：子件（如 A00125983-04）无独立图片时，
    自动回溯查找其父件（如 A00125983-03）的图片。
    """
    if not customer_name or not part_number:
        return None

    def _find_in_dir(cname, pname):
        part_dir = os.path.join(_PART_IMG_BASE, cname, pname)
        try:
            files = os.listdir(part_dir)
        except OSError:
            return None
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                encoded_cust = quote(cname, safe='')
                encoded_part = quote(pname, safe='')
                return f"/static/uploads/part_images/{encoded_cust}/{encoded_part}/{encoded_part}{ext}"
        return None

    # 1. 直接查找当前零件
    url = _find_in_dir(customer_name, part_number)
    if url:
        return url

    # 2. 共享图片：去掉常见后缀回溯父件
    #    A00125983-4（喷涂）→ A00125983-3（喷涂）→ A00125983-3
    #    A00125983-04 → A00125983-03 → A00125983-03
    parent = part_number
    for _ in range(3):
        # 去掉末尾的（喷涂）或类似后缀
        parent = re.sub(r'（[^）]*）\s*$', '', parent).strip()
        # 去掉末尾一位（处理 A00125983-04 → A00125983-0 → A00125983）
        parent = re.sub(r'-\d+$', lambda m: '-' + str(int(m.group()[1:]) // 10), parent) if re.search(r'-\d+$', parent) else parent
        if parent == part_number:
            break
        url = _find_in_dir(customer_name, parent)
        if url:
            return url

    return None
import uuid
import json
from datetime import datetime, date
from decimal import Decimal
from app.core.auth import get_current_user
from app.core.templates import templates
from app.models.schemas import PartCreateRequest, CalcPricingBody, QuoteCreateBody
from app.services.db_service import (
    create_part_with_pricing,
    create_part_with_mold_and_pricing,
    create_quote,
    calc_part_pricing,
    get_part_pricing_summary,
    get_all_parts_for_pricing_select,
    get_parts_for_pricing_list,
    get_part_history_price,
    upsert_material_base_price,
    update_part_manual_override,
    update_part_sample_judgment,
    unbind_reference_part,
    confirm_nomination,
    set_part_pending_nomination,
    get_part_nomination_info,
    get_all_urgent_parts,
    set_part_pricing_mode,
    update_part_twp,
    get_dict_items,
    add_dict_item,
    delete_dict_item,
    get_material_base_prices_for_select,
    delete_material_base_price,
    get_parts_using_material,
    sync_material_price_to_parts,
    get_all_materials,
    get_all_treatments,
    upsert_treatment,
    delete_treatment,
    get_quote_by_id,
    get_quotes_by_part,
    get_latest_quote_by_part,
    get_quote_detail_for_edit,
    update_quote,
    submit_quote_to_boss,
    approve_quote,
    reject_quote,
    get_pending_boss_quotes,
    boss_update_quote,
    delete_quote,
    delete_part_by_id,
    reopen_quote_as_new,
    get_part_inventory_summary,
    get_finished_inventory,
    upsert_finished_inventory,
    get_remnant_inventory,
    upsert_remnant_inventory,
    get_finished_inventory_list,
    get_remnant_inventory_list,
    adjust_finished_inventory,
    adjust_remnant_inventory,
    get_all_customers,
    get_parts_with_die_link,
    get_part_by_id,
    get_all_tooling_customers,
    DB_CONFIG,
)

# ── API 路由（无前缀，路径如 /api/part/{id}）─────────────────
api_router = APIRouter(prefix="", tags=["sales-api"])

# ── 页面路由（/sales 前缀）───────────────────────────────────
router = APIRouter(prefix="/sales", tags=["sales"])

# ── 老板页面路由（无前缀，/boss/*）──────────────────────────
boss_router = APIRouter(tags=["boss"])


# ═══════════════════════════════════════════════════════════════════
#  API 接口
# ═══════════════════════════════════════════════════════════════════


@api_router.post("/api/parts/create")
def api_create_part(request: Request, body: PartCreateRequest):
    """V12 双表事务：零件 + 模具 + 报价 单次原子写入。

    替换旧的 POST /sales/parts/new Form 提交。
    所有字段名与前端 part_create.html 的 name= 属性严格对齐。
    """
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse(
            jsonable_encoder({"code": 403, "message": "权限不足", "data": None}),
            status_code=403)

    try:
        is_independent = body.pricing_mode == "independent"
        part_id = create_part_with_mold_and_pricing(
            part_number=body.part_number,
            internal_name=body.internal_name,
            remark=body.remark,
            material_name=body.material_name,
            pricing_mode=body.pricing_mode,
            referenced_part_id=body.referenced_part_id,
            thickness=body.thickness if is_independent else None,
            width=body.width if is_independent else None,
            press_stroke=body.press_stroke if is_independent else None,
            cavity_count=body.cavity_count if is_independent else 1,
            material_utilization=body.material_utilization if is_independent else 100.0,
            machine_type=body.machine_type,
            press_tonnage=body.press_tonnage,
            stamping_fee=body.stamping_fee,
            surface_fee=body.surface_fee,
            treatment_fee=body.treatment_fee,
            profit_margin=body.profit_margin,
            final_price_override=body.final_price_override,
            customer_id=body.customer_id,
            alias_part_number=body.alias_part_number,
            operator_id=user["id"],
            drawing_file_path=body.drawing_file_path,
        )
        return JSONResponse(jsonable_encoder({
            "code": 0,
            "message": "创建成功",
            "data": {"part_id": part_id, "redirect": "/sales/parts/pricing"},
        }))
    except ValueError as e:
        return JSONResponse(
            jsonable_encoder({"code": 1, "message": str(e), "data": None}),
            status_code=400)
    except Exception:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            jsonable_encoder({"code": 2, "message": "服务器内部错误，请联系管理员", "data": None}),
            status_code=500)


@api_router.get("/api/part/{part_id}")
def get_part_detail(request: Request, part_id: int):
    """返回零件详情（含 part + quote + calc + history），供侧边抽屉 AJAX 渲染"""
    user = get_current_user(request)
    if not user:
        return JSONResponse(jsonable_encoder({"code": 401, "message": "未登录", "data": None}), status_code=401)
    if user["role_level"] < 4:
        return JSONResponse(jsonable_encoder({"code": 403, "message": "权限不足", "data": None}), status_code=403)
    data = get_part_pricing_summary(part_id)
    if not data:
        return JSONResponse(jsonable_encoder({"code": 404, "message": "零件不存在", "data": None}), status_code=404)
    # 参考件历史单价（从 APPROVED 报价单获取）
    ref_price = None
    quote = data.get('quote', {})
    ref_part_id = quote.get('pricing_mode') == 'reference'
    # 未来可通过 referenced_part_id 字段获取参考件历史价
    return JSONResponse(jsonable_encoder({
        "code": 200,
        "message": "success",
        "data": data,
    }))


class PartModeBody(BaseModel):
    pricing_mode: str          # 'Associated' | 'Independent'
    referenced_part_id: int | None = None


@api_router.post("/api/part/{part_id}/pricing-mode")
def set_pricing_mode(request: Request, part_id: int, body: PartModeBody):
    """设置零件的报价模式"""
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse(jsonable_encoder({"code": 403, "message": "权限不足", "data": None}), status_code=403)
    try:
        set_part_pricing_mode(part_id, body.pricing_mode,
                             body.referenced_part_id, user["id"])
        return JSONResponse(jsonable_encoder({
            "code": 200,
            "message": "success",
            "data": {"pricing_mode": body.pricing_mode}
        }))
    except Exception as e:
        return JSONResponse(jsonable_encoder({"code": 400, "message": str(e), "data": None}), status_code=400)


class PartOverrideBody(BaseModel):
    override_fields: list = []
    gross_weight: float | None = None
    material_net_cost_override: float | None = None
    final_price_override: float | None = None
    _twp: dict | None = None   # {"thickness": float, "width": float, "press_stroke": float}


@api_router.post("/api/part/{part_id}/override")
def part_override_price(request: Request, part_id: int,
                          body: PartOverrideBody = None):
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse(jsonable_encoder({"code": 403, "message": "权限不足", "data": None}), status_code=403)
    try:
        # 处理 T/W/P 快速设置（单独 SQL，不走 override）
        if body and body._twp:
            twp = body._twp
            update_part_twp(
                part_id,
                thickness=twp.get("thickness"),
                width=twp.get("width"),
                press_stroke=twp.get("press_stroke"),
                operator_id=user["id"],
            )
        else:
            update_part_manual_override(
                part_id,
                override_fields=body.override_fields if body else [],
                gross_weight=body.gross_weight if body else None,
                material_net_cost_override=body.material_net_cost_override if body else None,
                final_price_override=body.final_price_override if body else None,
                operator_id=user["id"],
            )
        return JSONResponse(jsonable_encoder({"code": 200, "message": "success", "data": None}))
    except Exception as e:
        return JSONResponse(jsonable_encoder({"code": 400, "message": str(e), "data": None}), status_code=400)


@api_router.post("/api/part/{part_id}/sample-judgment")
def part_sample_judgment(request: Request, part_id: int,
                         status: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse(jsonable_encoder({"code": 401, "message": "未登录", "data": None}), status_code=401)
    try:
        update_part_sample_judgment(part_id, status, user["id"])
        return JSONResponse(jsonable_encoder({"code": 200, "message": "success", "data": None}))
    except Exception as e:
        return JSONResponse(jsonable_encoder({"code": 400, "message": str(e), "data": None}), status_code=400)


@api_router.post("/api/part/{part_id}/unbind")
def part_unbind(request: Request, part_id: int):
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse(jsonable_encoder({"code": 403, "message": "权限不足", "data": None}), status_code=403)
    try:
        unbind_reference_part(part_id)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "success", "data": None}))
    except Exception as e:
        return JSONResponse(jsonable_encoder({"code": 400, "message": str(e), "data": None}), status_code=400)


@api_router.get("/api/customers")
def api_customers_list(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    rows = get_all_tooling_customers()
    return JSONResponse({"code": 200, "data": [{"id": r["id"], "name": r["name"]} for r in rows]})


class CustomerBody(BaseModel):
    name: str


@api_router.post("/api/customers")
def api_customer_create(request: Request, body: CustomerBody):
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    import psycopg2
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tooling_customers (name, created_at) VALUES (%s, NOW()) RETURNING id", (body.name.strip(),))
            new_id = cur.fetchone()[0]
        conn.commit()
    return JSONResponse({"code": 0, "data": {"id": new_id, "name": body.name.strip()}})


@api_router.put("/api/customers/{cid}")
def api_customer_update(request: Request, cid: int, body: CustomerBody):
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    import psycopg2
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE tooling_customers SET name=%s WHERE id=%s", (body.name.strip(), cid))
        conn.commit()
    return JSONResponse({"code": 0, "message": "已更新"})


@api_router.delete("/api/customers/{cid}")
def api_customer_delete(request: Request, cid: int):
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    import psycopg2
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 检查是否有零件价格数据（parts 表或 quotes 表有关联）
            cur.execute("""
                SELECT COUNT(*) FROM parts WHERE customer_id = %s;
            """, (cid,))
            part_count = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM quotes WHERE customer_id = %s;
            """, (cid,))
            quote_count = cur.fetchone()[0]

            if part_count > 0 or quote_count > 0:
                return JSONResponse({
                    "code": 400,
                    "message": f"无法删除：该客户下有 {part_count} 个零件和 {quote_count} 张报价单，请先清理关联数据"
                }, status_code=400)

            cur.execute("DELETE FROM tooling_customers WHERE id=%s", (cid,))
        conn.commit()
    return JSONResponse({"code": 0, "message": "已删除"})


_DRAWING_BASE_DIR = os.path.join("static", "uploads", "drawings")


def _get_drawing_subdir(part_id: int) -> str:
    """根据零件 ID 获取图纸存放子目录。
    有客户 → 客户名/零件名/零件号/drawings
    无客户 → _unassigned/{part_id}/drawings
    """
    import re
    def _safe(s):
        return re.sub(r'[\\/:*?"<>|]', '_', (s or '').strip())
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tc.name, p.internal_name, p.part_number
                    FROM parts p
                    LEFT JOIN tooling_customers tc ON p.customer_id = tc.id
                    WHERE p.id = %s
                """, (part_id,))
                row = cur.fetchone()
                if not row:
                    return f"_unassigned/{part_id}/drawings"
                customer_name, part_name, part_number = row
                if not customer_name:
                    return f"_unassigned/{part_id}/drawings"
                segs = [_safe(customer_name), _safe(part_name or ''), _safe(part_number or str(part_id))]
                return '/'.join(s for s in segs if s) + "/drawings"
    except Exception:
        return f"_unassigned/{part_id}/drawings"


def _save_drawing_file(file_obj: UploadFile, subdir: str) -> str:
    """将文件保存到 _DRAWING_BASE_DIR/subdir/，返回 /static/uploads/drawings/subdir/文件名。"""
    allowed = {'.pdf', '.dwg', '.dxf', '.png', '.jpg', '.jpeg'}
    ext = os.path.splitext(file_obj.filename or '')[1].lower()
    if ext not in allowed:
        raise ValueError(f"不支持的文件格式: {ext}")
    save_dir = os.path.join(_DRAWING_BASE_DIR, subdir)
    os.makedirs(save_dir, exist_ok=True)
    save_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(save_dir, save_name)
    content = file_obj.file.read()
    if len(content) > 20 * 1024 * 1024:
        raise ValueError("文件超过 20MB 限制")
    with open(save_path, 'wb') as f:
        f.write(content)
    return f"/static/uploads/drawings/{subdir}/{save_name}"


@api_router.post("/api/parts/drawing-upload")
async def api_drawing_upload(request: Request, file: UploadFile = File(...), part_id: int = Form(...)):
    """上传业务图纸文件，按 客户名/零件名/零件号/drawings 分类存放。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    try:
        subdir = _get_drawing_subdir(part_id)
        url_path = _save_drawing_file(file, subdir)
        return JSONResponse({"code": 0, "message": "上传成功", "data": {"path": url_path}})
    except ValueError as e:
        return JSONResponse({"code": 1, "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"code": 1, "message": f"上传失败: {e}"}, status_code=500)


# CalcPricingBody 和 QuoteCreateBody 已迁移至 app/models/schemas.py
class QuoteUpdateBody(BaseModel):
    """更新报价单参数"""
    annual_usage: int | None = None
    pricing_mode: str | None = None
    thickness: float | None = None
    width: float | None = None
    press_stroke: float | None = None
    cavity_count: int | None = None
    scrap_rate: float | None = None
    gross_weight: float | None = None
    material_net_cost: float | None = None
    material_name: str | None = None
    snapshot_mat_name: str | None = None
    snapshot_mat_price: float | None = None
    snapshot_density: float | None = None
    snapshot_scrap_price: float | None = None
    final_price: float | None = None
    stamping_fee: float | None = None
    inspection_fee: float | None = None
    packaging_fee: float | None = None
    surface_fee: float | None = None
    mold_cost: float | None = None
    treatment_fee: float | None = None
    profit_margin: float | None = None
    final_price_override: float | None = None
    unit_price_override: float | None = None
    material_cost_override: float | None = None
    override_fields: list[str] | None = None
    nomination_status: str | None = None
    nomination_attachment: str | None = None
    machine_type: str | None = None
    press_tonnage: int | None = None
    material_utilization: float | None = None
    annual_avg: float | None = None
    lifecycle_years: float | None = None
    customer_id: int | None = None
    mold_discount_mode: str | None = None
    mold_discount_rate: float | None = None
    treatment_items: list | None = None


@api_router.post("/api/calc-pricing")
def calc_pricing(request: Request, body: CalcPricingBody = None):
    """白盒报价核算（JSON body），Path B 实时核算调用（无需登录）"""
    import logging
    logger2 = logging.getLogger(__name__)
    logger2.debug("[API /api/calc-pricing] received body=%s", body)
    try:
        result = calc_part_pricing(
            thickness=body.thickness if body else 0,
            width=body.width if body else 0,
            press_stroke=body.press_stroke if body else 0,
            material_name=body.material_name if body else "",
            cavity_count=body.cavity_count if body else 1,
            scrap_rate=body.scrap_rate if body else 0.10,
            gross_weight_g=body.gross_weight_g,
            net_weight_g=body.net_weight_g,
            scrap_weight_g=body.scrap_weight_g,
            material_utilization=body.material_utilization if body else 100.0,
            stamping_fee=body.stamping_fee if body else 0,
            inspection_fee=body.inspection_fee if body else 0,
            packaging_fee=body.packaging_fee if body else 0,
            surface_fee=body.surface_fee if body else 0,
            treatment_fee=body.treatment_fee if body else 0,
            mold_cost=body.mold_cost if body else 0,
            profit_margin=body.profit_margin if body else 0,
            override_final_price=body.override_final_price if body else None,
            machine_type=body.machine_type if body else None,
        )
        logger2.debug("[API /api/calc-pricing] result=%s", result)

        # 业务错误（材料未注册、参数不完整）→ 返回 HTTP 422，不再用 200+soft-error
        if result.get('error'):
            return JSONResponse(
                jsonable_encoder({"code": 422, "message": result['error'], "data": None}),
                status_code=422
            )

        return JSONResponse(jsonable_encoder({"code": 200, "message": "success", "data": result}))
    except Exception as e:
        import traceback
        logger2.error("[API /api/calc-pricing] EXCEPTION: %s\n%s", e, traceback.format_exc())
        return JSONResponse(jsonable_encoder({"code": 500, "message": str(e), "data": None}), status_code=500)


# ═══════════════════════════════════════════════════════════════════
#  材料快捷操作 API（供零件创建页新建材料弹窗调用）
# ═══════════════════════════════════════════════════════════════════

@api_router.get("/api/materials")
def list_materials(request: Request):
    """返回活跃材料列表（来自 material_base_prices 表），供前端下拉框渲染"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    try:
        rows = get_material_base_prices_for_select()
        return JSONResponse(jsonable_encoder({"code": 200, "data": rows}))
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


class MaterialQuickCreateBody(BaseModel):
    material_name: str
    default_density: float
    default_price: float
    scrap_price: float | None = None


class MaterialBody(BaseModel):
    material_name: str
    default_density: float
    default_price: float
    scrap_price: float | None = None


@api_router.put("/api/materials/{material_name}")
def update_material_base_price(request: Request, material_name: str, body: MaterialBody):
    """
    更新指定材料的基准价格（PUT · JSON body）。
    返回：{code:200, data:{id, material_name, default_density, default_price, scrap_price}}
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        upsert_material_base_price(
            material_name=body.material_name,
            default_density=body.default_density,
            default_price=body.default_price,
            scrap_price=body.scrap_price,
            operator_id=user["id"],
        )
        all_mats = get_material_base_prices_for_select()
        updated = next((m for m in all_mats if m['material_name'] == body.material_name), None)
        return JSONResponse(jsonable_encoder({
            "code": 200,
            "message": "success",
            "data": {
                "id": updated['id'] if updated else 0,
                "material_name": body.material_name,
                "default_density": body.default_density,
                "default_price": body.default_price,
                "scrap_price": body.scrap_price,
            }
        }))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.post("/api/materials")
def quick_create_material(request: Request, body: MaterialQuickCreateBody):
    """
    快捷新建材料（JSON body），part_create.html JS 调用。
    返回：{code:200, data:{id, material_name, default_density, default_price, scrap_price}}
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        result = upsert_material_base_price(
            material_name=body.material_name,
            default_density=body.default_density,
            default_price=body.default_price,
            scrap_price=body.scrap_price,
        )
        all_mats = get_material_base_prices_for_select()
        created = next((m for m in all_mats if m['material_name'] == body.material_name), None)
        return JSONResponse(jsonable_encoder({
            "code": 200,
            "message": "success",
            "data": {
                "id": created['id'] if created else 0,
                "material_name": body.material_name,
                "default_density": body.default_density,
                "default_price": body.default_price,
                "scrap_price": body.scrap_price,
            }
        }))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.post("/api/materials/prices")
def upsert_material_price(request: Request,
                          material_name: str = Form(...),
                          default_density: float = Form(...),
                          default_price: float = Form(...),
                          scrap_price: float | None = Form(None),
                          sync_draft: str = Form("false")):
    """
    新增或更新材料基准价格（material_base_prices 表）。
    前端 POST FormData，响应 {ok, action, draft_parts, old_price, new_price}
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        result = upsert_material_base_price(
            material_name=material_name,
            default_density=default_density,
            default_price=default_price,
            scrap_price=scrap_price if scrap_price is not None else None,
            operator_id=user["id"],
        )
        # 前端通过 d.ok / d.action 判断是否有 Draft 零件需要同步
        return JSONResponse(jsonable_encoder({"code": 200, **result}))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.get("/api/materials/prices/{material_name}/parts")
def get_material_draft_parts(request: Request, material_name: str):
    """返回使用指定材料且状态为 Draft 的零件列表，供同步弹窗展示"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    try:
        rows = get_parts_using_material(material_name)
        return JSONResponse(jsonable_encoder({"code": 200, "data": rows}))
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/materials/prices/sync-draft")
def sync_draft_by_material(request: Request,
                           material_name: str = Form(...)):
    """将指定材料的最新基准价格同步到所有 Draft 零件"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        result = sync_material_price_to_parts(material_name)
        mat = get_material_base_prices_for_select()
        new_price = next((m['default_price'] for m in mat if m['material_name'] == material_name), None)
        return JSONResponse(jsonable_encoder({
            "code": 200,
            "ok": True,
            "affected_count": result.get("affected_count", 0),
            "new_price": new_price,
        }))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.delete("/api/materials/prices/{material_name}")
def delete_material_price(request: Request, material_name: str):
    """删除材料基准价格（被零件引用时拒绝）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok, msg = delete_material_base_price(material_name)
        if not ok:
            return JSONResponse({"code": 400, "ok": False, "detail": msg}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "ok": True, "message": msg}))
    except Exception as e:
        return JSONResponse({"code": 400, "ok": False, "detail": str(e)}, status_code=400)


# ═══════════════════════════════════════════════════════════════════
#  零件名称数据字典 API
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# 表面处理字典 CRUD  /api/dict/treatments
# 注意：这些路由必须定义在泛型 /api/dict/{dict_type} 之前！
# FastAPI 按定义顺序匹配路由，泛型路由 {dict_type} 会拦截 treatments。
# ═══════════════════════════════════════════════════════════════════════════════

class TreatmentBody(BaseModel):
    name: str
    calc_mode: str  # 'manual' | 'net_weight'
    rate: float
    unit: str = "元/件"


@api_router.get("/api/dict/treatments")
def list_treatments():
    """返回所有表面处理方式列表（无需登录）"""
    try:
        rows = get_all_treatments()
        return JSONResponse({"code": 200, "data": rows})
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/dict/treatments")
def create_or_update_treatment(request: Request, body: TreatmentBody):
    """新增/更新处理方式（无需登录）"""
    if body.calc_mode not in ("manual", "net_weight"):
        return JSONResponse({"code": 400, "message": "calc_mode must be manual or net_weight"}, status_code=400)
    try:
        result = upsert_treatment(body.name, body.calc_mode, body.rate, body.unit)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "success", "data": result}))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.delete("/api/dict/treatments/{treatment_id}")
def remove_treatment(treatment_id: int):
    """删除处理方式（无需登录）"""
    try:
        ok = delete_treatment(treatment_id)
        if not ok:
            return JSONResponse({"code": 404, "message": "未找到该处理方式"}, status_code=404)
        return JSONResponse({"code": 200, "message": "已删除"})
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


# ═══════════════════════════════════════════════════════════════════════════════
# 通用字典路由（必须在 treatments 路由之后，否则被 {dict_type} 泛型拦截）
# ═══════════════════════════════════════════════════════════════════════════════

class DictItemBody(BaseModel):
    dict_type:  str
    dict_value: str


@api_router.get("/api/dict/{dict_type}")
def get_dict(request: Request, dict_type: str):
    """返回指定类型的字典项列表"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    try:
        items = get_dict_items(dict_type)
        return JSONResponse(jsonable_encoder({"code": 200, "data": items}))
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/dict")
def create_dict(request: Request, body: DictItemBody):
    """新增字典项"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    if not body.dict_value or not body.dict_value.strip():
        return JSONResponse({"code": 400, "message": "字典值不能为空"}, status_code=400)
    try:
        item = add_dict_item(body.dict_type, body.dict_value.strip())
        return JSONResponse(jsonable_encoder({"code": 200, "message": "添加成功", "data": item}))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.delete("/api/dict/{dict_type}/{item_id}")
def remove_dict(request: Request, dict_type: str, item_id: int):
    """删除（软删除）字典项"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok = delete_dict_item(dict_type, item_id)
        if not ok:
            return JSONResponse({"code": 404, "message": "未找到该字典项"}, status_code=404)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "已删除"}))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@router.get("/quotes/{quote_id}/edit")
def quote_edit_page(request: Request, quote_id: int):
    """报价单编辑页面 — 从零件报价列表点击非 APPROVED 卡片进入"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    # 取报价单详情（含 part + quote + calc）
    quote_data = get_quote_detail_for_edit(quote_id)
    if not quote_data:
        raise HTTPException(status_code=404, detail="报价单不存在")
    materials = get_material_base_prices_for_select()
    ref_parts = get_all_parts_for_pricing_select()
    part_name_list = get_dict_items("part_name")
    return templates.TemplateResponse("sales/quote_edit.html", {
        "request": request,
        "user": user,
        "quote_data": quote_data,
        "materials": materials,
        "ref_parts": ref_parts,
        "part_name_list": part_name_list,
    })


@router.get("/parts/new")
def sales_part_new_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    # 材料列表：取 material_base_prices 表（含 default_density/default_price/scrap_price）
    materials = get_material_base_prices_for_select()
    # 参考件列表（已有 T/W/P 参数的件，供路径 A 关联）
    ref_parts = get_all_parts_for_pricing_select()
    # 零件名称数据字典（动态渲染 datalist）
    part_name_list = get_dict_items("part_name")
    return templates.TemplateResponse("sales/part_create.html", {
        "request": request,
        "user": user,
        "materials": materials,
        "ref_parts": ref_parts,
        "part_name_list": part_name_list,
    })


@router.post("/parts/new")
def sales_part_new(request: Request,
                   part_number: str = Form(...),
                   internal_name: str = Form(""),
                   remark: str = Form(""),
                   surface_type: str = Form(""),
                   coating_color: str = Form(""),
                   surface_area: float = Form(0),
                   thickness: float = Form(0),
                   press_tonnage: float = Form(0),
                   customer_id: int = Form(None),
                   customer_part_number: str = Form(""),
                   reference_part_id: int = Form(None),
                   pricing_track: str = Form("independent"),
                   density: float = Form(None),
                   material_price: float = Form(None),
                   scrap_price: float = Form(None),
                   manual_total_price: float = Form(None),
                   remarks: str = Form(""),
                   # V12 新增字段（路径 B）
                   width: float = Form(None),
                   press_stroke: float = Form(None),
                   cavity_count: int = Form(1),
                   material_utilization: float = Form(100.0),
                   machine_type: str = Form(None)):
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    try:
        part_id = create_part_with_pricing(
            part_number=part_number,
            internal_name=internal_name,
            remark=remark,
            material_name="",
            pricing_mode=pricing_track,
            referenced_part_id=reference_part_id,
            thickness=thickness if pricing_track == "independent" else None,
            width=width if pricing_track == "independent" else None,
            press_stroke=press_stroke if pricing_track == "independent" else None,
            cavity_count=cavity_count if pricing_track == "independent" else 1,
            stamping_fee=None,
            surface_fee=None,
            profit_margin=None,
            customer_id=customer_id,
            alias_part_number=customer_part_number,
            operator_id=user["id"],
            material_utilization=material_utilization if pricing_track == "independent" else 100.0,
            machine_type=machine_type,
        )
        return RedirectResponse(f"/sales/detail/{part_id}", 303)
    except Exception as e:
        import traceback; traceback.print_exc()
        return HTMLResponse(
            f"<html><body><script>alert('创建失败: {str(e)}'); history.back();</script></body></html>",
            status_code=400)


@router.get("/parts")
def sales_parts_list_page(request: Request, status_filter: str = ""):
    """
    零件报价列表页（支持 status_filter 过滤）。
    用于：
    - 老板看板点击【立即处理】→ /sales/parts?status_filter=PENDING_BOSS
    - 业务视角浏览全部零件 → /sales/parts
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 1:
        raise HTTPException(status_code=403, detail="权限不足")
    parts = get_parts_for_pricing_list(status_filter=status_filter.upper() if status_filter else "")
    return templates.TemplateResponse("sales/part_pricing.html", {
        "request": request, "user": user, "parts": parts,
        "status_filter": status_filter.upper() if status_filter else "",
    })


# ── 零件表（仅展示，供全员查询）───────────────────────────────────────────────

@router.get("/parts")
def sales_part_list_page(request: Request):
    """零件表页面 — 全员可访问，仅展示零件基础信息"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    from app.services.db_service import get_parts_for_list_view
    parts = get_parts_for_list_view()
    return templates.TemplateResponse("sales/part_list.html", {
        "request": request, "user": user, "parts": parts,
    })


@router.get("/parts/pricing")
def sales_part_pricing_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 1:
        raise HTTPException(status_code=403, detail="权限不足")
    parts = get_parts_for_pricing_list()
    return templates.TemplateResponse("sales/part_pricing.html", {
        "request": request, "user": user, "parts": parts,
    })


@router.get("/parts/pricing/{part_id}")
def sales_part_pricing_detail(request: Request, part_id: int):
    """零件报价详情页（SSR 模式）"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    data = get_part_pricing_summary(part_id)
    if not data:
        raise HTTPException(status_code=404, detail="零件不存在")
    return templates.TemplateResponse("sales/part_pricing.html", {
        "request": request, "user": user,
        "data": data,
    })


@router.post("/parts/{part_id}/nominate")
def sales_nominate(request: Request, part_id: int,
                   attachment_url: str = Form(""),
                   mold_number: str = Form(""),
                   mold_type: str = Form(""),
                   press_tonnage: str = Form(""),
                   ppap_no: str = Form("")):
    """
    定点终裁确认（从报价单 quotes 维度定点）。
    confirmed_price 参数已从签名移除——定点价格来自报价单的 final_price_override。
    定点后模具基础信息（mold_number/mold_type/press_tonnage/ppap_no）同步写入 parts 表。
    """
    user = get_current_user(request)
    if not user or user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="权限不足")
    try:
        result = confirm_nomination(
            part_id=part_id,
            operator_id=user["id"],
            attachment_filenames=[attachment_url] if attachment_url else None,
            mold_number=mold_number or None,
            mold_type=mold_type or None,
            press_tonnage=press_tonnage or None,
            ppap_no=ppap_no or None,
        )
        return RedirectResponse(f"/sales/detail/{part_id}", 303)
    except Exception as e:
        return HTMLResponse(
            f"<html><body><script>alert('{str(e)}'); history.back();</script></body></html>",
            status_code=400)


# =============================================================================
#  报价单 (quotes) CRUD API
# =============================================================================

@api_router.get("/api/part/{part_id}/quotes")
def get_part_quotes(request: Request, part_id: int):
    """返回零件的全部报价单历史"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    rows = get_quotes_by_part(part_id)
    return JSONResponse(jsonable_encoder({"code": 200, "data": rows}))


@api_router.get("/api/quote/{quote_id}")
def get_quote(request: Request, quote_id: int):
    """返回单条报价单详情"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    row = get_quote_by_id(quote_id)
    if not row:
        return JSONResponse({"code": 404, "message": "报价单不存在"}, status_code=404)
    return JSONResponse(jsonable_encoder({"code": 200, "data": row}))


@api_router.put("/api/quote/{quote_id}")
def update_quote_legacy_route(request: Request, quote_id: int, body: QuoteUpdateBody):
    """更新报价单字段（仅 DRAFT / REJECTED 状态允许）- 兼容旧路径"""
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok = update_quote(
            quote_id=quote_id,
            annual_usage=body.annual_usage,
            pricing_mode=body.pricing_mode,
            thickness=body.thickness,
            width=body.width,
            press_stroke=body.press_stroke,
            cavity_count=body.cavity_count,
            scrap_rate=body.scrap_rate,
            gross_weight=body.gross_weight,
            material_net_cost=body.material_net_cost,
            material_name=body.material_name,
            snapshot_mat_name=body.snapshot_mat_name,
            snapshot_mat_price=body.snapshot_mat_price,
            snapshot_density=body.snapshot_density,
            snapshot_scrap_price=body.snapshot_scrap_price,
            final_price=body.final_price,
            stamping_fee=body.stamping_fee,
            inspection_fee=body.inspection_fee,
            packaging_fee=body.packaging_fee,
            surface_fee=body.surface_fee,
            mold_cost=body.mold_cost,
            treatment_fee=body.treatment_fee,
            profit_margin=body.profit_margin,
            final_price_override=body.final_price_override,
            unit_price_override=body.unit_price_override,
            material_cost_override=body.material_cost_override,
            override_fields=body.override_fields,
            nomination_status=body.nomination_status,
            nomination_attachment=body.nomination_attachment,
            machine_type=body.machine_type,
            press_tonnage=body.press_tonnage,
            material_utilization=body.material_utilization,
        )
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单不存在或状态不允许编辑"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "success"}))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.post("/api/part/{part_id}/quote")
def create_quote_route(request: Request, part_id: int):
    """
    为零件新建一条报价单。
    从最新 APPROVED 报价单继承参数，或基于零件主档 T/W/P 创建空白报价单。
    """
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        # 取最新 APPROVED 报价单作为模板
        latest = get_latest_quote_by_part(part_id)
        if latest and latest.get('approval_status') == 'APPROVED':
            new_id = create_quote(
                part_id=part_id,
                pricing_mode=latest.get('pricing_mode') or 'independent',
                thickness=latest.get('thickness'),
                width=latest.get('width'),
                press_stroke=latest.get('press_stroke'),
                cavity_count=latest.get('cavity_count') or 1,
                scrap_rate=latest.get('scrap_rate') or 0.10,
                stamping_fee=latest.get('stamping_fee'),
                surface_fee=latest.get('surface_fee'),
                treatment_fee=latest.get('treatment_fee'),
                profit_margin=latest.get('profit_margin'),
                approval_status='WAITING_FOR_TECH',
                operator_id=user['id'],
            )
        else:
            # 无 APPROVED 报价单，取 parts 主档 T/W/P（parts 表无 T/W/P，从 dies 表补取）
            part = get_part_by_id(part_id)
            if not part:
                return JSONResponse({"code": 404, "message": "零件不存在"}, status_code=404)

            # 从 dies 表取 T/W/P（parts 表本身无此字段）
            twp = {'thickness': None, 'width': None, 'press_stroke': None, 'cavity_count': 1}
            with psycopg2.connect(**DB_CONFIG) as conn_twp:
                with conn_twp.cursor() as cur_twp:
                    cur_twp.execute("""
                        SELECT thickness_mm, width_mm, pitch_mm, cavity_count
                        FROM dies
                        WHERE part_id = %s
                          AND lifecycle_status != 'SCRAPPED'
                        LIMIT 1;
                    """, (part_id,))
                    row_twp = cur_twp.fetchone()
                    if row_twp:
                        twp['thickness']   = float(row_twp[0]) if row_twp[0] else None
                        twp['width']       = float(row_twp[1]) if row_twp[1] else None
                        twp['press_stroke'] = float(row_twp[2]) if row_twp[2] else None
                        twp['cavity_count'] = int(row_twp[3]) if row_twp[3] else 1

            new_id = create_quote(
                part_id=part_id,
                pricing_mode='independent',
                thickness=twp['thickness'],
                width=twp['width'],
                press_stroke=twp['press_stroke'],
                cavity_count=twp['cavity_count'],
                approval_status='WAITING_FOR_TECH',
                operator_id=user['id'],
            )
        return JSONResponse(jsonable_encoder({
            "code": 200,
            "message": "success",
            "data": {"quote_id": new_id},
        }))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.post("/api/quote/{quote_id}/submit")
def submit_quote_route(request: Request, quote_id: int):
    """提交报价单至 PENDING_BOSS"""
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok = submit_quote_to_boss(quote_id, operator_id=user["id"])
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单状态不允许提交（仅 DRAFT/REJECTED 可提交）"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "success"}))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.post("/api/quote/{quote_id}/approve")
def approve_quote_route(request: Request, quote_id: int):
    """审核通过报价单（老板/业务副总操作）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 9:
        return JSONResponse({"code": 403, "message": "权限不足（需 admin 权限）"}, status_code=403)
    try:
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


class RejectBody(BaseModel):
    reason: str


@api_router.post("/api/quote/{quote_id}/reject")
def reject_quote_route(request: Request, quote_id: int, body: RejectBody):
    """驳回报价单（可选择是否重新生成）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 9:
        return JSONResponse({"code": 403, "message": "权限不足（需 admin 权限）"}, status_code=403)
    try:
        ok = reject_quote(quote_id, rejection_reason=body.reason, operator_id=user["id"])
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单状态不允许驳回"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "驳回成功"}))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.post("/api/quote/{quote_id}/reopen")
def reopen_quote_route(request: Request, quote_id: int):
    """基于被驳回的报价单重新生成一条新报价单"""
    user = get_current_user(request)
    if not user or user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        new_id = reopen_quote_as_new(quote_id, operator_id=user["id"])
        return JSONResponse(jsonable_encoder({
            "code": 200,
            "message": "新报价单已创建",
            "data": {"new_quote_id": new_id},
        }))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


# ═══════════════════════════════════════════════════════════════════
#  报价工作流 API（quotes 状态机）— 复数路径，与 api_config.js 一致
# ═══════════════════════════════════════════════════════════════════

class QuoteRejectBody(BaseModel):
    reason: str = ""


@api_router.put("/api/quotes/{quote_id}")
def update_quote_route(request: Request, quote_id: int, body: QuoteUpdateBody):
    """快速修改报价单（仅 DRAFT / REJECTED 状态允许）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok = update_quote(
            quote_id=quote_id,
            annual_usage=body.annual_usage,
            pricing_mode=body.pricing_mode,
            thickness=body.thickness,
            width=body.width,
            press_stroke=body.press_stroke,
            cavity_count=body.cavity_count,
            scrap_rate=body.scrap_rate,
            gross_weight=body.gross_weight,
            material_net_cost=body.material_net_cost,
            material_name=body.material_name,
            snapshot_mat_name=body.snapshot_mat_name,
            snapshot_mat_price=body.snapshot_mat_price,
            snapshot_density=body.snapshot_density,
            snapshot_scrap_price=body.snapshot_scrap_price,
            final_price=body.final_price,
            stamping_fee=body.stamping_fee,
            inspection_fee=body.inspection_fee,
            packaging_fee=body.packaging_fee,
            surface_fee=body.surface_fee,
            mold_cost=body.mold_cost,
            treatment_fee=body.treatment_fee,
            profit_margin=body.profit_margin,
            final_price_override=body.final_price_override,
            unit_price_override=body.unit_price_override,
            material_cost_override=body.material_cost_override,
            override_fields=body.override_fields,
            nomination_status=body.nomination_status,
            nomination_attachment=body.nomination_attachment,
            machine_type=body.machine_type,
            press_tonnage=body.press_tonnage,
            material_utilization=body.material_utilization,
            annual_avg=body.annual_avg,
            lifecycle_years=body.lifecycle_years,
            customer_id=body.customer_id,
            mold_discount_mode=body.mold_discount_mode,
            mold_discount_rate=body.mold_discount_rate,
            treatment_items=body.treatment_items,
        )
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单不存在或状态不允许编辑"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "修改已保存"}))
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.put("/api/quotes/{quote_id}/recalculate")
def recalc_quote(request: Request, quote_id: int, body: CalcPricingBody = None):
    """
    重算报价单：将白盒核算结果完整写回 quotes 表。
    前端保存前调用此接口，把 material_net_cost / final_price 等快照字段全部更新。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    import logging
    logger2 = logging.getLogger(__name__)
    try:
        # 先查当前报价单状态
        quote = get_quote_by_id(quote_id)
        if not quote:
            return JSONResponse({"code": 404, "message": "报价单不存在"}, status_code=404)
        if quote.get("approval_status") not in ("DRAFT", "REJECTED", "PENDING_BOSS"):
            return JSONResponse({"code": 400, "message": "当前状态不允许修改"}, status_code=400)

        # 调用白盒核算引擎
        calc = calc_part_pricing(
            thickness=body.thickness if body else 0,
            width=body.width if body else 0,
            press_stroke=body.press_stroke if body else 0,
            material_name=body.material_name if body else "",
            cavity_count=body.cavity_count if body else 1,
            scrap_rate=body.scrap_rate if body else 0.10,
            gross_weight_g=body.gross_weight_g,
            net_weight_g=body.net_weight_g,
            scrap_weight_g=body.scrap_weight_g,
            material_utilization=body.material_utilization if body else 100.0,
            stamping_fee=body.stamping_fee if body else 0,
            inspection_fee=body.inspection_fee if body else 0,
            packaging_fee=body.packaging_fee if body else 0,
            surface_fee=body.surface_fee if body else 0,
            treatment_fee=body.treatment_fee if body else 0,
            mold_cost=body.mold_cost if body else 0,
            profit_margin=body.profit_margin if body else 0,
            override_final_price=body.override_final_price if body else None,
            override_material_cost=body.override_material_cost if body else None,
            override_unit_price=body.unit_price_override if body else None,
            machine_type=body.machine_type if body else None,
        )

        if calc.get("error"):
            return JSONResponse({"code": 422, "message": calc["error"], "data": None}, status_code=422)

        # 写回数据库
        ok = update_quote(
            quote_id=quote_id,
            gross_weight=calc.get("gross_weight"),
            material_net_cost=calc.get("material_net_cost"),
            snapshot_mat_name=body.material_name if body else "",
            snapshot_mat_price=calc.get("unit_price"),
            snapshot_density=calc.get("density"),
            snapshot_scrap_price=calc.get("scrap_price"),
            final_price=calc.get("final_price"),
            stamping_fee=calc.get("stamping_fee"),
            inspection_fee=calc.get("inspection_fee"),
            packaging_fee=calc.get("packaging_fee"),
            surface_fee=calc.get("surface_fee"),
            mold_cost=body.mold_cost if body else None,
            treatment_fee=calc.get("treatment_fee"),
            profit_margin=calc.get("profit_margin"),
            final_price_override=calc.get("final_price_override") or body.override_final_price if body else None,
            unit_price_override=calc.get("material_unit_price_override") if calc.get("material_unit_price_override") else None,
            material_cost_override=body.override_material_cost if body and body.override_material_cost is not None else calc.get("material_net_cost_override"),
            override_fields=calc.get("override_flags") or [],
            material_utilization=calc.get("material_utilization"),
            thickness=body.thickness if body else None,
            width=body.width if body else None,
            press_stroke=body.press_stroke if body else None,
            cavity_count=body.cavity_count if body else None,
            scrap_rate=calc.get("scrap_rate"),
            machine_type=body.machine_type if body else None,
        )

        if not ok:
            return JSONResponse({"code": 400, "message": "更新失败"}, status_code=400)

        return JSONResponse(jsonable_encoder({"code": 200, "message": "核算结果已保存", "data": calc}))
    except Exception as e:
        import traceback
        logger2.error("[API recalc] EXCEPTION: %s\n%s", e, traceback.format_exc())
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.delete("/api/quotes/{quote_id}")
def delete_quote_route(request: Request, quote_id: int):
    """删除草稿报价单（仅 DRAFT 状态允许删除）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok = delete_quote(quote_id)
        if not ok:
            return JSONResponse({"code": 400, "message": "仅草稿状态的报价单可删除，或该单不存在"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "报价单已删除"}))
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.delete("/api/parts/{part_id}")
def delete_part_route(request: Request, part_id: int):
    """
    直接按零件 ID 强制删除（忽略报价单状态）。
    用于清理孤立的测试零件（如 APPROVED + 已软删除报价单的 TEST 零件）。
    权限：role_level >= 4（业务/技术）。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        delete_part_by_id(part_id)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "零件及关联数据已删除"}))
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/quotes/{quote_id}/submit")
def submit_quote_api(request: Request, quote_id: int):
    """提交报价单至 PENDING_BOSS（业务提交）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok = submit_quote_to_boss(quote_id, operator_id=user["id"])
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单状态不允许提交（仅草稿/已驳回可提交）"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "已提交，等待审核"}))
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/quotes/{quote_id}/approve")
def approve_quote_api(request: Request, quote_id: int):
    """老板审核通过报价单"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 9:
        return JSONResponse({"code": 403, "message": "权限不足（需 admin 权限）"}, status_code=403)
    try:
        ok = approve_quote(quote_id, operator_id=user["id"])
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单状态不允许审核（仅待审核状态可审批）"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "审核通过！"}))
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/quotes/{quote_id}/reject")
def reject_quote_api(request: Request, quote_id: int, body: QuoteRejectBody):
    """老板驳回报价单"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 9:
        return JSONResponse({"code": 403, "message": "权限不足（需 admin 权限）"}, status_code=403)
    try:
        ok = reject_quote(quote_id, rejection_reason=body.reason or "（未填写驳回原因）", operator_id=user["id"])
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单状态不允许驳回（仅待审核状态可驳回）"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "已驳回，业务员可重新修改后再次提交"}))
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════════
#  库存体系 API（v12）
# ═══════════════════════════════════════════════════════════════════

@api_router.get("/api/parts/{part_id}/inventory")
def get_inventory_summary(request: Request, part_id: int):
    """零件库存聚合查询：成品库 + 尾数库 + 合计"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    data = get_part_inventory_summary(part_id)
    if data is None:
        return JSONResponse({"code": 404, "message": "零件不存在"}, status_code=404)
    return JSONResponse(jsonable_encoder({"code": 200, "data": data}))


class FinishedInventoryBody(BaseModel):
    quantity: int
    location: str = ""


@api_router.post("/api/parts/{part_id}/finished-inventory")
def set_finished_inventory(request: Request, part_id: int, body: FinishedInventoryBody):
    """成品库入库/更新（按库位 upsert）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 3:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        row = upsert_finished_inventory(part_id, body.quantity, body.location)
        return JSONResponse(jsonable_encoder({"code": 200, "data": row}))
    except ValueError as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


class RemnantInventoryBody(BaseModel):
    quantity: int


@api_router.post("/api/parts/{part_id}/remnant-inventory")
def set_remnant_inventory(request: Request, part_id: int, body: RemnantInventoryBody):
    """尾数库入库/更新"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 3:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        row = upsert_remnant_inventory(part_id, body.quantity)
        return JSONResponse(jsonable_encoder({"code": 200, "data": row}))
    except ValueError as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


# ── 库存列表 JSON API ──────────────────────────────────────────────────────────

@api_router.get("/api/inventory/finished")
def api_finished_inventory_list(request: Request, customer: str = ""):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    rows = get_finished_inventory_list(customer_name=customer or None)
    return JSONResponse(jsonable_encoder({"code": 200, "data": rows}))


@api_router.get("/api/inventory/remnant")
def api_remnant_inventory_list(request: Request, customer: str = ""):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    rows = get_remnant_inventory_list(customer_name=customer or None)
    return JSONResponse(jsonable_encoder({"code": 200, "data": rows}))


class InventoryAdjustBody(BaseModel):
    delta: int
    location: str = ""


@api_router.post("/api/inventory/finished/{part_id}/adjust")
def api_adjust_finished(request: Request, part_id: int, body: InventoryAdjustBody):
    """成品库出入库（delta 正=入库，负=出库）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 3:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        row = adjust_finished_inventory(part_id, body.delta, body.location)
        return JSONResponse(jsonable_encoder({"code": 200, "data": row}))
    except ValueError as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/inventory/remnant/{part_id}/adjust")
def api_adjust_remnant(request: Request, part_id: int, body: InventoryAdjustBody):
    """尾数库出入库（delta 正=入库，负=出库）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 3:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        row = adjust_remnant_inventory(part_id, body.delta)
        return JSONResponse(jsonable_encoder({"code": 200, "data": row}))
    except ValueError as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


# ── 库存管理页面路由 ───────────────────────────────────────────────────────────

@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    customers = get_all_customers()
    return templates.TemplateResponse("sales/inventory.html", {
        "request": request,
        "user": user,
        "customers": customers,
    })


# ── 零件-模具关联表页面路由 ────────────────────────────────────────────────

@router.get("/parts/die-link", response_class=HTMLResponse)
def parts_die_link_page(request: Request):
    """零件-模具关联表（die-link）：一个零件 × 一个模具 = 一行，含净重/价格/订单发货统计。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    return templates.TemplateResponse("sales/part_die_link.html", {
        "request": request,
        "user": user,
    })


@api_router.get("/parts/die-link/json")
def parts_die_link_json(
        part_name: str = "",
        mold_number: str = "",
        month: str = ""):
    """零件-模具关联表数据接口。"""
    try:
        rows = get_parts_with_die_link(
            part_name=part_name,
            mold_number=mold_number,
            month=month,
        )
        return JSONResponse({"code": 200, "data": rows})
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


# =============================================================================
#  老板报价审批 (boss)
# =============================================================================

@api_router.get("/api/boss/price-cards/template")
def download_price_template(request: Request):
    """下载价格成本核算模板"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    import os
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "static", "uploads", "prices", "价格成本核算模板.xlsx"
    )
    if not os.path.exists(template_path):
        return JSONResponse({"code": 404, "message": "模板文件不存在"}, status_code=404)

    from starlette.responses import FileResponse
    return FileResponse(
        template_path,
        filename="价格成本核算模板.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@boss_router.get("/boss/price-cards")
def boss_price_cards_page(request: Request):
    """价格成本卡片 — 业务和老板可访问"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="仅业务和老板可访问")
    return templates.TemplateResponse("boss/price_cards_choose.html", {
        "request": request,
        "user": user,
    })


@boss_router.get("/boss/price-cards/{customer_id}")
def boss_price_cards_customer_page(request: Request, customer_id: int):
    """某客户的价格成本卡片列表"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="仅业务和老板可访问")

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM tooling_customers WHERE id=%s", (customer_id,))
            row = cur.fetchone()
            customer_name = row[0] if row else "未知客户"
    finally:
        conn.close()

    return templates.TemplateResponse("boss/price_cards_list.html", {
        "request": request,
        "user": user,
        "customer_id": customer_id,
        "customer_name": customer_name,
    })


@boss_router.get("/boss/price-cards/{customer_id}/detail/{price_id}")
def boss_price_card_detail_page(request: Request, customer_id: int, price_id: int):
    """价格成本卡片详情页"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="仅业务和老板可访问")

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM tooling_customers WHERE id=%s", (customer_id,))
            row = cur.fetchone()
            customer_name = row[0] if row else "未知客户"
    finally:
        conn.close()

    return templates.TemplateResponse("boss/price_card_detail.html", {
        "request": request,
        "user": user,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "price_id": price_id,
    })


@api_router.get("/api/boss/customers")
def boss_customer_list(request: Request):
    """获取所有客户列表，供价格成本卡片使用"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM tooling_customers ORDER BY name;")
            rows = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
    return JSONResponse({"code": 200, "data": rows})


class BossCustomerBody(BaseModel):
    name: str


@api_router.post("/api/boss/customers")
def boss_customer_create(request: Request, body: BossCustomerBody):
    """新增客户（业务/老板可用）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    import psycopg2
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 检查重名
            cur.execute("SELECT id FROM tooling_customers WHERE name=%s", (body.name.strip(),))
            if cur.fetchone():
                return JSONResponse({"code": 400, "message": "客户名称已存在"}, status_code=400)
            cur.execute("INSERT INTO tooling_customers (name, created_at) VALUES (%s, NOW()) RETURNING id",
                         (body.name.strip(),))
            new_id = cur.fetchone()[0]
        conn.commit()
    return JSONResponse({"code": 0, "data": {"id": new_id, "name": body.name.strip()}})


@api_router.put("/api/boss/customers/{cid}")
def boss_customer_update(request: Request, cid: int, body: BossCustomerBody):
    """更新客户名称（业务/老板可用）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    import psycopg2
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE tooling_customers SET name=%s WHERE id=%s", (body.name.strip(), cid))
        conn.commit()
    return JSONResponse({"code": 0, "message": "已更新"})


@api_router.delete("/api/boss/customers/{cid}")
def boss_customer_delete(request: Request, cid: int):
    """删除客户（业务/老板可用），有价格数据则禁止删除"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    import psycopg2
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM parts WHERE customer_id = %s", (cid,))
            part_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM quotes WHERE customer_id = %s", (cid,))
            quote_count = cur.fetchone()[0]
            if part_count > 0 or quote_count > 0:
                return JSONResponse({
                    "code": 400,
                    "message": f"无法删除：该客户下有 {part_count} 个零件和 {quote_count} 张报价单"
                }, status_code=400)
            cur.execute("DELETE FROM tooling_customers WHERE id=%s", (cid,))
        conn.commit()
    return JSONResponse({"code": 0, "message": "已删除"})


# ============================================================================
# 价格成本卡片 API
# ============================================================================

def _calc_material_cost(gross_weight, net_weight, material_unit_price, scrap_price):
    """计算材料成本（元/件）= 净重(kg) × 材料单价（元/kg）。

    scrap_price 存的是废料比率（0~1），作为参考值不参与成本计算。
    """
    if net_weight is None or material_unit_price is None:
        return None
    nw = float(net_weight or 0)
    mp = float(material_unit_price or 0)
    return round(nw * mp, 4)


def _calc_current_price(years_data, reductions_data, current_year):
    """
    计算当前价格：
    1. 取最新录入的单价
    2. 若最新录入年份 >= current_year，按录入值
    3. 否则按年降规则自动推算
    返回 (unit_price, year, source: '录入'/'年降推算')
    """
    if not years_data:
        return None, None, None
    sorted_years = sorted(years_data, key=lambda x: x['year'], reverse=True)
    latest = sorted_years[0]

    if latest['year'] >= current_year:
        return latest['unit_price'], latest['year'], '录入'

    # 按年降规则推算到 current_year
    base_price = latest['unit_price']
    base_year = latest['year']
    applied = 0
    for r in sorted(reductions_data, key=lambda x: x['start_year']):
        if r['start_year'] <= base_year:
            continue
        years_elapsed = min(r['start_year'], current_year) - base_year
        if years_elapsed <= 0:
            continue
        pct = float(r['reduction_pct'] or 0) / 100.0
        effective_elapsed = years_elapsed - applied
        if effective_elapsed > 0:
            base_price = base_price * ((1 - pct) ** effective_elapsed)
            applied += effective_elapsed
        if base_year + applied >= current_year:
            break
    return round(base_price, 4), current_year, '年降推算'


class PriceCardCostUpdate(BaseModel):
    material_name: str | None = None
    net_weight: float | None = None
    gross_weight: float | None = None
    material_unit_price: float | None = None
    scrap_price: float | None = None
    surface_treatment: list | None = None
    surface_treatment_cost: float | None = None
    material_cost: float | None = None   # 独立材料成本（元/件），直接存储
    remark: str | None = None
    cost_override: float | None = None


@api_router.get("/api/boss/price-cards/{customer_id}")
def price_card_list(request: Request, customer_id: int):
    """获取某客户下所有零件的价格卡片列表"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    current_year = datetime.now().year
    prev_year = current_year - 1

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id AS price_id, p.part_id, p.customer_id,
                       p.material_name, p.net_weight, p.gross_weight,
                       p.material_unit_price, p.scrap_price,
                       p.surface_treatment,
                       p.surface_treatment_cost, p.cost_override,
                       p.updated_at,
                       pt.part_number, pt.internal_name,
                       tc.name AS customer_name
                FROM prices p
                JOIN parts pt ON p.part_id = pt.id
                LEFT JOIN tooling_customers tc ON p.customer_id = tc.id
                WHERE p.customer_id = %s
                ORDER BY pt.internal_name;
            """, (customer_id,))
            rows = [dict(r) for r in cur.fetchall()]

        result = []
        for row in rows:
            for k, v in row.items():
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
                elif isinstance(v, Decimal):
                    row[k] = float(v)

            price_id = row['price_id']

            # 年份数据
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, year, unit_price, annual_sales
                    FROM price_years WHERE price_id=%s ORDER BY year DESC;
                """, (price_id,))
                years_data = [dict(r) for r in cur.fetchall()]
                for y in years_data:
                    for k, v in y.items():
                        if isinstance(v, Decimal):
                            y[k] = float(v)

            # 年降规则
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, reduction_pct, start_year, duration_years, reason
                    FROM annual_reductions WHERE price_id=%s ORDER BY start_year DESC;
                """, (price_id,))
                reductions_data = [dict(r) for r in cur.fetchall()]
                for r in reductions_data:
                    for k, v in r.items():
                        if isinstance(v, Decimal):
                            r[k] = float(v)

            # 计算成本
            gross = row.get('gross_weight')
            net = row.get('net_weight')
            mp = row.get('material_unit_price')
            sp = row.get('scrap_price')
            stc = row.get('surface_treatment_cost') or 0
            override = row.get('cost_override')

            mat_cost = _calc_material_cost(gross, net, mp, sp)
            if override is not None:
                total_cost = override
            elif mat_cost is not None:
                total_cost = round(mat_cost + (stc or 0), 4)
            else:
                total_cost = None

            # 当前价格（最新录入 or 年降推算）
            cur_price, cur_price_year, price_source = _calc_current_price(
                years_data, reductions_data, current_year)

            # 去年销量
            prev_year_sales = None
            for y in years_data:
                if y['year'] == prev_year:
                    prev_year_sales = y.get('annual_sales')
                    break

            result.append({
                "price_id": price_id,
                "part_id": row['part_id'],
                "customer_id": row['customer_id'],
                "part_number": row['part_number'],
                "internal_name": row['internal_name'],
                "customer_name": row['customer_name'],
                "image_url": _get_image_url(row.get('customer_name'), row.get('part_number')),
                "total_cost": total_cost,
                "prev_year_sales": prev_year_sales,
                "current_price": cur_price,
                "current_price_year": cur_price_year,
                "price_source": price_source,
                "updated_at": row['updated_at'],
            })

        return JSONResponse({"code": 200, "data": result})
    finally:
        conn.close()


@api_router.get("/api/boss/price-cards/detail/{price_id}")
def price_card_detail(request: Request, price_id: int):
    """获取单个零件价格卡片详情"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    current_year = datetime.now().year

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, p.part_id, p.customer_id,
                       p.material_name, p.net_weight, p.gross_weight,
                       p.material_unit_price, p.scrap_price,
                       p.surface_treatment,
                       p.surface_treatment_cost, p.material_cost, p.remark, p.cost_override,
                       p.created_at, p.updated_at,
                       pt.part_number, pt.internal_name,
                       tc.name AS customer_name
                FROM prices p
                JOIN parts pt ON p.part_id = pt.id
                LEFT JOIN tooling_customers tc ON p.customer_id = tc.id
                WHERE p.id = %s;
            """, (price_id,))
            row = cur.fetchone()
            if not row:
                return JSONResponse({"code": 404, "message": "价格台账不存在"}, status_code=404)

        for k, v in row.items():
            if isinstance(v, (datetime, date)):
                row[k] = v.isoformat()
            elif isinstance(v, Decimal):
                row[k] = float(v)

        # 年份数据
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, year, unit_price, annual_sales
                FROM price_years WHERE price_id=%s ORDER BY year DESC;
            """, (price_id,))
            years_data = [dict(r) for r in cur.fetchall()]
            for y in years_data:
                for k, v in y.items():
                    if isinstance(v, Decimal):
                        y[k] = float(v)

        # 年降规则
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, reduction_pct, start_year, duration_years, reason, created_by, created_at
                FROM annual_reductions WHERE price_id=%s ORDER BY start_year DESC;
            """, (price_id,))
            reductions_data = [dict(r) for r in cur.fetchall()]
            for r in reductions_data:
                for k, v in r.items():
                    if isinstance(v, (datetime, date)):
                        r[k] = v.isoformat()
                    elif isinstance(v, Decimal):
                        r[k] = float(v)

        # 调价历史
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, adjusted_at, old_price, new_price,
                       adjustment_type, reason, operator_id
                FROM manual_adjustments WHERE price_id=%s ORDER BY adjusted_at DESC;
            """, (price_id,))
            adj_data = [dict(r) for r in cur.fetchall()]
            for a in adj_data:
                for k, v in a.items():
                    if isinstance(v, (datetime, date)):
                        a[k] = v.isoformat()
                    elif isinstance(v, Decimal):
                        a[k] = float(v)

        # 计算当前价格
        cur_price, cur_price_year, price_source = _calc_current_price(
            years_data, reductions_data, current_year)

        # 材料成本：优先取 DB 存储值（来自 Excel 导入或手动填写的独立材料成本）
        mat_cost = row.get('material_cost')
        if mat_cost is None:
            mat_cost = _calc_material_cost(
                row.get('gross_weight'), row.get('net_weight'),
                row.get('material_unit_price'), row.get('scrap_price'))

        # 总成本
        stc = row.get('surface_treatment_cost') or 0
        override = row.get('cost_override')
        if override is not None:
            total_cost = override
        elif mat_cost is not None:
            total_cost = round(mat_cost + stc, 4)
        else:
            total_cost = None

        result = dict(row)
        result['material_cost'] = mat_cost
        result['total_cost_calc'] = total_cost
        result['current_price'] = cur_price
        result['current_price_year'] = cur_price_year
        result['price_source'] = price_source
        result['years_data'] = years_data
        result['reductions_data'] = reductions_data
        result['adjustments_data'] = adj_data
        result['image_url'] = _get_image_url(row.get('customer_name'), row.get('part_number'))
        # 材料牌号列表（供前端选择）
        result['material_grades'] = get_material_base_prices_for_select()
        # 数据库存 kg → API 统一返回 g（前端显示用 g）
        if result.get('net_weight') is not None:
            result['net_weight'] = round(float(result['net_weight']) * 1000, 6)
        if result.get('gross_weight') is not None:
            result['gross_weight'] = round(float(result['gross_weight']) * 1000, 6)

        # 兜底：把 result 里所有剩余 Decimal / date/datetime 全部转成可 JSON 序列化的类型
        def _sanitize(obj):
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_sanitize(x) for x in obj]
            elif isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return obj

        result = _sanitize(result)

        return JSONResponse({"code": 200, "data": result})
    finally:
        conn.close()


@api_router.put("/api/boss/price-cards/detail/{price_id}")
def price_card_update(request: Request, price_id: int, body: PriceCardCostUpdate):
    """更新价格台账成本要素"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    updates = {}
    for field, val in [
        ('material_name', body.material_name),
        ('net_weight', body.net_weight),
        ('gross_weight', body.gross_weight),
        ('material_unit_price', body.material_unit_price),
        ('scrap_price', body.scrap_price),
        ('surface_treatment_cost', body.surface_treatment_cost),
        ('material_cost', body.material_cost),
        ('remark', body.remark),
        ('cost_override', body.cost_override),
    ]:
        if val is not None:
            # 前端提交 g → 数据库存 kg
            if field in ('net_weight', 'gross_weight'):
                val = round(float(val) / 1000, 6)
            updates[field] = val

    if body.surface_treatment is not None:
        updates['surface_treatment'] = json.dumps(body.surface_treatment)

    if not updates:
        return JSONResponse({"code": 0, "message": "无变更"})

    set_clause = ', '.join(f"{k}=%s" for k in updates)
    set_clause += ', updated_at=NOW()'
    values = list(updates.values()) + [price_id]

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE prices SET {set_clause} WHERE id=%s",
                values
            )
        conn.commit()
        return JSONResponse({"code": 0, "message": "已更新"})
    except Exception as e:
        conn.rollback()
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)
    finally:
        conn.close()


class ReductionBody(BaseModel):
    reduction_pct: float
    start_year: int
    duration_years: int = 0
    reason: str = ""


class CloneBody(BaseModel):
    target_part_id: int
    target_customer_id: int | None = None  # 不填则沿用源 customer_id


@api_router.post("/api/boss/price-cards/detail/{price_id}/clone")
def price_card_clone(request: Request, price_id: int, body: CloneBody):
    """
    将源价格台账（price_id）克隆一份给目标零件，复制内容：
    - 成本要素（material_name / net_weight / gross_weight /
              material_unit_price / scrap_price /
              surface_treatment_cost / material_cost / remark）
    - price_years（年份价格 + 销量）
    - annual_reductions（年降规则）
    - manual_adjustments（调价历史）
    返回新创建的价格台账 ID。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    target_part_id = body.target_part_id
    target_customer_id = body.target_customer_id

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # 验证源台账存在
            cur.execute("SELECT part_id, customer_id, material_name, net_weight, gross_weight, "
                        "material_unit_price, scrap_price, surface_treatment, surface_treatment_cost, "
                        "material_cost, remark, cost_override, created_at "
                        "FROM prices WHERE id=%s", (price_id,))
            src = cur.fetchone()
            if not src:
                return JSONResponse({"code": 404, "message": "源价格台账不存在"}, status_code=404)

            # 验证目标零件存在
            cur.execute("SELECT id FROM parts WHERE id=%s", (target_part_id,))
            if not cur.fetchone():
                return JSONResponse({"code": 404, "message": "目标零件不存在"}, status_code=404)

            src_customer = src[1]
            cust_id = target_customer_id if target_customer_id is not None else src_customer

            # 检查目标台账是否已存在
            cur.execute("SELECT id FROM prices WHERE part_id=%s AND customer_id=%s LIMIT 1",
                        (target_part_id, cust_id))
            existing = cur.fetchone()
            if existing:
                return JSONResponse({
                    "code": 409,
                    "message": f"目标零件在此客户下已存在价格台账（id={existing[0]}），请先删除再克隆"
                }, status_code=409)

        # 在同一事务中执行克隆
        with conn.cursor() as cur:
            cols = ('part_id', 'customer_id', 'material_name', 'net_weight', 'gross_weight',
                    'material_unit_price', 'scrap_price', 'surface_treatment',
                    'surface_treatment_cost', 'material_cost', 'remark', 'cost_override',
                    'created_at', 'updated_at')

            def _json(v):
                return v if isinstance(v, str) else None

            cur.execute(f"""
                INSERT INTO prices
                    (part_id, customer_id, material_name, net_weight, gross_weight,
                     material_unit_price, scrap_price, surface_treatment,
                     surface_treatment_cost, material_cost, remark, cost_override,
                     created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                RETURNING id
            """, (
                target_part_id, cust_id,
                src[2], src[3], src[4],
                src[5], src[6],
                _json(src[7]), src[8],
                src[9], src[10], src[11],
                src[12],
            ))
            new_price_id = cur.fetchone()[0]

            # 克隆 price_years
            cur.execute("""
                INSERT INTO price_years
                    (price_id, year, unit_price, annual_sales, created_at, updated_at)
                SELECT %s, year, unit_price, annual_sales, NOW(), NOW()
                FROM price_years WHERE price_id=%s
            """, (new_price_id, price_id))

            # 克隆 annual_reductions
            cur.execute("""
                INSERT INTO annual_reductions
                    (price_id, reduction_pct, start_year, duration_years, reason, created_by, created_at)
                SELECT %s, reduction_pct, start_year, duration_years, reason, created_by, NOW()
                FROM annual_reductions WHERE price_id=%s
            """, (new_price_id, price_id))

            # 克隆 manual_adjustments
            cur.execute("""
                INSERT INTO manual_adjustments
                    (price_id, adjusted_at, old_price, new_price, adjustment_type, reason, operator_id)
                SELECT %s, adjusted_at, old_price, new_price, adjustment_type, reason, operator_id
                FROM manual_adjustments WHERE price_id=%s
            """, (new_price_id, price_id))

        conn.commit()
        return JSONResponse({
            "code": 0,
            "message": "克隆成功",
            "data": {
                "new_price_id": new_price_id,
                "target_part_id": target_part_id,
                "customer_id": cust_id,
            }
        })
    except Exception as e:
        conn.rollback()
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)
    finally:
        conn.close()


class NewPriceCardBody(BaseModel):
    part_id: int
    customer_id: int


@api_router.post("/api/boss/price-cards/parts")
def price_card_parts_list(request: Request):
    """获取可分配价格的零件列表"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, p.part_number, p.internal_name,
                       COALESCE(p.material_name, '') AS material_name
                FROM parts p
                ORDER BY p.part_number;
            """)
            rows = cur.fetchall()
        return JSONResponse({"code": 200, "data": [dict(r) for r in rows]})
    finally:
        conn.close()


@api_router.post("/api/boss/price-cards")
def price_card_create(request: Request, body: NewPriceCardBody):
    """为某客户创建零件价格台账"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # 检查是否已存在
            cur.execute(
                "SELECT id FROM prices WHERE part_id=%s AND customer_id=%s",
                (body.part_id, body.customer_id)
            )
            if cur.fetchone():
                return JSONResponse({"code": 400, "message": "该零件的价格台账已存在"}, status_code=400)

            # 检查零件是否存在
            cur.execute("SELECT id FROM parts WHERE id=%s", (body.part_id,))
            if not cur.fetchone():
                return JSONResponse({"code": 404, "message": "零件不存在"}, status_code=404)

            cur.execute("""
                INSERT INTO prices (part_id, customer_id, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                RETURNING id;
            """, (body.part_id, body.customer_id))
            new_id = cur.fetchone()[0]
        conn.commit()
        return JSONResponse({"code": 0, "data": {"price_id": new_id, "part_id": body.part_id, "customer_id": body.customer_id}})
    except Exception as e:
        conn.rollback()
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)
    finally:
        conn.close()


@api_router.post("/api/boss/price-cards/detail/{price_id}/reduction")
def price_card_add_reduction(request: Request, price_id: int, body: ReductionBody):
    """为某价格台账添加年降规则"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO annual_reductions
                    (price_id, reduction_pct, start_year, duration_years, reason, created_by, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,NOW())
            """, (price_id, body.reduction_pct, body.start_year,
                  body.duration_years, body.reason, user["id"]))
        conn.commit()
        return JSONResponse({"code": 0, "message": "年降规则已添加"})
    except Exception as e:
        conn.rollback()
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)
    finally:
        conn.close()


@boss_router.get("/boss/quotes")
def boss_quote_approval_page(request: Request):
    """老板报价审批首页 — 仅 role_level >= 9 可访问"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 9:
        raise HTTPException(status_code=403, detail="仅老板可访问")
    return templates.TemplateResponse("boss/quote_approval.html", {
        "request": request,
        "user": user,
    })


@api_router.get("/api/boss/quotes")
def boss_quote_list(request: Request):
    """
    返回老板待审批的报价单列表（status = PENDING_BOSS）。
    包含零件参数 + 价格明细 + 提交人信息。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 9:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        rows = get_pending_boss_quotes()
        return JSONResponse({"code": 200, "data": rows})
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


class BossQuickEditBody(BaseModel):
    thickness: float | None = None
    width: float | None = None
    press_stroke: float | None = None
    cavity_count: int | None = None
    machine_type: str | None = None
    gross_weight: float | None = None
    material_cost_override: float | None = None
    stamping_fee: float | None = None
    inspection_fee: float | None = None
    packaging_fee: float | None = None
    surface_fee: float | None = None
    treatment_fee: float | None = None
    mold_cost: float | None = None
    profit_margin: float | None = None
    final_price_override: float | None = None
    unit_price_override: float | None = None
    mold_discount_mode: str | None = None
    mold_discount_rate: float | None = None
    treatment_items: list | None = None


@api_router.put("/api/boss/quotes/{quote_id}")
def boss_quick_edit(request: Request, quote_id: int, body: BossQuickEditBody):
    """
    老板快速修改报价单字段（在批准前调整价格参数）。
    仅 PENDING_BOSS 状态可操作。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 9:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok = boss_update_quote(quote_id, body.model_dump(exclude_none=True))
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单状态不允许修改（仅 PENDING_BOSS 可操作）"}, status_code=400)
        return JSONResponse({"code": 200, "message": "修改成功"})
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/boss/quotes/{quote_id}/approve")
def boss_approve(request: Request, quote_id: int):
    """老板批准报价单"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 9:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok = approve_quote(quote_id, operator_id=user["id"])
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单状态不允许通过"}, status_code=400)
        return JSONResponse({"code": 200, "message": "审核通过"})
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/boss/quotes/{quote_id}/reject")
def boss_reject(request: Request, quote_id: int, body: RejectBody):
    """老板驳回报价单"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 9:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    try:
        ok = reject_quote(quote_id, rejection_reason=body.reason, operator_id=user["id"])
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单状态不允许驳回"}, status_code=400)
        return JSONResponse({"code": 200, "message": "驳回成功"})
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════════
#  Excel 价格台账批量导入
# ═══════════════════════════════════════════════════════════════════

class PriceImportPreview(BaseModel):
    customer_id: int
    filename: str
    rows: list[dict]
    summary: dict


def _parse_price_excel_bytes(content: bytes, customer_id: int) -> tuple[list[dict], dict]:
    """解析 Excel 文件内容，返回（行列表，汇总信息）。

    支持两种格式：
      - 新模板（18列，文件头含"本厂产品名称"）：col=0「原图产品编号」...
        各列：原图产品编号 | 图片 | 本厂产品名称 | 模具类型 | 材质 | 用料规格 |
              参考冲床吨位 | 单件毛重量(g) | 产品净重/g | 材料价格 | 废料价格 |
              材料成本 | 表面处理 | 胶成本 | 喷涂成本/外协成本 | 成本 | 2025年开票价格 | 2025销量
      - 旧格式（<16列）：按 idx() 动态匹配，col_stc 之前的「成本」列为总成本（非材料成本）

    子行（重量/价格全为 null）继承上一个主行的数据。
    """
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    # 优先找有完整数据的 Sheet（零件编号 + 重量列都有实际数据的）
    sheets_priority = []
    for name in wb.sheetnames:
        ws = wb[name]
        if ws.max_row < 3:
            continue
        headers = [str(c).strip() if c is not None else '' for c in next(ws.iter_rows(values_only=True))]
        header_str = '|'.join(headers)

        def idx_hdr(keywords):
            for i, h in enumerate(headers):
                if h and any(kw in h for kw in keywords):
                    return i
            return -1

        col_part  = idx_hdr(['原图产品编号', '零件编号', '规格型号', '件号'])
        col_gross = idx_hdr(['单件毛重量', '毛重', 'gross'])
        col_net   = idx_hdr(['单件净重量', '产品净重', '净重'])

        # 统计实际数据行中有零件编号且有重量数据的行数
        score = 0
        for row in ws.iter_rows(values_only=True):
            part = row[col_part] if col_part >= 0 else None
            gross = row[col_gross] if col_gross >= 0 else None
            net   = row[col_net]   if col_net   >= 0 else None
            if part and str(part).strip() and not any(x in str(part) for x in ('总计', '合计')):
                if col_gross >= 0 or col_net >= 0:
                    score += 1

        entry = (name, headers, score)
        if '原图产品编号' in header_str or '件号' in header_str:
            sheets_priority.insert(0, entry)
        else:
            sheets_priority.append(entry)

    # 按数据完整性排序
    sheets_priority.sort(key=lambda x: x[2], reverse=True)

    if not sheets_priority:
        raise ValueError("未找到有效数据 Sheet")

    target_name, headers, _ = sheets_priority[0]
    ws = wb[target_name]

    # ── 新模板列索引（从 0 开始，按顺序精确指定）───────────────────────────────
    # 0:原图产品编号  1:图片  2:本厂产品名称  3:模具类型  4:材质
    # 5:用料规格  6:参考冲床吨位  7:单件毛重量(g)  8:产品净重/g
    # 9:材料价格  10:废料价格  11:材料成本  12:表面处理
    # 13:胶成本  14:喷涂成本/外协成本  15:成本  16:2025年开票价格  17:2025销量
    #
    # 对于其他格式旧 Excel，列索引可能不同 → 如果命中旧格式的列名特征则动态取
    # 最终以「col_cost=11」「col_stc=14」「col_price=16」「col_sales=17」为准

    def idx(keywords):
        for i, h in enumerate(headers):
            if h and any(kw in h for kw in keywords):
                return i
        return -1

    # ── 动态列索引（通用格式）────────────────────────────────────────────────
    col_part  = idx(['原图产品编号', '零件编号', '规格型号', '件号'])
    col_gross = idx(['单件毛重量', '毛重', 'gross'])
    col_net   = idx(['单件净重量', '产品净重', '净重'])
    col_mp    = idx(['材料价格'])
    col_sp    = idx(['废料价格'])
    col_stc   = idx(['喷涂成本', '胶成本', '回火', '外协成本'])
    col_price = idx(['价格', '单价', 'price'])
    col_sales = idx(['销量', 'sales', '年销量'])

    # ── 材料成本 / 总成本列的智能判定────────────────────────────────────────
    # 新模板（18列）：col=11「材料成本」，col=15「成本」（总成本）
    # 旧格式：col<col_stc 的「成本」= 总成本（不是材料成本）
    if len(headers) >= 16 and col_part >= 0:
        # 疑似新模板：件号列存在 且 总列数>=16 → 用固定偏移
        _mat_cost_col   = 11    # 新模板「材料成本」
        _total_cost_col = 15    # 新模板「成本」总
    else:
        # 旧格式：用 idx 动态取，并根据与 col_stc 的相对位置判断
        _cost_raw = idx(['成本'])
        if _cost_raw >= 0 and _cost_raw < col_stc:
            # 旧格式「成本」在 stc 之前 → 该列是总成本，mat_cost 无此列由公式算
            _mat_cost_col   = -1
            _total_cost_col = _cost_raw
        else:
            # 新格式或找不到「成本」列
            _mat_cost_col   = _cost_raw if _cost_raw >= 0 else -1
            _total_cost_col = _cost_raw if _cost_raw >= 0 else -1

    rows_out = []
    last_valid = None

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue

        part = _cell(row, col_part)
        if not part:
            continue
        part = str(part).strip()

        # 剥离件号末尾的括号内容（如「A00125983-3（喷涂）」→ 件号「A00125983-3」，备注「喷涂」）
        suffix_match = re.search(r'[（(][^）)]+[）)]\s*$', part)
        part_remark = None
        if suffix_match:
            part_remark = suffix_match.group()[1:-1].strip()  # 去掉首尾括号
            part = part[:suffix_match.start()].strip()

        if '总计' in part or '合计' in part or not part:
            last_valid = None
            continue

        gross = _num(row, col_gross)
        net   = _num(row, col_net)
        mp_excel = _num(row, col_mp)
        sp_excel = _num(row, col_sp)
        stc_excel = _num(row, col_stc)
        # 总成本（= Excel「成本」列 = 材料净成本，不含 stc）
        excel_total_cost = _num(row, _total_cost_col) if _total_cost_col >= 0 else None
        # 材料成本（= Excel「材料成本」列，或由公式计算得出）
        mat_cost = _num(row, _mat_cost_col) if _mat_cost_col >= 0 else None
        price = _num(row, col_price)
        sales = _num(row, col_sales)

        if gross is None and net is None and mp_excel is None:
            if last_valid:
                gross = last_valid['gross_weight']
                net   = last_valid['net_weight']
                mp_excel = last_valid['material_unit_price']
                sp_excel = last_valid['scrap_price']
                stc_excel = last_valid.get('surface_treatment_cost')
                excel_total_cost = last_valid.get('excel_cost')
                mat_cost = last_valid.get('material_cost')
                if part_remark:
                    last_valid['remark'] = part_remark
        else:
            last_valid = {}
            if part_remark:
                last_valid['remark'] = part_remark

        # Excel 重量列为 g，数据库存 kg → /1000
        gross_kg = round(gross / 1000, 8) if gross is not None else None
        net_kg   = round(net   / 1000, 8) if net   is not None else None

        # scrap_ratio = (gross - net) / gross（废料比率，0~1）
        scrap_ratio = None
        if gross is not None and net is not None and gross != 0:
            scrap_ratio = round((gross - net) / gross, 6)

        # material_unit_price（元/kg）：优先用 Excel 列9「材料价格」；
        # 若无则用「材料成本/净重」推算（仅当两者均缺失时）
        mp_db = _num(row, col_mp) if col_mp >= 0 else None
        if mp_db is None and mat_cost is not None and net_kg and net_kg != 0:
            mp_db = round(mat_cost / net_kg, 6)

        # 若无「材料成本」列（旧格式），则从总成本反推：mat_cost = total - stc
        if mat_cost is None and excel_total_cost is not None:
            mat_cost = round(excel_total_cost - (stc_excel or 0), 6)

        # 总成本：excel_total_cost（不含 stc） + stc
        total_cost = round((excel_total_cost or 0) + (stc_excel or 0), 6) if excel_total_cost is not None else None

        # stc 已是元/件
        stc_db = stc_excel

        if net is not None:
            last_valid.update({
                'gross_weight': gross_kg, 'net_weight': net_kg,
                'material_unit_price': mp_db, 'scrap_price': scrap_ratio,
                'surface_treatment_cost': stc_db,
                'material_cost': mat_cost,
                'excel_cost': excel_total_cost,
                'remark': part_remark,
            })

        rows_out.append({
            'part_number': part,
            'remark': part_remark,
            'gross_weight': gross_kg,
            'net_weight': net_kg,
            'material_unit_price': mp_db,
            'scrap_price': scrap_ratio,
            'surface_treatment_cost': stc_db,
            'material_cost': mat_cost,
            'cost_override': total_cost,
            'current_price': price,
            'prev_year_sales': sales,
        })

    summary = {
        'total_rows': len(rows_out),
        'with_weight': sum(1 for r in rows_out if r['gross_weight'] is not None),
        'with_price': sum(1 for r in rows_out if r['current_price'] is not None),
        'with_sales': sum(1 for r in rows_out if r['prev_year_sales'] is not None),
        'sheet': target_name,
    }
    return rows_out, summary


def _cell(row, col: int):
    if col < 0 or col >= len(row):
        return None
    v = row[col]
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _num(row, col: int):
    if col < 0 or col >= len(row):
        return None
    v = row[col]
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@api_router.post("/api/boss/price-cards/import-preview")
async def price_import_preview(
    request: Request,
    file: UploadFile = File(...),
    customer_id: int = Form(...),
):
    """解析 Excel 文件，返回预览数据（不写入数据库）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return JSONResponse({"code": 400, "message": "仅支持 .xlsx / .xls 文件"}, status_code=400)

    try:
        content = await file.read()
        rows, summary = _parse_price_excel_bytes(content, customer_id)
        return JSONResponse({
            "code": 0,
            "data": {
                "filename": file.filename,
                "customer_id": customer_id,
                "rows": rows,
                "summary": summary,
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"code": 500, "message": f"解析失败: {e}"}, status_code=500)


@api_router.post("/api/boss/price-cards/import-confirm")
async def price_import_confirm(
    request: Request,
    file: UploadFile = File(...),
    customer_id: int = Form(...),
):
    """确认导入：写入/更新数据库（upsert）"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 5:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)

    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return JSONResponse({"code": 400, "message": "仅支持 .xlsx / .xls 文件"}, status_code=400)

    try:
        content = await file.read()
        rows, summary = _parse_price_excel_bytes(content, customer_id)

        conn = psycopg2.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cur:
                imported = 0
                skipped = 0

                for row_data in rows:
                    part_number = row_data['part_number']
                    if not part_number:
                        skipped += 1
                        continue

                    cur.execute("SELECT id FROM parts WHERE part_number=%s LIMIT 1", (part_number,))
                    part_row = cur.fetchone()
                    if part_row:
                        part_id = part_row[0]
                    else:
                        cur.execute(
                            "INSERT INTO parts (part_number, internal_name, status, created_at, updated_at) "
                            "VALUES (%s, %s, 'DRAFT', NOW(), NOW()) RETURNING id",
                            (part_number, part_number))
                        part_id = cur.fetchone()[0]

                    cur.execute(
                        "SELECT id FROM prices WHERE part_id=%s AND customer_id=%s LIMIT 1",
                        (part_id, customer_id))
                    price_row = cur.fetchone()

                    fields = []
                    for f in ('gross_weight', 'net_weight', 'material_unit_price',
                               'scrap_price', 'surface_treatment_cost',
                               'material_cost', 'remark', 'cost_override'):
                        if row_data.get(f) is not None:
                            fields.append(f)

                    if price_row:
                        price_id = price_row[0]
                        if fields:
                            set_parts = ', '.join(f'{f}=%s' for f in fields)
                            vals = tuple(row_data[f] for f in fields) + (price_id,)
                            cur.execute(
                                f"UPDATE prices SET {set_parts}, updated_at=NOW() WHERE id=%s",
                                vals)
                        imported += 1
                    else:
                        col_names = ', '.join(fields)
                        placeholders = ', '.join(['%s'] * len(fields))
                        vals = [part_id, customer_id] + [row_data[f] for f in fields]
                        cur.execute(
                            "INSERT INTO prices (part_id, customer_id, " + col_names
                            + ", created_at, updated_at) VALUES (%s, %s, "
                            + placeholders + ", NOW(), NOW())",
                            vals)
                        imported += 1

                    # 写入/更新年销量（price_id 需要重新获取）
                    price_sales = row_data.get('prev_year_sales')
                    price_val = row_data.get('current_price')
                    if price_sales is not None or price_val is not None:
                        cur.execute("SELECT id FROM prices WHERE part_id=%s AND customer_id=%s LIMIT 1", (part_id, customer_id))
                        pid = cur.fetchone()[0]
                        prev_year = 2025
                        if price_sales is not None:
                            cur.execute("""
                                INSERT INTO price_years (price_id, year, unit_price, annual_sales, updated_at)
                                VALUES (%s, %s, %s, %s, NOW())
                                ON CONFLICT (price_id, year) DO UPDATE SET
                                    unit_price = COALESCE(EXCLUDED.unit_price, price_years.unit_price),
                                    annual_sales = COALESCE(EXCLUDED.annual_sales, price_years.annual_sales),
                                    updated_at = NOW()
                            """, (pid, prev_year,
                                  price_val if price_val is not None else None,
                                  int(price_sales) if price_sales is not None else None))

            conn.commit()
            return JSONResponse({
                "code": 0,
                "message": f"导入完成：新增/更新 {imported} 条，忽略 {skipped} 行",
                "data": {"imported": imported, "skipped": skipped, "summary": summary},
            })
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"code": 500, "message": f"导入失败: {e}"}, status_code=500)


# ============================================================================