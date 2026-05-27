"""
app/api/tech_api.py
===================
打样与源头建档路由层 — 技术部专项（JSON API）

职责：接参 → Pydantic 校验 → 调用 Service → JSONResponse
禁止在 Router 层写 SQL 或 if-else 业务逻辑。

路由清单
--------
POST /tech/part/profile          — 源头建档（录入 T/W/P + 模具参数）
GET  /tech/part/{id}            — 读取零件主档
POST /tech/prototype/start       — 连续模打样开机
POST /tech/prototype/report      — 连续模打样报工（填入即生效）
POST /tech/simple-prototype      — 简易模打样（完全线下）
GET  /tech/sample-inventory      — 样件虚拟库视图
GET  /tech/qa-audit             — QA 审计记录查询

前缀: /tech
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Optional
from fastapi import UploadFile, File
import uuid
import os
import re
import psycopg2

from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.tech_service import (
    create_part_profile,
    get_part_profile,
    start_prototype,
    report_prototype,
    report_simple_prototype,
    get_sample_inventory,
)
from app.services.qa_service import get_qa_audit_logs
from app.services.db_service import tech_approve_quote, tech_reject_quote, DB_CONFIG
from app.models.schemas import (
    PartProfileCreateRequest,
    PartProfileData,
    PrototypeStartRequest,
    PrototypeStartData,
    PrototypeReportRequest,
    PrototypeReportData,
    SimplePrototypeReportRequest,
    SimplePrototypeData,
    SampleInventoryRow,
    QAAuditLogRow,
)

router = APIRouter(prefix="/tech", tags=["tech_api"])

# ── JSON API 路由（无前缀，路径如 /api/tech/*）────────────────
api_router = APIRouter(prefix="", tags=["tech_api"])


# ============================================================================
# §Tech 源头建档
# ============================================================================

@router.post("/part/profile")
def api_create_part_profile(request: Request, body: PartProfileCreateRequest):
    """
    源头建档 — 录入零件物理基因参数（T/W/P + 模具参数）。

    INSERT parts（mold_cost 已在 quotes 层，parts 表不存金额字段）。

    权限：role_level >= 4（技术部）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需技术部）"}, status_code=403)

    result = create_part_profile(
        part_number=body.part_number,
        internal_name=body.internal_name,
        material_name=body.material_name,
        remark=body.remark or "",
        created_by=user["id"],
    )

    status_code = 200 if result.get("code") == 0 else 400
    return JSONResponse(result, status_code=status_code)


@router.get("/part/{part_id}")
def api_get_part_profile(request: Request, part_id: int):
    """
    读取零件主档（含 T/W/P + 模具参数）。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    profile = get_part_profile(part_id)
    if not profile:
        return JSONResponse({"error": f"零件 #{part_id} 不存在"}, status_code=404)

    return JSONResponse({"code": 0, "data": profile})


# ============================================================================
# §Tech 连续模打样（需扫机台 → PROTOTYPING → 填入即生效）
# ============================================================================

@router.post("/prototype/start")
def api_start_prototype(request: Request, body: PrototypeStartRequest):
    """
    连续模打样开机 — 机台进入 PROTOTYPING 状态。

    防呆规则：
      - 机台必须为 IDLE 态
      - 禁止重复 PROTOTYPING 会话

    权限：role_level >= 2（组长）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需设计工程师）"}, status_code=403)

    result = start_prototype(machine_id=body.machine_id)

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "不存在" in msg:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


