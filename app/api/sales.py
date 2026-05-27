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
import psycopg2
import re
import os
import uuid
from app.core.auth import get_current_user
from app.core.templates import templates
from app.models.schemas import PartCreateRequest
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


class CalcPricingBody(BaseModel):
    thickness: float = 0        # 厚度 T (mm)
    width: float = 0            # 宽度 W (mm)
    press_stroke: float = 0    # 行程 P (mm)
    material_name: str = ""      # 材料牌号
    cavity_count: int = 1        # 穴数
    scrap_rate: float = 0.10    # 废料率（仅作参考展示）
    gross_weight_g: float | None = None   # 前端已算好的毛重（g），直接用
    net_weight_g: float | None = None      # 前端已算好的净重（g），直接用
    scrap_weight_g: float | None = None    # 前端已算好的废料重（g），直接用
    material_utilization: float = 100.0    # 材料利用率（%），用户在前端输入，默认100
    stamping_fee: float = 0      # 冲压费
    inspection_fee: float = 0    # 全检费
    packaging_fee: float = 0     # 包装运费
    surface_fee: float = 0      # 表面处理费
    mold_cost: float = 0         # 模具费
    treatment_fee: float = 0     # 处理费合计
    profit_margin: float = 0      # 利润率系数
    override_final_price: float | None = None
    override_material_cost: float | None = None  # 材料净成本覆盖（元）
    unit_price_override: float | None = None      # 材料单价覆盖（元/kg）
    machine_type: str | None = None  # 使用设备（吨位/型号）


class QuoteCreateBody(BaseModel):
    """创建报价单时接收的参数（对应 quotes 表字段）"""
    part_id: int
    annual_usage: int = 0
    pricing_mode: str = "independent"   # 'independent' | 'reference'
    thickness: float | None = None
    width: float | None = None
    press_stroke: float | None = None
    cavity_count: int = 1
    scrap_rate: float = 0.10
    stamping_fee: float = 0
    surface_fee: float = 0
    treatment_fee: float = 0
    profit_margin: float = 0
    final_price_override: float | None = None
    override_fields: list[str] = []
    approval_status: str = "DRAFT"      # 'DRAFT' | 'PENDING_BOSS'
    submitted_by: int | None = None
    nomination_status: str | None = None
    nomination_attachment: str | None = None
    machine_type: str | None = None


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


@api_router.post("/api/calc-pricing")
def calc_pricing(request: Request, body: CalcPricingBody = None):
    """白盒报价核算（JSON body），Path B 实时核算调用"""
    import logging
    logger2 = logging.getLogger(__name__)
    logger2.debug("[API /api/calc-pricing] received body=%s", body)
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录", "data": None}, status_code=401)
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
def list_treatments(request: Request):
    """返回所有表面处理方式列表"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    try:
        rows = get_all_treatments()
        return JSONResponse({"code": 200, "data": rows})
    except Exception as e:
        return JSONResponse({"code": 500, "message": str(e)}, status_code=500)


@api_router.post("/api/dict/treatments")
def create_or_update_treatment(request: Request, body: TreatmentBody):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
    if body.calc_mode not in ("manual", "net_weight"):
        return JSONResponse({"code": 400, "message": "calc_mode must be manual or net_weight"}, status_code=400)
    try:
        result = upsert_treatment(body.name, body.calc_mode, body.rate, body.unit)
        return JSONResponse(jsonable_encoder(result))
    except Exception as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)


@api_router.delete("/api/dict/treatments/{treatment_id}")
def remove_treatment(request: Request, treatment_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录"}, status_code=401)
    if user["role_level"] < 4:
        return JSONResponse({"code": 403, "message": "权限不足"}, status_code=403)
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
    # 双重防线：若当前处于业务视角，拒绝审批
    view_as = request.cookies.get("view_as", "")
    if view_as and view_as != "admin":
        return JSONResponse(
            {"code": 403, "message": "当前处于业务视角，无法执行审批操作。请切换至老板视角后重试。"},
            status_code=403)
    try:
        ok = approve_quote(quote_id, operator_id=user["id"])
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单状态不允许通过（仅 PENDING_BOSS 可审核）"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "审核通过"}))
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
    # 双重防线：若当前处于业务视角，拒绝驳回
    view_as = request.cookies.get("view_as", "")
    if view_as and view_as != "admin":
        return JSONResponse(
            {"code": 403, "message": "当前处于业务视角，无法执行驳回操作。请切换至老板视角后重试。"},
            status_code=403)
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
            unit_price_override=calc.get("unit_price_override") if calc.get("unit_price_override") else None,
            material_cost_override=calc.get("material_net_cost_override") if calc.get("material_net_cost_override") else None,
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
    # 双重防线：若当前处于业务视角（view_as != 'admin'），拒绝审批
    view_as = request.cookies.get("view_as", "")
    if view_as and view_as != "admin":
        return JSONResponse(
            {"code": 403, "message": "当前处于业务视角，无法执行审批操作。请切换至老板视角后重试。"},
            status_code=403)
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
    # 双重防线：若当前处于业务视角（view_as != 'admin'），拒绝驳回
    view_as = request.cookies.get("view_as", "")
    if view_as and view_as != "admin":
        return JSONResponse(
            {"code": 403, "message": "当前处于业务视角，无法执行驳回操作。请切换至老板视角后重试。"},
            status_code=403)
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
    profit_margin: float | None = None
    final_price_override: float | None = None
    unit_price_override: float | None = None
    mold_cost: float | None = None


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

