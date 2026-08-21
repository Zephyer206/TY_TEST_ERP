"""After-sales installation kit archive and component annotation API."""

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.after_sales import (
    AfterSalesInstallationKit,
    AfterSalesKitChangeLog,
    AfterSalesKitComponent,
    AfterSalesKitComponentAnnotation,
)
from app.schemas.after_sales import (
    InstallationKitComponentResponse,
    InstallationKitComponentPairResponse,
    InstallationKitComponentUpdate,
    InstallationKitComponentStatusUpdate,
    InstallationKitDetail,
    InstallationKitHistoryResponse,
    InstallationKitListItem,
    InstallationKitPage,
    InstallationKitSummary,
    InstallationKitUpdate,
)

router = APIRouter(prefix="/after-sales/installation-kits", tags=["After sales"])

COMPONENT_STATUS_LABELS = {
    "external_purchase": "外购",
    "no_mold": "暂无模具",
    "developing": "开发中",
}


def _has_text(column):
    return and_(column.is_not(None), func.length(func.trim(column)) > 0)


def _status_is_complete(value: Optional[str]) -> bool:
    """Return True only for an explicit approval/OK conclusion.

    Excel uses date-bearing values such as ``PPAP send date:7.18`` and
    ``PPAP re_sent date:7.23`` to record submission activity, not approval.
    Unknown non-empty values remain incomplete until a conclusion is present.
    """
    normalized = (value or "").strip().lower()
    if not normalized:
        return False
    if any(token in normalized for token in (
        "not ok", "nok", "fail", "reject", "不通过", "未通过", "失败", "异常",
    )):
        return False
    if any(token in normalized for token in (
        "re_send", "re-send", "resend", "sending", "send date", "sent date",
        "estimated", "待补充", "待确认", "进行中", "pending",
    )):
        return False
    return any(token in normalized for token in (
        "ok", "approved", "approval date", "通过", "已通过",
    ))


def _status_complete_condition(column):
    """SQL counterpart of :func:`_status_is_complete` for list filtering."""
    submitted = or_(
        column.ilike("%re_send%"),
        column.ilike("%re-send%"),
        column.ilike("%resend%"),
        column.ilike("%sending%"),
        column.ilike("%send date%"),
        column.ilike("%sent date%"),
        column.ilike("%estimated%"),
        column.ilike("%待补充%"),
        column.ilike("%待确认%"),
        column.ilike("%进行中%"),
        column.ilike("%pending%"),
    )
    negative = or_(
        column.ilike("%not ok%"),
        column.ilike("%nok%"),
        column.ilike("%fail%"),
        column.ilike("%reject%"),
        column.ilike("%不通过%"),
        column.ilike("%未通过%"),
        column.ilike("%失败%"),
        column.ilike("%异常%"),
    )
    approved = or_(
        column.ilike("%ok%"),
        column.ilike("%approved%"),
        column.ilike("%approval date%"),
        column.ilike("%通过%"),
        column.ilike("%已通过%"),
    )
    return and_(_has_text(column), ~submitted, ~negative, approved)


def _documents_complete(kit: AfterSalesInstallationKit) -> bool:
    return all(_status_is_complete(value) for value in (
        kit.drawing_status,
        kit.sample_status,
        kit.ppap_status,
    ))


def _to_list_item(
    kit: AfterSalesInstallationKit,
    *,
    include_component_pairs: bool = False,
) -> InstallationKitListItem:
    return InstallationKitListItem(
        fmg_code=kit.fmg_code,
        description=kit.description,
        priority=kit.priority,
        d_code=kit.d_code,
        tianyue_pn=kit.tianyue_pn,
        ibi_spec=kit.ibi_spec,
        internal_kit_spec=kit.internal_kit_spec,
        component_pairs=_component_pairs(kit) if include_component_pairs else [],
        drawing_status=kit.drawing_status,
        sample_status=kit.sample_status,
        ppap_status=kit.ppap_status,
        document_complete=_documents_complete(kit),
        price=kit.price,
        price_mismatch=bool((kit.source_data or {}).get("price_mismatch", False)),
        currency=kit.currency,
        remark=kit.remark,
    )


def _component_response(component: Optional[AfterSalesKitComponent]) -> Optional[InstallationKitComponentResponse]:
    if component is None:
        return None
    return InstallationKitComponentResponse.model_validate(component, from_attributes=True)


def _is_non_part(component: Optional[AfterSalesKitComponent]) -> bool:
    if component is None:
        return False
    text = " ".join(filter(None, (component.raw_text, component.description))).lower()
    return "油脂包" in text or "说明书" in text