@router.post("/prototype/report")
def api_report_prototype(request: Request, body: PrototypeReportRequest):
    """
    连续模打样报工 — 填入即生效（.cursorrules 打样双轨）。

    执行链路：
      1. 找 PROTOTYPING 会话
      2. 查 cavity_count → 成品量 = qty × cavity_count
      3. 原料扣减：零（打样不计料耗）
      4. sample_inventory.sample_qty += 成品量
      5. 会话 CLOSED + 机台 → IDLE

    权限：role_level >= 2
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需设计工程师）"}, status_code=403)

    result = report_prototype(
        machine_id=body.machine_id,
        qty=body.qty,
        operator_id=body.operator_id or user["id"],
    )

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "不存在" in msg:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# §Tech 简易模打样（完全线下，无需扫机台）
# ============================================================================

@router.post("/simple-prototype")
def api_simple_prototype(request: Request, body: SimplePrototypeReportRequest):
    """
    简易模打样 — 完全线下隐形，直接累加 sample_inventory。

    执行链路：
      1. 读取零件 cavity_count
      2. 成品量 = qty × cavity_count
      3. 原料扣减：零
      4. sample_inventory.sample_qty += 成品量
      5. 不写入 production_sessions（完全线下，无系统机台占用）

    权限：role_level >= 2
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需设计工程师）"}, status_code=403)

    result = report_simple_prototype(
        part_id=body.part_id,
        qty=body.qty,
        operator_id=body.operator_id or user["id"],
    )

    if result.get("code") == 1:
        msg = result.get("message", "")
        if "不存在" in msg:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result, status_code=400)

    return JSONResponse(result, status_code=200)


# ============================================================================
# §Tech 辅助查询
# ============================================================================

@router.get("/sample-inventory")
def api_sample_inventory(request: Request, part_id: int = 0):
    """
    查询样件虚拟库（sample_inventory）。

    参数
    ----
    part_id : int 按零件过滤（0 = 全部有库存的零件）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)

    rows = get_sample_inventory(
        part_id=part_id if part_id else None,
    )
    return JSONResponse({"code": 0, "data": rows})


@router.get("/qa-audit")
def api_qa_audit(
    request: Request,
    work_order_id: int = 0,
    action_type: str = "",
    limit: int = 50,
):
    """
    查询 QA 审计记录（黑匣子）。

    参数
    ----
    work_order_id : int  按工单过滤（0 = 不限）
    action_type  : str  按动作类型过滤（如 first_piece_release）
    limit        : int  返回条数上限（默认 50）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 3:
        return JSONResponse({"error": "权限不足"}, status_code=403)

    rows = get_qa_audit_logs(
        work_order_id=work_order_id if work_order_id else None,
        action_type=action_type if action_type else None,
        limit=limit,
    )
    return JSONResponse({"code": 0, "data": rows})


# ============================================================================
# §Tech 报价技术审核（V7.0 新增）
# ============================================================================

class TechReviewBody(BaseModel):
    rejection_reason: str = ""


@router.post("/quote/{quote_id}/tech-approve")
def api_tech_approve_quote(request: Request, quote_id: int):
    """
    技术部审核通过报价单（WAITING_FOR_TECH → TECH_APPROVED）。
    权限：role_level >= 4（技术部）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需技术部）"}, status_code=403)
    ok = tech_approve_quote(quote_id, operator_id=user["id"])
    if not ok:
        return JSONResponse({"code": 1, "message": "操作失败：报价单状态不允许技术审核通过"}, status_code=400)
    return JSONResponse({"code": 0, "message": "技术审核通过"})


@router.post("/quote/{quote_id}/tech-reject")
def api_tech_reject_quote(request: Request, quote_id: int, body: TechReviewBody):
    """
    技术部驳回报价单（WAITING_FOR_TECH → TECH_REJECTED）。
    权限：role_level >= 4（技术部）
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需技术部）"}, status_code=403)
    ok = tech_reject_quote(quote_id, rejection_reason=body.rejection_reason, operator_id=user["id"])
    if not ok:
        return JSONResponse({"code": 1, "message": "操作失败：报价单状态不允许技术驳回"}, status_code=400)
    return JSONResponse({"code": 0, "message": "技术驳回成功"})


# ============================================================================
# §Tech 技术参数填写（业务提交图纸后，开发填写 T/W/P、模具费、穴数、吨位）
# ============================================================================

