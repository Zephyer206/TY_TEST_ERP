"""
app/api/qc.py
品质部路由 — QC 扫码 / 巡检 / OQC / 检验
前缀: /qc
"""
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.core.auth import get_current_user
from app.core.templates import templates
from app.services.db_service import (
    submit_qc_log,
    audit_qc_log,
    submit_inspection_log,
    get_qc_inspection_logs,
    get_today_patrol_logs,
    get_qc_today_summary,
    get_blocked_parts,
    unblock_part,
    get_oqc_reports,
    count_oqc_reports,
    create_oqc_report,
    approve_oqc_report,
    get_pending_parts_for_qc,
    get_qc_pass_rate_trend,
    get_major_qc_anomalies,
    get_qc_summary_stats,
    resolve_part_id_by_number,
)

router = APIRouter(prefix="/qc", tags=["qc"])


# ── QC 扫码 ──────────────────────────────────────────────────────
@router.get("/scan", response_class=HTMLResponse)
def qc_scan_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role_level"] < 3 and user["department"] not in ("qc", "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    blocked = get_blocked_parts()
    summary = get_qc_today_summary()
    return templates.TemplateResponse("qc/qc_scan.html", {
        "request": request, "user": user,
        "blocked_parts": blocked, "summary": summary,
    })


@router.post("/submit")
def qc_submit(request: Request,
              part_id: int = Form(...),
              qty_checked: int = Form(...),
              qty_passed: int = Form(...),
              qty_failed: int = Form(0),
              inspection_type: str = Form("first_piece"),
              result: str = Form("pass"),
              notes: str = Form(""),
              actual_date: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    submit_qc_log(part_id=part_id,
                  operator_id=user["id"],
                  qty_checked=qty_checked,
                  qty_passed=qty_passed,
                  qty_failed=qty_failed,
                  inspection_type=inspection_type,
                  result=result,
                  notes=notes,
                  actual_date=actual_date if actual_date else None)
    return RedirectResponse("/qc/scan", 303)


@router.post("/audit")
def qc_audit(request: Request,
             qc_log_id: int = Form(...),
             approved: bool = Form(True)):
    user = get_current_user(request)
    if not user or user["role_level"] < 5:
        raise HTTPException(status_code=403, detail="权限不足")
    audit_qc_log(qc_log_id, user["id"], approved)
    return RedirectResponse(request.headers.get("referer", "/qc/scan"), 303)


# ── 巡检记录 ─────────────────────────────────────────────────────
@router.get("/patrol", response_class=HTMLResponse)
def qc_patrol_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    logs = get_today_patrol_logs()
    return templates.TemplateResponse("qc/qc_scan.html", {
        "request": request, "user": user,
        "patrol_logs": logs,
    })


# ── OQC 出货检验 ─────────────────────────────────────────────────
@router.get("/oqc", response_class=HTMLResponse)
def qc_oqc_page(request: Request, status_filter: str = "pending"):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    reports = get_oqc_reports(status_filter=status_filter)
    pending_count = count_oqc_reports("pending_approve")
    return templates.TemplateResponse("qc/qc_scan.html", {
        "request": request, "user": user,
        "oqc_reports": reports,
        "oqc_pending_count": pending_count,
        "status_filter": status_filter,
    })


# ── 零件检验 ─────────────────────────────────────────────────────
@router.get("/inspection", response_class=HTMLResponse)
def qc_inspection_page(request: Request, page: int = 1):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    limit, offset = 50, (page - 1) * 50
    logs = get_qc_inspection_logs(limit=limit, offset=offset)
    return templates.TemplateResponse("qc/qc_inspection.html", {
        "request": request, "user": user,
        "logs": logs, "page": page,
    })


@router.post("/inspection/submit")
def qc_inspection_submit(request: Request,
                         part_id: int = Form(...),
                         inspection_type: str = Form(...),
                         qty_checked: int = Form(...),
                         qty_passed: int = Form(...),
                         result: str = Form("pass"),
                         notes: str = Form(""),
                         actual_date: str = Form("")):
    user = get_current_user(request)
    if not user or user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="权限不足")
    submit_inspection_log(part_id=part_id,
                          operator_id=user["id"],
                          inspection_type=inspection_type,
                          qty_checked=qty_checked,
                          qty_passed=qty_passed,
                          result=result,
                          notes=notes,
                          actual_date=actual_date if actual_date else None)
    return RedirectResponse("/qc/inspection", 303)


# ============================================================================
# 阶段五：首件 QA 检验 (/qc/first-piece)
# 对应 .cursorrules V3.2 §2.3 报工前必须校验 is_first_piece_required
# ============================================================================

@router.get("/first-piece", response_class=HTMLResponse)
def qa_first_piece_page(request: Request):
    """首件检验页面（质检 / 技术操作工终端）。"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("qc/qa_first_piece.html", {
        "request": request, "user": user,
    })