def _component_pairs(kit: AfterSalesInstallationKit) -> list[InstallationKitComponentPairResponse]:
    by_kind: dict[str, dict[int, AfterSalesKitComponent]] = defaultdict(dict)
    for component in kit.components:
        by_kind[component.source_kind][component.sequence] = component
    annotations = {item.sequence: item for item in kit.component_annotations}

    sequences = sorted(set(by_kind["ibi"]) | set(by_kind["internal"]))
    pairs: list[InstallationKitComponentPairResponse] = []
    for sequence in sequences:
        ibi = by_kind["ibi"].get(sequence)
        internal = by_kind["internal"].get(sequence)
        if ibi is not None and internal is not None:
            match_state = "paired"
        elif _is_non_part(ibi):
            match_state = "non_part"
        else:
            match_state = "unmatched"
        annotation = annotations.get(sequence) if match_state == "paired" else None
        pairs.append(
            InstallationKitComponentPairResponse(
                sequence=sequence,
                ibi=_component_response(ibi),
                internal=_component_response(internal),
                status=annotation.status if annotation else None,
                match_state=match_state,
                status_updated_at=annotation.updated_at if annotation else None,
            )
        )
    return pairs


@router.get("", response_model=InstallationKitPage)
async def list_installation_kits(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None, max_length=200),
    priority: Optional[int] = Query(default=None, ge=1, le=3),
    document_status: Optional[str] = Query(default=None, pattern="^(complete|incomplete)$"),
    price_status: Optional[str] = Query(default=None, pattern="^(confirmed|missing)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=100),
) -> InstallationKitPage:
    require_role(current_user, min_level=1)
    conditions = [AfterSalesInstallationKit.is_active.is_(True)]
    if search and (term := search.strip()):
        pattern = f"%{term}%"
        conditions.append(
            or_(
                AfterSalesInstallationKit.fmg_code.ilike(pattern),
                AfterSalesInstallationKit.description.ilike(pattern),
                AfterSalesInstallationKit.d_code.ilike(pattern),
                AfterSalesInstallationKit.tianyue_pn.ilike(pattern),
                AfterSalesInstallationKit.ibi_spec.ilike(pattern),
                AfterSalesInstallationKit.internal_kit_spec.ilike(pattern),
            )
        )
    if priority is not None:
        conditions.append(AfterSalesInstallationKit.priority == priority)

    complete_condition = and_(
        _status_complete_condition(AfterSalesInstallationKit.drawing_status),
        _status_complete_condition(AfterSalesInstallationKit.sample_status),
        _status_complete_condition(AfterSalesInstallationKit.ppap_status),
    )
    if document_status == "complete":
        conditions.append(complete_condition)
    elif document_status == "incomplete":
        conditions.append(~complete_condition)
    if price_status == "confirmed":
        conditions.append(AfterSalesInstallationKit.price.is_not(None))
    elif price_status == "missing":
        conditions.append(AfterSalesInstallationKit.price.is_(None))

    filtered_total = await db.scalar(
        select(func.count()).select_from(AfterSalesInstallationKit).where(*conditions)
    )
    result = await db.execute(
        select(AfterSalesInstallationKit)
        .where(*conditions)
        .options(
            selectinload(AfterSalesInstallationKit.components),
            selectinload(AfterSalesInstallationKit.component_annotations),
        )
        .order_by(
            AfterSalesInstallationKit.priority.asc().nullslast(),
            AfterSalesInstallationKit.source_item_no.asc().nullslast(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    kits = list(result.scalars())

    active_condition = AfterSalesInstallationKit.is_active.is_(True)
    total_records = await db.scalar(
        select(func.count()).select_from(AfterSalesInstallationKit).where(active_condition)
    )
    priced_records = await db.scalar(
        select(func.count())
        .select_from(AfterSalesInstallationKit)
        .where(active_condition, AfterSalesInstallationKit.price.is_not(None))
    )
    drawing_ok_records = await db.scalar(
        select(func.count())
        .select_from(AfterSalesInstallationKit)
        .where(active_condition, _status_complete_condition(AfterSalesInstallationKit.drawing_status))
    )
    sample_ok_records = await db.scalar(
        select(func.count())
        .select_from(AfterSalesInstallationKit)
        .where(active_condition, _status_complete_condition(AfterSalesInstallationKit.sample_status))
    )
    ppap_ok_records = await db.scalar(
        select(func.count())
        .select_from(AfterSalesInstallationKit)
        .where(active_condition, _status_complete_condition(AfterSalesInstallationKit.ppap_status))
    )
    total_count = total_records or 0
    return InstallationKitPage(
        items=[_to_list_item(kit, include_component_pairs=True) for kit in kits],
        total=filtered_total or 0,
        page=page,
        page_size=page_size,
        summary=InstallationKitSummary(
            total_records=total_count,
            priced_records=priced_records or 0,
            missing_price_records=total_count - (priced_records or 0),
            drawing_ok_records=drawing_ok_records or 0,
            sample_ok_records=sample_ok_records or 0,
            ppap_ok_records=ppap_ok_records or 0,
        ),
    )


@router.get("/{fmg_code}", response_model=InstallationKitDetail)
async def get_installation_kit(
    fmg_code: str,
    db: DbSession,
    current_user: CurrentUser,
) -> InstallationKitDetail:
    require_role(current_user, min_level=1)
    result = await db.execute(
        select(AfterSalesInstallationKit)
        .where(
            AfterSalesInstallationKit.fmg_code == fmg_code,
            AfterSalesInstallationKit.is_active.is_(True),
        )
        .options(
            selectinload(AfterSalesInstallationKit.components),
            selectinload(AfterSalesInstallationKit.change_logs),
            selectinload(AfterSalesInstallationKit.component_annotations),
        )
    )
    kit = result.scalar_one_or_none()
    if not kit:
        raise HTTPException(status_code=404, detail="安装包不存在")

    base = _to_list_item(kit, include_component_pairs=True).model_dump()
    return InstallationKitDetail(
        **base,
        components=[
            InstallationKitComponentResponse.model_validate(component, from_attributes=True)
            for component in sorted(
                kit.components,
                key=lambda item: (0 if item.source_kind == "ibi" else 1, item.sequence),
            )
        ],
        change_history=[
            InstallationKitHistoryResponse.model_validate(history, from_attributes=True)
            for history in sorted(kit.change_logs, key=lambda item: item.created_at, reverse=True)
        ],
        created_at=kit.created_at,
        updated_at=kit.updated_at,
    )


def _audit_value(value):
    """Convert Decimal/datetime values to JSON-safe audit values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@router.put("/{fmg_code}", response_model=InstallationKitDetail)
async def update_installation_kit(
    fmg_code: str,
    payload: InstallationKitUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> InstallationKitDetail:
    """Update every editable business field shown in the dossier."""
    require_role(current_user, min_level=2)
    result = await db.execute(
        select(AfterSalesInstallationKit)
        .where(
            AfterSalesInstallationKit.fmg_code == fmg_code,
            AfterSalesInstallationKit.is_active.is_(True),
        )
        .options(
            selectinload(AfterSalesInstallationKit.components),
            selectinload(AfterSalesInstallationKit.change_logs),
            selectinload(AfterSalesInstallationKit.component_annotations),
        )
    )
    kit = result.scalar_one_or_none()
    if not kit:
        raise HTTPException(status_code=404, detail="安装包不存在")

    updates = payload.model_dump(exclude_unset=True)
    if "fmg_code" in updates:
        next_code = (updates["fmg_code"] or "").strip()
        if not next_code:
            raise HTTPException(status_code=400, detail="FMG CODE 不能为空")
        duplicate = await db.scalar(
            select(AfterSalesInstallationKit.id).where(
                AfterSalesInstallationKit.fmg_code == next_code,
                AfterSalesInstallationKit.id != kit.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="FMG CODE 已存在")
        updates["fmg_code"] = next_code
    if "currency" in updates and updates["currency"] is not None:
        updates["currency"] = updates["currency"].strip().upper()
        if len(updates["currency"]) != 3:
            raise HTTPException(status_code=400, detail="币种必须为 3 位代码")

    changed_fields: list[str] = []
    change_data: dict[str, dict[str, object]] = {}
    for field, next_value in updates.items():
        previous_value = getattr(kit, field)
        if previous_value == next_value:
            continue
        setattr(kit, field, next_value)
        changed_fields.append(field)
        change_data[field] = {
            "before": _audit_value(previous_value),
            "after": _audit_value(next_value),
        }

    if changed_fields:
        db.add(
            AfterSalesKitChangeLog(
                kit_id=kit.id,
                actor_user_id=current_user.id,
                action="kit_updated",
                summary=f"更新安装包信息：{', '.join(changed_fields)}",
                changed_fields=changed_fields,
                change_data=change_data,
            )
        )
        await db.flush()
        await db.refresh(kit)

    return await get_installation_kit(fmg_code=kit.fmg_code, db=db, current_user=current_user)


@router.put(
    "/{fmg_code}/components/{source_kind}/{sequence}",
    response_model=InstallationKitComponentResponse,
)
async def update_installation_kit_component(
    fmg_code: str,
    source_kind: str,
    sequence: int,
    payload: InstallationKitComponentUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> InstallationKitComponentResponse:
    """Update the displayed values for one IBI or internal component."""
    require_role(current_user, min_level=2)
    if source_kind not in {"ibi", "internal"}:
        raise HTTPException(status_code=400, detail="组成类型必须为 ibi 或 internal")
    result = await db.execute(
        select(AfterSalesInstallationKit)
        .where(
            AfterSalesInstallationKit.fmg_code == fmg_code,
            AfterSalesInstallationKit.is_active.is_(True),
        )
    )
    kit = result.scalar_one_or_none()
    if not kit:
        raise HTTPException(status_code=404, detail="安装包不存在")
    component = await db.scalar(
        select(AfterSalesKitComponent).where(
            AfterSalesKitComponent.kit_id == kit.id,
            AfterSalesKitComponent.source_kind == source_kind,
            AfterSalesKitComponent.sequence == sequence,
        )
    )
    if component is None:
        raise HTTPException(status_code=404, detail="组成项不存在")

    updates = payload.model_dump(exclude_unset=True)
    next_sequence = updates.get("sequence", sequence)
    if "raw_text" in updates and not (updates["raw_text"] or "").strip():
        raise HTTPException(status_code=400, detail="组成原始文本不能为空")
    if next_sequence != sequence:
        duplicate = await db.scalar(
            select(AfterSalesKitComponent.id).where(
                AfterSalesKitComponent.kit_id == kit.id,
                AfterSalesKitComponent.source_kind == source_kind,
                AfterSalesKitComponent.sequence == next_sequence,
                AfterSalesKitComponent.id != component.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="同一组成类型下顺序已存在")

    changed_fields: list[str] = []
    change_data: dict[str, dict[str, object]] = {}
    for field, next_value in updates.items():
        previous_value = getattr(component, field)
        if previous_value == next_value:
            continue
        setattr(component, field, next_value)
        changed_fields.append(f"component:{source_kind}:{field}")
        change_data[f"component:{source_kind}:{field}"] = {
            "before": _audit_value(previous_value),
            "after": _audit_value(next_value),
        }
    if changed_fields:
        db.add(
            AfterSalesKitChangeLog(
                kit_id=kit.id,
                actor_user_id=current_user.id,
                action="component_updated",
                summary=f"更新{source_kind}组成：第 {component.sequence} 项",
                changed_fields=changed_fields,
                change_data=change_data,
            )
        )
        await db.flush()

    return InstallationKitComponentResponse.model_validate(component, from_attributes=True)


@router.put("/{fmg_code}/component-pairs/{sequence}", response_model=InstallationKitComponentPairResponse)
async def update_component_pair_status(
    db: DbSession,
    current_user: CurrentUser,
    fmg_code: str,
    sequence: int = Path(..., ge=1),
    payload: InstallationKitComponentStatusUpdate = Body(...),
) -> InstallationKitComponentPairResponse:
    """Set or clear the status for one IBI/Tianyue component pair."""
    require_role(current_user, min_level=1)
    result = await db.execute(
        select(AfterSalesInstallationKit)
        .where(
            AfterSalesInstallationKit.fmg_code == fmg_code,
            AfterSalesInstallationKit.is_active.is_(True),
        )
        .options(
            selectinload(AfterSalesInstallationKit.components),
            selectinload(AfterSalesInstallationKit.component_annotations),
        )
    )
    kit = result.scalar_one_or_none()
    if not kit:
        raise HTTPException(status_code=404, detail="安装包不存在")

    pairs = _component_pairs(kit)
    pair = next((item for item in pairs if item.sequence == sequence), None)
    if pair is None:
        raise HTTPException(status_code=404, detail="组成项不存在")
    if pair.match_state != "paired":
        raise HTTPException(status_code=409, detail="只有一一对应的零件对可以标注状态")

    existing = next(
        (item for item in kit.component_annotations if item.sequence == sequence),
        None,
    )
    previous_status = existing.status if existing else None
    next_status = payload.status
    if previous_status != next_status:
        if next_status is None:
            if existing is not None:
                kit.component_annotations.remove(existing)
                await db.delete(existing)
        elif existing is not None:
            existing.status = next_status
        else:
            kit.component_annotations.append(
                AfterSalesKitComponentAnnotation(kit_id=kit.id, sequence=sequence, status=next_status)
            )
        db.add(
            AfterSalesKitChangeLog(
                kit_id=kit.id,
                actor_user_id=current_user.id,
                action="component_status_updated",
                summary=(
                    f"第 {sequence} 对组成标注为 {COMPONENT_STATUS_LABELS[next_status]}"
                    if next_status
                    else f"清除第 {sequence} 对组成标注"
                ),
                changed_fields=[f"component_pair:{sequence}", "status"],
                change_data={
                    f"component_pair:{sequence}.status": {
                        "before": previous_status,
                        "after": next_status,
                    }
                },
            )
        )
        await db.flush()

    return next(item for item in _component_pairs(kit) if item.sequence == sequence)