class TechParamsBody(BaseModel):
    thickness: Optional[float] = None
    width: Optional[float] = None
    press_stroke: Optional[float] = None
    cavity_count: Optional[int] = None
    mold_cost: Optional[float] = None
    press_tonnage: Optional[int] = None
    sdr_drawing_path: Optional[str] = None
    material_utilization: Optional[float] = None  # 材料利用率（%）
    mold_life: Optional[int] = None  # 模具寿命（万次）
    mold_type: Optional[str] = None  # 模具类型：continuous（连续模）/ progressive（工程模）


@router.get("/tech-params")
def tech_params_page(request: Request):
    """
    技术参数填写页面 — 设计部填写 T/W/P、模具费、穴数、吨位。
    权限：role_level >= 4（设计工程师及以上）
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.get("role_level", 0) < 4:
        raise HTTPException(status_code=403, detail="权限不足（需设计工程师）")
    return templates.TemplateResponse("tech/tech_params.html", {
        "request": request,
        "user": user,
    })


# ── 模具类型管理 ────────────────────────────────────────────────

@api_router.get("/api/tech/mold-types")
def api_get_mold_types(request: Request):
    """获取所有模具类型列表"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    from app.services.db_service import get_all_mold_types
    rows = get_all_mold_types()
    return JSONResponse({"code": 0, "data": rows})


class MoldTypeBody(BaseModel):
    id: Optional[int] = None
    code: str
    name: str
    sort_order: int = 0


@api_router.post("/api/tech/mold-types")
def api_create_mold_type(request: Request, body: MoldTypeBody):
    """创建模具类型"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)
    from app.services.db_service import create_mold_type
    try:
        mold_type = create_mold_type(body.code, body.name, body.sort_order)
        return JSONResponse({"code": 0, "message": "创建成功", "data": mold_type})
    except Exception as e:
        return JSONResponse({"code": 1, "message": str(e)}, status_code=400)


@api_router.put("/api/tech/mold-types/{type_id}")
def api_update_mold_type(request: Request, type_id: int, body: MoldTypeBody):
    """更新模具类型"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)
    from app.services.db_service import update_mold_type
    ok = update_mold_type(type_id, body.code, body.name, body.sort_order)
    if ok:
        return JSONResponse({"code": 0, "message": "更新成功"})
    return JSONResponse({"code": 1, "message": "更新失败"}, status_code=400)


@api_router.delete("/api/tech/mold-types/{type_id}")
def api_delete_mold_type(request: Request, type_id: int):
    """删除模具类型"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足"}, status_code=403)
    from app.services.db_service import delete_mold_type
    ok = delete_mold_type(type_id)
    if ok:
        return JSONResponse({"code": 0, "message": "删除成功"})
    return JSONResponse({"code": 1, "message": "删除失败，可能被使用中"}, status_code=400)


@api_router.get("/api/tech/pending-quotes")
def api_pending_tech_quotes(request: Request):
    """
    返回所有待技术审核的报价单列表（WAITING_FOR_TECH 状态）。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需设计工程师）"}, status_code=403)
    from app.services.db_service import get_pending_tech_quotes as _get_pending
    rows = _get_pending()
    return JSONResponse({"code": 0, "data": rows})


