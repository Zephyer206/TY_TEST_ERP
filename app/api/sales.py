"""
app/api/sales.py
业务部路由
  - api_router:  /api/*  (无前缀，直接挂根)
  - router:      /sales/* (页面路由)
"""
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
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
    update_quote,
    submit_quote_to_boss,
    approve_quote,
    reject_quote,
    delete_quote,
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
)

# ── API 路由（无前缀，路径如 /api/part/{id}）─────────────────
api_router = APIRouter(prefix="", tags=["sales-api"])

# ── 页面路由（/sales 前缀）───────────────────────────────────
router = APIRouter(prefix="/sales", tags=["sales"])


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
        part_id = create_part_with_mold_and_pricing(
            part_number=body.part_number,
            internal_name=body.internal_name,
            material_name=body.material_name,
            pricing_mode=body.pricing_mode,
            referenced_part_id=body.referenced_part_id,
            thickness=body.thickness if body.pricing_mode == "independent" else None,
            width=body.width if body.pricing_mode == "independent" else None,
            press_stroke=body.press_stroke if body.pricing_mode == "independent" else None,
            cavity_count=body.cavity_count if body.pricing_mode == "independent" else 1,
            material_utilization=body.material_utilization if body.pricing_mode == "independent" else 100.0,
            machine_type=body.machine_type,
            press_tonnage=body.press_tonnage,
            stamping_fee=body.stamping_fee,
            surface_fee=body.surface_fee,
            profit_margin=body.profit_margin,
            final_price_override=body.final_price_override,
            customer_id=body.customer_id,
            alias_part_number=body.alias_part_number,
            operator_id=user["id"],
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
    treatment_fee: float = 0     # 处理费合计
    profit_margin: float = 0      # 利润率系数
    override_final_price: float | None = None
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
    stamping_fee: float | None = None
    surface_fee: float | None = None
    treatment_fee: float | None = None
    profit_margin: float | None = None
    final_price_override: float | None = None
    unit_price_override: float | None = None   # 材料单价覆盖（元/kg）
    material_cost_override: float | None = None  # 材料净成本覆盖（元）
    override_fields: list[str] | None = None
    nomination_status: str | None = None
    nomination_attachment: str | None = None
    machine_type: str | None = None


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
    if user["role_level"] < 4:
        raise HTTPException(status_code=403, detail="权限不足")
    parts = get_parts_for_pricing_list(status_filter=status_filter.upper() if status_filter else "")
    return templates.TemplateResponse("sales/part_pricing.html", {
        "request": request, "user": user, "parts": parts,
        "status_filter": status_filter.upper() if status_filter else "",
    })


@router.get("/parts/pricing")
def sales_part_pricing_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 4:
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
                   attachment_url: str = Form("")):
    """
    定点终裁确认（从报价单 quotes 维度定点）。
    confirmed_price 参数已从签名移除——定点价格来自报价单的 final_price_override。
    """
    user = get_current_user(request)
    if not user or user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="权限不足")
    try:
        result = confirm_nomination(
            part_id=part_id,
            operator_id=user["id"],
            attachment_filenames=[attachment_url] if attachment_url else None,
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
            stamping_fee=body.stamping_fee,
            surface_fee=body.surface_fee,
            treatment_fee=body.treatment_fee,
            profit_margin=body.profit_margin,
            final_price_override=body.final_price_override,
            unit_price_override=body.unit_price_override,
            material_cost_override=body.material_cost_override,
            override_fields=body.override_fields,
            nomination_status=body.nomination_status,
            nomination_attachment=body.nomination_attachment,
            machine_type=body.machine_type,
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
                approval_status='DRAFT',
                operator_id=user['id'],
            )
        else:
            # 无 APPROVED 报价单，取 parts 主档 T/W/P
            from app.services.db_service import get_part_by_id
            part = get_part_by_id(part_id)
            if not part:
                return JSONResponse({"code": 404, "message": "零件不存在"}, status_code=404)
            new_id = create_quote(
                part_id=part_id,
                pricing_mode='independent',
                thickness=part.get('thickness'),
                width=part.get('width'),
                press_stroke=part.get('press_stroke'),
                cavity_count=part.get('cavity_count') or 1,
                approval_status='DRAFT',
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
            stamping_fee=body.stamping_fee,
            surface_fee=body.surface_fee,
            treatment_fee=body.treatment_fee,
            profit_margin=body.profit_margin,
            final_price_override=body.final_price_override,
            unit_price_override=body.unit_price_override,
            material_cost_override=body.material_cost_override,
            override_fields=body.override_fields,
            nomination_status=body.nomination_status,
            nomination_attachment=body.nomination_attachment,
            machine_type=body.machine_type,
        )
        if not ok:
            return JSONResponse({"code": 400, "message": "报价单不存在或状态不允许编辑"}, status_code=400)
        return JSONResponse(jsonable_encoder({"code": 200, "message": "修改已保存"}))
    except Exception as e:
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