@api_router.get("/api/tech/quote/{quote_id}")
def api_get_quote_for_tech(request: Request, quote_id: int):
    """
    返回单条报价单详情（供技术参数填写页使用）。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需设计工程师）"}, status_code=403)
    from app.services.db_service import get_quote_by_id as _get_quote
    row = _get_quote(quote_id)
    if not row:
        return JSONResponse({"code": 1, "message": "报价单不存在"}, status_code=404)
    return JSONResponse({"code": 0, "data": row})


@api_router.put("/api/tech/quote/{quote_id}/params")
def api_update_tech_params(request: Request, quote_id: int, body: TechParamsBody):
    """
    填写/更新技术参数（T/W/P、模具费、穴数、吨位）。
    状态 WAITING_FOR_TECH → TECH_APPROVED。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 2:
        return JSONResponse({"code": 1, "message": "权限不足（需设计工程师）"}, status_code=403)
    from app.services.db_service import update_quote_tech_params as _update_params
    ok = _update_params(
        quote_id=quote_id,
        thickness=body.thickness,
        width=body.width,
        press_stroke=body.press_stroke,
        cavity_count=body.cavity_count,
        mold_cost=body.mold_cost,
        press_tonnage=body.press_tonnage,
        sdr_drawing_path=body.sdr_drawing_path,
        material_utilization=body.material_utilization,
        mold_life=body.mold_life,
        mold_type=body.mold_type,
        operator_id=user["id"],
    )
    if not ok:
        return JSONResponse({
            "code": 1,
            "message": "操作失败：报价单状态不允许技术参数填写（需 WAITING_FOR_TECH 状态）"
        }, status_code=400)
    return JSONResponse({"code": 0, "message": "技术参数已保存，报价单已提交技术审核通过"})


_SDR_UPLOAD_DIR = os.path.join("static", "uploads", "drawings")


def _get_drawing_subdir_by_quote(quote_id: int) -> str:
    """根据报价单 ID 获取图纸子目录。
    有客户 → 客户名/零件名/零件号/drawings
    无客户 → _unassigned/{quote_id}/drawings
    """
    import re
    def _safe(s):
        return re.sub(r'[\\/:*?"<>|]', '_', (s or '').strip())
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tc.name, p.internal_name, p.part_number
                    FROM quotes q
                    JOIN parts p ON q.part_id = p.id
                    LEFT JOIN tooling_customers tc ON COALESCE(q.customer_id, p.customer_id) = tc.id
                    WHERE q.id = %s
                """, (quote_id,))
                row = cur.fetchone()
                if not row:
                    return f"_unassigned/{quote_id}/drawings"
                customer_name, part_name, part_number = row
                if not customer_name:
                    return f"_unassigned/{quote_id}/drawings"
                segs = [_safe(customer_name), _safe(part_name or ''), _safe(part_number or str(quote_id))]
                return '/'.join(s for s in segs if s) + "/drawings"
    except Exception:
        return f"_unassigned/{quote_id}/drawings"


@api_router.post("/api/tech/quote/{quote_id}/sdr-upload")
async def api_sdr_upload(request: Request, quote_id: int, file: UploadFile = File(...)):
    """
    上传 SDR 分析图纸文件，按 客户名/零件名/零件号/drawings 分类存放。
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 1, "message": "未登录"}, status_code=401)
    if user.get("role_level", 0) < 4:
        return JSONResponse({"code": 1, "message": "权限不足（需设计工程师）"}, status_code=403)
    allowed = {'.pdf', '.dwg', '.dxf', '.png', '.jpg', '.jpeg'}
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in allowed:
        return JSONResponse({"code": 1, "message": "不支持的文件格式"}, status_code=400)
    try:
        subdir = _get_drawing_subdir_by_quote(quote_id)
        save_dir = os.path.join(_SDR_UPLOAD_DIR, subdir)
        os.makedirs(save_dir, exist_ok=True)
        save_name = f"SDR_{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(save_dir, save_name)
        content = await file.read()
        if len(content) > 20 * 1024 * 1024:
            return JSONResponse({"code": 1, "message": "文件超过 20MB 限制"}, status_code=400)
        with open(save_path, 'wb') as f:
            f.write(content)
        url_path = f"/static/uploads/drawings/{subdir}/{save_name}"
        return JSONResponse({"code": 0, "message": "上传成功", "data": {"path": url_path}})
    except Exception as e:
        return JSONResponse({"code": 1, "message": f"上传失败: {e}"}, status_code=500)
