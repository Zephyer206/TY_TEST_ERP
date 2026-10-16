"""Customer-first gaibo after-sales APIs."""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Iterable, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import Boolean, Date, Numeric, Text, and_, case, cast, exists, false, func, literal, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.gaibo import (
    GaiboAfterSalesCustomer,
    GaiboChangeLog,
    GaiboCustomerRequirement,
    GaiboCustomerWorkspace,
    GaiboDocumentStatus,
    GaiboDrawing,
    GaiboInstallationPackage,
    GaiboPackageItem,
    GaiboProcessRoute,
    GaiboProcessStep,
    GaiboSinglePart,
    GaiboViewPreference,
)
from app.schemas.gaibo import (
    GaiboChangeLogResponse,
    GaiboDocumentEventResponse,
    GaiboDocumentStatusCreate,
    GaiboDocumentStatusResponse,
    GaiboDocumentStatusUpdate,
    GaiboFilterOption,
    GaiboFilterOptionsResponse,
    GaiboDrawingCreate,
    GaiboDrawingResponse,
    GaiboDrawingUpdate,
    GaiboPackageCreate,
    GaiboPackageDetailResponse,
    GaiboPackageItemCreate,
    GaiboPackageItemResponse,
    GaiboPackageItemUpdate,
    GaiboPackageResponse,
    GaiboPackageUpdate,
    GaiboProcessRouteCreate,
    GaiboProcessRouteResponse,
    GaiboProcessRouteUpdate,
    GaiboProcessStepResponse,
    GaiboRequirementCreate,
    GaiboRequirementDossierUpdate,
    GaiboRequirementDetailResponse,
    GaiboRequirementResponse,
    GaiboRequirementUpdate,
    GaiboSearchItem,
    GaiboSearchPage,
    GaiboSearchSummary,
    GaiboSinglePartCreate,
    GaiboSinglePartResponse,
    GaiboSinglePartUpdate,
    GaiboWorkspaceCreate,
    GaiboWorkspaceColumnConfigResponse,
    GaiboWorkspaceColumnConfigUpdate,
    GaiboWorkspaceResponse,
    GaiboWorkspaceUpdate,
    GaiboWorkspaceViewConfig,
    GaiboCustomFieldDefinition,
    GaiboViewPreferenceResponse,
    GaiboViewPreferenceUpdate,
)
from app.services.after_sales_service import (
    GaiboValidationError,
    add_change_log,
    changed_values,
    creation_change_data,
    normalize_currency,
    require_text,
    validate_package_item_reference,
)
from app.services.after_sales_document_events import (
    append_status_event,
    document_events,
    latest_document_event,
)

router = APIRouter(prefix="/after-sales/gaibo", tags=["Gaibo after sales"])


def _document_response(document: GaiboDocumentStatus) -> GaiboDocumentStatusResponse:
    """Serialize a document status together with its process timeline."""
    payload = GaiboDocumentStatusResponse.model_validate(document, from_attributes=True).model_dump()
    events = document_events(document.source_data, document_type=document.document_type, remark=document.remark)
    payload["events"] = events
    payload["latest_event"] = events[-1] if events else None
    return GaiboDocumentStatusResponse(**payload)


def _latest_event_for_row(document: GaiboDocumentStatus | None) -> GaiboDocumentEventResponse | None:
    if document is None:
        return None
    event = latest_document_event(document.source_data, document_type=document.document_type, remark=document.remark)
    return GaiboDocumentEventResponse(**event) if event else None


def _ordered_documents(documents: Iterable[GaiboDocumentStatus]) -> list[GaiboDocumentStatus]:
    order = {"drawing": 0, "sample": 1, "ppap": 2}
    return sorted(documents, key=lambda document: (order.get(document.document_type, 99), document.id))


CORE_COLUMN_DEFAULTS: dict[str, dict[str, object]] = {
    "type": {"label": "类型", "width": 66, "visible": True},
    "workspace": {"label": "客户", "width": 100, "visible": True},
    "primaryNumber": {"label": "FMG CODE / 客户件号", "width": 132, "visible": True},
    "priority": {"label": "优先级", "width": 62, "visible": True},
    "dCode": {"label": "D code", "width": 78, "visible": True},
    "tianyuePn": {"label": "天悦 PN", "width": 90, "visible": True},
    "internalComposition": {"label": "天越内部组成", "width": 168, "visible": True},
    "ibi": {"label": "IBI", "width": 152, "visible": True},
    "status": {"label": "安装包状态", "width": 156, "visible": True},
    "price": {"label": "价格（FCA USD）", "width": 104, "visible": True},
    "remark": {"label": "备注", "width": 120, "visible": True},
    "updatedAt": {"label": "更新时间", "width": 140, "visible": False},
}
CORE_COLUMN_KEYS = tuple(CORE_COLUMN_DEFAULTS)
CORE_SORT_KEYS = {"primaryNumber", "priority", "dCode", "tianyuePn", "price", "updatedAt"}


_changed_values = changed_values
_add_change_log = add_change_log


def _workspace_custom_fields(workspace: GaiboCustomerWorkspace) -> list[GaiboCustomFieldDefinition]:
    raw = workspace.extra_field_definitions or {}
    columns = raw.get("columns", []) if isinstance(raw, dict) else []
    fields: list[GaiboCustomFieldDefinition] = []
    for value in columns if isinstance(columns, list) else []:
        try:
            fields.append(GaiboCustomFieldDefinition.model_validate(value))
        except ValidationError:
            continue
    return sorted(fields, key=lambda field: (field.sequence, field.key))


def _default_workspace_view_config(
    custom_fields: list[GaiboCustomFieldDefinition],
) -> GaiboWorkspaceViewConfig:
    active_custom = [field for field in custom_fields if field.is_active]
    order = [*CORE_COLUMN_KEYS, *(field.key for field in active_custom)]
    visible = [
        key
        for key, definition in CORE_COLUMN_DEFAULTS.items()
        if definition["visible"] is True
    ]
    visible.extend(field.key for field in active_custom if field.default_visible)
    widths = {
        **{key: int(definition["width"]) for key, definition in CORE_COLUMN_DEFAULTS.items()},
        **{field.key: field.width for field in active_custom},
    }
    return GaiboWorkspaceViewConfig(
        visible=visible,
        order=order,
        widths=widths,
        density="compact",
        sortKey="updatedAt",
        sortOrder="desc",
    )


def _normalize_workspace_view_config(
    value: GaiboWorkspaceViewConfig | dict[str, object] | None,
    custom_fields: list[GaiboCustomFieldDefinition],
) -> GaiboWorkspaceViewConfig:
    defaults = _default_workspace_view_config(custom_fields)
    if not value:
        return defaults
    candidate = value if isinstance(value, GaiboWorkspaceViewConfig) else GaiboWorkspaceViewConfig.model_validate(value)
    active_custom = [field for field in custom_fields if field.is_active]
    allowed = {*CORE_COLUMN_KEYS, *(field.key for field in active_custom)}
    order = list(dict.fromkeys([*(key for key in candidate.order if key in allowed), *defaults.order]))
    visible = list(dict.fromkeys(key for key in candidate.visible if key in allowed))
    if "primaryNumber" not in visible:
        visible.insert(0, "primaryNumber")
    widths = dict(defaults.widths)
    widths.update({key: width for key, width in candidate.widths.items() if key in allowed})
    sort_key = candidate.sortKey if candidate.sortKey in CORE_SORT_KEYS or candidate.sortKey in allowed - set(CORE_COLUMN_KEYS) else defaults.sortKey
    return GaiboWorkspaceViewConfig(
        visible=visible,
        order=order,
        widths=widths,
        density=candidate.density,
        sortKey=sort_key,
        sortOrder=candidate.sortOrder,
    )


def _normalize_field_labels(values: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in values.items():
        if key not in CORE_COLUMN_DEFAULTS:
            raise HTTPException(status_code=400, detail=f"不支持修改字段 {key} 的显示名称")
        label = value.strip()
        if not label or len(label) > 50:
            raise HTTPException(status_code=400, detail="字段显示名称必须为 1 到 50 个字符")
        normalized[key] = label
    return normalized


def _normalize_detail_section_labels(values: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in values.items():
        if key != "core_fields":
            raise HTTPException(status_code=400, detail=f"不支持修改详情标题 {key}")
        label = value.strip()
        if not label or len(label) > 50:
            raise HTTPException(status_code=400, detail="详情标题必须为 1 到 50 个字符")
        normalized[key] = label
    return normalized


def _parse_column_filters(raw: str | None) -> dict[str, str | list[str]]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="列筛选条件格式无效")
    if not isinstance(value, dict) or len(value) > 40:
        raise HTTPException(status_code=400, detail="列筛选条件格式无效")
    parsed: dict[str, str | list[str]] = {}
    for key, item in value.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        if isinstance(item, list):
            values = [str(value).strip() for value in item if str(value).strip()][:40]
            if values:
                parsed[normalized_key] = values
        elif str(item).strip():
            parsed[normalized_key] = str(item).strip()
    return parsed


def _column_config_response(workspace: GaiboCustomerWorkspace) -> GaiboWorkspaceColumnConfigResponse:
    custom_fields = _workspace_custom_fields(workspace)
    view_config = _normalize_workspace_view_config(workspace.default_view_config, custom_fields)
    field_labels = {
        key: value.strip()
        for key, value in (workspace.field_labels or {}).items()
        if key in CORE_COLUMN_DEFAULTS and isinstance(value, str) and value.strip() and len(value.strip()) <= 50
    }
    raw_extra = workspace.extra_field_definitions or {}
    raw_detail_labels = raw_extra.get("detail_section_labels", {}) if isinstance(raw_extra, dict) else {}
    detail_section_labels = {
        key: value.strip()
        for key, value in raw_detail_labels.items()
        if key == "core_fields" and isinstance(value, str) and value.strip() and len(value.strip()) <= 50
    }
    return GaiboWorkspaceColumnConfigResponse(
        workspace_id=workspace.id,
        version=workspace.column_config_version,
        field_labels=field_labels,
        detail_section_labels=detail_section_labels,
        custom_fields=custom_fields,
        default_view_config=view_config,
    )


def _workspace_response(workspace: GaiboCustomerWorkspace) -> GaiboWorkspaceResponse:
    customer = workspace.after_sales_customer
    return GaiboWorkspaceResponse(
        id=workspace.id,
        after_sales_customer_id=workspace.after_sales_customer_id,
        after_sales_customer_name=customer.name,
        slug=workspace.slug,
        display_name=workspace.display_name,
        is_active=workspace.is_active,
        field_labels=workspace.field_labels or {},
        extra_field_definitions=workspace.extra_field_definitions or {},
        default_view_config=workspace.default_view_config or {},
        column_config_version=workspace.column_config_version,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


def _validate_extra_data(
    workspace: GaiboCustomerWorkspace,
    values: dict[str, object],
    *,
    record_type: str,
    existing: dict[str, object] | None = None,
) -> dict[str, object]:
    if len(values) > 24:
        raise HTTPException(status_code=400, detail="客户扩展字段不能超过 24 项")
    allowed = {
        field.key: field
        for field in _workspace_custom_fields(workspace)
        if field.is_active and field.scope in ("both", record_type)
    }
    merged = dict(existing or {})
    for key, value in values.items():
        field = allowed.get(key)
        if field is None:
            raise HTTPException(status_code=400, detail=f"扩展字段 {key} 不属于当前客户或记录类型")
        if value is None or value == "":
            merged[key] = None
            continue
        if field.data_type == "text":
            text_value = str(value).strip()
            if len(text_value) > 2000:
                raise HTTPException(status_code=400, detail=f"{field.label}不能超过 2000 个字符")
            merged[key] = text_value
        elif field.data_type == "number":
            try:
                number = Decimal(str(value))
            except (InvalidOperation, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"{field.label}必须是数字") from exc
            merged[key] = int(number) if number == number.to_integral_value() else float(number)
        elif field.data_type == "date":
            try:
                merged[key] = date.fromisoformat(str(value)[:10]).isoformat()
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"{field.label}必须是有效日期") from exc
        elif field.data_type == "boolean":
            if not isinstance(value, bool):
                raise HTTPException(status_code=400, detail=f"{field.label}必须是是/否值")
            merged[key] = value
        else:
            option = str(value).strip()
            if option not in field.options:
                raise HTTPException(status_code=400, detail=f"{field.label}不在允许的选项中")
            merged[key] = option
    return merged


@router.get("/view-preferences/{view_key}", response_model=GaiboViewPreferenceResponse)
async def get_view_preference(
    view_key: str,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboViewPreferenceResponse:
    require_role(current_user, min_level=1)
    normalized_key = view_key.strip()
    if not normalized_key or len(normalized_key) > 100:
        raise HTTPException(status_code=400, detail="视图标识无效")
    item = await db.scalar(
        select(GaiboViewPreference).where(
            GaiboViewPreference.user_id == current_user.id,
            GaiboViewPreference.view_key == normalized_key,
        )
    )
    if item is None:
        return GaiboViewPreferenceResponse(view_key=normalized_key, config={})
    return GaiboViewPreferenceResponse.model_validate(item, from_attributes=True)


@router.put("/view-preferences/{view_key}", response_model=GaiboViewPreferenceResponse)
async def save_view_preference(
    view_key: str,
    payload: GaiboViewPreferenceUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboViewPreferenceResponse:
    require_role(current_user, min_level=1)
    normalized_key = view_key.strip()
    if not normalized_key or len(normalized_key) > 100:
        raise HTTPException(status_code=400, detail="视图标识无效")
    item = await db.scalar(
        select(GaiboViewPreference).where(
            GaiboViewPreference.user_id == current_user.id,
            GaiboViewPreference.view_key == normalized_key,
        )
    )
    if item is None:
        item = GaiboViewPreference(
            user_id=current_user.id,
            view_key=normalized_key,
            config=payload.config,
        )
        db.add(item)
    else:
        item.config = payload.config
    await _flush_or_conflict(db, "视图设置保存冲突，请重试")
    return GaiboViewPreferenceResponse.model_validate(item, from_attributes=True)


def _join_package_display_values(values: Iterable[object]) -> str | None:
    """Keep package composition visible without duplicating repeated values."""
    joined: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip() if value is not None else ""
        if not text or text in seen:
            continue
        seen.add(text)
        joined.append(text)
    return " · ".join(joined) or None


def _aggregate_package_display_values(
    rows: Iterable[tuple[object, object, object]],
) -> dict[int, tuple[str | None, str | None]]:
    """Build ordered list-cell values from package item rows."""
    grouped: dict[int, dict[str, list[object]]] = {}
    for package_id, ibi, internal in rows:
        values = grouped.setdefault(int(package_id), {"ibi": [], "internal": []})
        values["ibi"].append(ibi)
        values["internal"].append(internal)
    return {
        package_id: (
            _join_package_display_values(values["ibi"]),
            _join_package_display_values(values["internal"]),
        )
        for package_id, values in grouped.items()
    }


def _currency_or_400(value: str | None) -> str | None:
    try:
        return normalize_currency(value)
    except GaiboValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _required_currency_or_400(value: str | None) -> str:
    normalized = _currency_or_400(value)
    if normalized is None:
        raise HTTPException(status_code=400, detail="币种不能为空")
    return normalized


def _text_or_400(value: str | None, label: str) -> str:
    try:
        return require_text(value, label)
    except GaiboValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _normalize_required_text_updates(updates: dict[str, object], labels: dict[str, str]) -> None:
    """Reject explicit null or blank values before they reach a NOT NULL column."""
    for field, label in labels.items():
        if field in updates:
            updates[field] = _text_or_400(updates[field], label)  # type: ignore[arg-type]


def _normalize_requirement_updates(updates: dict[str, object]) -> None:
    if "currency" in updates:
        updates["currency"] = _required_currency_or_400(updates["currency"])  # type: ignore[arg-type]
    if "price" in updates and updates["price"] is None:
        raise HTTPException(status_code=400, detail="价格不能为空")
    _normalize_required_text_updates(
        updates,
        {
            "customer_part_number": "客户件号",
            "ibi": "IBI",
            "tianyue_internal_composition": "天越内部组成",
        },
    )


async def _flush_or_conflict(db, detail: str = "数据与现有售后档案冲突，请检查重复的编号、版本或资料类型") -> None:
    """Convert database uniqueness failures into a recoverable business response."""
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


def _check_updated_at(item, expected_updated_at: datetime | None) -> None:
    if expected_updated_at is None:
        return
    actual = item.updated_at
    if actual is None:
        raise HTTPException(status_code=409, detail="档案版本已变化，请刷新后重试")
    expected = expected_updated_at.replace(tzinfo=None)
    actual_naive = actual.replace(tzinfo=None)
    if actual_naive != expected:
        raise HTTPException(status_code=409, detail="档案已被其他用户更新，请刷新后重试")


async def _get_requirement_detail(db, requirement_id: int) -> GaiboCustomerRequirement | None:
    result = await db.execute(
        select(GaiboCustomerRequirement)
        .options(
            selectinload(GaiboCustomerRequirement.single_part).selectinload(GaiboSinglePart.requirements),
            selectinload(GaiboCustomerRequirement.drawings),
            selectinload(GaiboCustomerRequirement.process_routes).selectinload(GaiboProcessRoute.steps),
            selectinload(GaiboCustomerRequirement.documents),
        )
        .where(GaiboCustomerRequirement.id == requirement_id, GaiboCustomerRequirement.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def _get_package_detail(db, package_id: int) -> GaiboInstallationPackage | None:
    result = await db.execute(
        select(GaiboInstallationPackage)
        .options(
            selectinload(GaiboInstallationPackage.items),
            selectinload(GaiboInstallationPackage.documents),
        )
        .where(GaiboInstallationPackage.id == package_id, GaiboInstallationPackage.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def _get_package_change_history(db, package: GaiboInstallationPackage) -> list[GaiboChangeLog]:
    """Return history owned directly by one installation package.

    A package can own its own record, package items, and package-level document
    statuses. Requirement records linked by an item intentionally remain in the
    single-part archive, so their history is not included here.
    """
    package_item_ids = select(GaiboPackageItem.id).where(GaiboPackageItem.package_id == package.id)
    package_document_ids = select(GaiboDocumentStatus.id).where(GaiboDocumentStatus.package_id == package.id)
    history = await db.scalars(
        select(GaiboChangeLog)
        .where(
            GaiboChangeLog.workspace_id == package.workspace_id,
            or_(
                and_(
                    GaiboChangeLog.entity_type == "package",
                    GaiboChangeLog.entity_id == package.id,
                ),
                and_(
                    GaiboChangeLog.entity_type == "package_item",
                    GaiboChangeLog.entity_id.in_(package_item_ids),
                ),
                and_(
                    GaiboChangeLog.entity_type == "document",
                    GaiboChangeLog.entity_id.in_(package_document_ids),
                ),
            ),
        )
        .order_by(GaiboChangeLog.created_at.desc(), GaiboChangeLog.id.desc())
    )
    return list(history)


async def _get_requirement_change_history(
    db,
    requirement: GaiboCustomerRequirement,
) -> list[GaiboChangeLog]:
    """Return the complete, customer-scoped dossier history for one requirement."""
    drawing_ids = select(GaiboDrawing.id).where(GaiboDrawing.requirement_id == requirement.id)
    route_ids = select(GaiboProcessRoute.id).where(GaiboProcessRoute.requirement_id == requirement.id)
    document_ids = select(GaiboDocumentStatus.id).where(GaiboDocumentStatus.requirement_id == requirement.id)
    history = await db.scalars(
        select(GaiboChangeLog)
        .where(
            GaiboChangeLog.workspace_id == requirement.workspace_id,
            or_(
                and_(
                    GaiboChangeLog.entity_type == "requirement",
                    GaiboChangeLog.entity_id == requirement.id,
                ),
                and_(
                    GaiboChangeLog.entity_type == "single_part",
                    GaiboChangeLog.entity_id == requirement.single_part_id,
                ),
                and_(
                    GaiboChangeLog.entity_type == "drawing",
                    GaiboChangeLog.entity_id.in_(drawing_ids),
                ),
                and_(
                    GaiboChangeLog.entity_type == "process_route",
                    GaiboChangeLog.entity_id.in_(route_ids),
                ),
                and_(
                    GaiboChangeLog.entity_type == "document",
                    GaiboChangeLog.entity_id.in_(document_ids),
                ),
            ),
        )
        .order_by(GaiboChangeLog.created_at.desc(), GaiboChangeLog.id.desc())
    )
    return list(history)


async def _demote_current_routes(
    db,
    *,
    requirement_id: int,
    workspace_id: int,
    except_route_id: int | None,
    actor_user_id: int,
) -> None:
    """Clear the prior current route before another route becomes current."""
    existing = await db.scalars(
        select(GaiboProcessRoute).where(
            GaiboProcessRoute.requirement_id == requirement_id,
            GaiboProcessRoute.is_current.is_(True),
        )
    )
    changed = False
    for route in existing:
        if route.id == except_route_id:
            continue
        route.is_current = False
        _add_change_log(
            db,
            workspace_id=workspace_id,
            entity_type="process_route",
            entity_id=route.id,
            action="process_route_current_replaced",
            changed_fields=["is_current"],
            change_data={"is_current": {"before": True, "after": False}},
            actor_user_id=actor_user_id,
            summary="已由新的当前工艺版本替换",
        )
        changed = True
    if changed:
        # PostgreSQL's partial unique index requires this update to land before
        # inserting or promoting the next current route.
        await db.flush()


@router.get("/workspaces", response_model=list[GaiboWorkspaceResponse])
async def list_workspaces(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None, max_length=200),
    include_inactive: bool = False,
) -> list[GaiboWorkspaceResponse]:
    require_role(current_user, min_level=1)
    conditions = [] if include_inactive else [GaiboCustomerWorkspace.is_active.is_(True)]
    if search and (term := search.strip()):
        pattern = f"%{term}%"
        conditions.append(or_(GaiboCustomerWorkspace.display_name.ilike(pattern), GaiboCustomerWorkspace.slug.ilike(pattern)))
    result = await db.execute(
        select(GaiboCustomerWorkspace)
        .options(selectinload(GaiboCustomerWorkspace.after_sales_customer))
        .where(*conditions)
        .order_by(GaiboCustomerWorkspace.display_name.asc())
    )
    return [_workspace_response(item) for item in result.scalars()]


@router.post("/workspaces", response_model=GaiboWorkspaceResponse, status_code=201)
async def create_workspace(
    payload: GaiboWorkspaceCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboWorkspaceResponse:
    require_role(current_user, min_level=4)
    payload_data = payload.model_dump()
    customer_name = payload_data.pop("after_sales_customer_name").strip()
    payload_data["slug"] = payload_data["slug"].strip()
    payload_data["display_name"] = payload_data["display_name"].strip()
    if not customer_name or not payload_data["slug"] or not payload_data["display_name"]:
        raise HTTPException(status_code=400, detail="售后客户名称、工作区名称和标识不能为空")
    existing_customer = await db.scalar(
        select(GaiboAfterSalesCustomer).where(GaiboAfterSalesCustomer.name == customer_name)
    )
    if existing_customer:
        raise HTTPException(status_code=409, detail="该售后客户已存在")
    customer = GaiboAfterSalesCustomer(name=customer_name)
    db.add(customer)
    await _flush_or_conflict(db, "售后客户名称已存在")
    payload_data["after_sales_customer_id"] = customer.id
    workspace = GaiboCustomerWorkspace(**payload_data)
    db.add(workspace)
    await _flush_or_conflict(db, "客户工作区标识已存在")
    _add_change_log(
        db,
        workspace_id=workspace.id,
        entity_type="workspace",
        entity_id=workspace.id,
        action="workspace_created",
        changed_fields=list(payload_data),
        change_data=creation_change_data(payload_data),
        actor_user_id=current_user.id,
    )
    await db.refresh(workspace, attribute_names=["after_sales_customer"])
    return _workspace_response(workspace)


@router.patch("/workspaces/{workspace_id}", response_model=GaiboWorkspaceResponse)
async def update_workspace(
    workspace_id: int,
    payload: GaiboWorkspaceUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboWorkspaceResponse:
    require_role(current_user, min_level=4)
    workspace = await db.scalar(
        select(GaiboCustomerWorkspace)
        .options(selectinload(GaiboCustomerWorkspace.after_sales_customer))
        .where(GaiboCustomerWorkspace.id == workspace_id)
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="售后客户工作区不存在")
    updates = payload.model_dump(exclude_unset=True)
    if "slug" in updates:
        updates["slug"] = updates["slug"].strip()
    if "display_name" in updates:
        updates["display_name"] = updates["display_name"].strip()
    changed, data = _changed_values(workspace, updates)
    if changed:
        _add_change_log(
            db,
            workspace_id=workspace.id,
            entity_type="workspace",
            entity_id=workspace.id,
            action="workspace_updated",
            changed_fields=changed,
            change_data=data,
            actor_user_id=current_user.id,
            summary=f"更新客户工作区：{', '.join(changed)}",
        )
        await _flush_or_conflict(db, "客户工作区标识已存在")
    return _workspace_response(workspace)


@router.get(
    "/workspaces/{workspace_id}/column-config",
    response_model=GaiboWorkspaceColumnConfigResponse,
)
async def get_workspace_column_config(
    workspace_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboWorkspaceColumnConfigResponse:
    require_role(current_user, min_level=1)
    workspace = await db.get(GaiboCustomerWorkspace, workspace_id)
    if not workspace or not workspace.is_active:
        raise HTTPException(status_code=404, detail="售后客户工作区不存在")
    return _column_config_response(workspace)


@router.put(
    "/workspaces/{workspace_id}/column-config",
    response_model=GaiboWorkspaceColumnConfigResponse,
)
async def save_workspace_column_config(
    workspace_id: int,
    payload: GaiboWorkspaceColumnConfigUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboWorkspaceColumnConfigResponse:
    require_role(current_user, min_level=4)
    workspace = await db.get(GaiboCustomerWorkspace, workspace_id)
    if not workspace or not workspace.is_active:
        raise HTTPException(status_code=404, detail="售后客户工作区不存在")
    if workspace.column_config_version != payload.expected_version:
        raise HTTPException(status_code=409, detail="客户表格配置已被其他用户更新，请刷新后重试")

    current_fields = {field.key: field for field in _workspace_custom_fields(workspace)}
    incoming_fields: list[GaiboCustomFieldDefinition] = []
    seen_keys: set[str] = set()
    for sequence, field in enumerate(payload.custom_fields):
        if field.key in seen_keys:
            raise HTTPException(status_code=400, detail="客户自定义字段标识不能重复")
        previous = current_fields.get(field.key)
        if previous and (previous.data_type != field.data_type or previous.scope != field.scope):
            raise HTTPException(status_code=400, detail=f"已保存字段“{previous.label}”不能修改数据类型或适用范围")
        seen_keys.add(field.key)
        incoming_fields.append(field.model_copy(update={"sequence": sequence}))
    for key, previous in current_fields.items():
        if key not in seen_keys:
            incoming_fields.append(previous.model_copy(update={"is_active": False, "sequence": len(incoming_fields)}))

    field_labels = _normalize_field_labels(payload.field_labels)
    detail_section_labels = _normalize_detail_section_labels(payload.detail_section_labels)
    default_view = _normalize_workspace_view_config(payload.default_view_config, incoming_fields)
    before_version = workspace.column_config_version
    before_fields = current_fields
    workspace.field_labels = field_labels
    workspace.extra_field_definitions = {
        "schema_version": 1,
        "columns": [field.model_dump(mode="json") for field in incoming_fields],
        "detail_section_labels": detail_section_labels,
    }
    workspace.default_view_config = default_view.model_dump(mode="json")
    workspace.column_config_version += 1

    added = [field.label for field in incoming_fields if field.key not in before_fields and field.is_active]
    archived = [
        field.label
        for field in incoming_fields
        if field.key in before_fields and before_fields[field.key].is_active and not field.is_active
    ]
    restored = [
        field.label
        for field in incoming_fields
        if field.key in before_fields and not before_fields[field.key].is_active and field.is_active
    ]
    renamed = [
        f"{before_fields[field.key].label} -> {field.label}"
        for field in incoming_fields
        if field.key in before_fields and before_fields[field.key].label != field.label
    ]
    _add_change_log(
        db,
        workspace_id=workspace.id,
        entity_type="workspace",
        entity_id=workspace.id,
        action="workspace_columns_updated",
        changed_fields=["field_labels", "detail_section_labels", "custom_fields", "default_view_config"],
        change_data={
            "version": {"before": before_version, "after": workspace.column_config_version},
            "added": added,
            "archived": archived,
            "restored": restored,
            "renamed": renamed,
        },
        actor_user_id=current_user.id,
        summary="更新客户档案表格配置",
    )
    await _flush_or_conflict(db, "客户表格配置保存冲突，请刷新后重试")
    return _column_config_response(workspace)


@router.get("/filter-options", response_model=GaiboFilterOptionsResponse)
async def get_gaibo_filter_options(
    db: DbSession,
    current_user: CurrentUser,
    column_key: str = Query(min_length=1, max_length=72),
    q: Optional[str] = Query(default=None, max_length=200),
    workspace_id: Optional[int] = Query(default=None, gt=0),
    record_type: Optional[str] = Query(default=None, pattern="^(single_part|installation_package)$"),
) -> GaiboFilterOptionsResponse:
    """Return all distinct values and record counts for one Excel-style column filter."""
    require_role(current_user, min_level=1)
    workspace = await db.get(GaiboCustomerWorkspace, workspace_id) if workspace_id is not None else None
    if workspace_id is not None and (workspace is None or not workspace.is_active):
        raise HTTPException(status_code=404, detail="售后客户工作区不存在")
    custom_fields = {field.key: field for field in _workspace_custom_fields(workspace)} if workspace else {}
    if column_key not in CORE_COLUMN_KEYS and column_key not in custom_fields:
        raise HTTPException(status_code=400, detail="筛选字段无效")
    if column_key in custom_fields and not custom_fields[column_key].is_active:
        raise HTTPException(status_code=400, detail="筛选字段已停用")

    req_conditions = [GaiboCustomerRequirement.is_active.is_(True), GaiboCustomerWorkspace.is_active.is_(True)]
    package_conditions = [GaiboInstallationPackage.is_active.is_(True), GaiboCustomerWorkspace.is_active.is_(True)]
    if workspace_id is not None:
        req_conditions.append(GaiboCustomerRequirement.workspace_id == workspace_id)
        package_conditions.append(GaiboInstallationPackage.workspace_id == workspace_id)
    if q and (term := q.strip()):
        pattern = f"%{term}%"
        req_conditions.append(or_(
            GaiboCustomerRequirement.customer_part_number.ilike(pattern),
            GaiboCustomerRequirement.ibi.ilike(pattern),
            GaiboCustomerRequirement.tianyue_internal_composition.ilike(pattern),
        ))
        package_conditions.append(or_(
            GaiboInstallationPackage.package_number.ilike(pattern),
            GaiboInstallationPackage.d_code.ilike(pattern),
            GaiboInstallationPackage.tianyue_pn.ilike(pattern),
            GaiboInstallationPackage.remark.ilike(pattern),
        ))

    req_stmt = select(
        literal("single_part").label("record_type"),
        GaiboCustomerRequirement.id.label("record_id"),
        GaiboCustomerRequirement.workspace_id.label("workspace_id"),
        GaiboCustomerWorkspace.display_name.label("workspace_name"),
        GaiboCustomerRequirement.customer_part_number.label("primary_number"),
        literal(None).label("priority"),
        literal(None).label("d_code"),
        GaiboSinglePart.tianyue_internal_part_no.label("tianyue_pn"),
        GaiboCustomerRequirement.ibi.label("ibi"),
        GaiboCustomerRequirement.tianyue_internal_composition.label("internal_composition"),
        GaiboCustomerRequirement.price.label("price"),
        GaiboCustomerRequirement.remark.label("remark"),
        GaiboCustomerRequirement.extra_data.label("extra_data"),
    ).join(GaiboCustomerWorkspace, GaiboCustomerWorkspace.id == GaiboCustomerRequirement.workspace_id).join(
        GaiboSinglePart, GaiboSinglePart.id == GaiboCustomerRequirement.single_part_id
    ).where(*req_conditions)
    package_stmt = select(
        literal("installation_package").label("record_type"),
        GaiboInstallationPackage.id.label("record_id"),
        GaiboInstallationPackage.workspace_id.label("workspace_id"),
        GaiboCustomerWorkspace.display_name.label("workspace_name"),
        GaiboInstallationPackage.package_number.label("primary_number"),
        GaiboInstallationPackage.priority.label("priority"),
        GaiboInstallationPackage.d_code.label("d_code"),
        GaiboInstallationPackage.tianyue_pn.label("tianyue_pn"),
        literal(None).label("ibi"),
        literal(None).label("internal_composition"),
        GaiboInstallationPackage.price.label("price"),
        GaiboInstallationPackage.remark.label("remark"),
        GaiboInstallationPackage.extra_data.label("extra_data"),
    ).join(GaiboCustomerWorkspace, GaiboCustomerWorkspace.id == GaiboInstallationPackage.workspace_id).where(*package_conditions)
    if record_type == "single_part":
        rows = list(await db.execute(req_stmt))
    elif record_type == "installation_package":
        rows = list(await db.execute(package_stmt))
    else:
        rows = list(await db.execute(req_stmt.union_all(package_stmt)))

    if column_key == "status":
        status_labels = {
            "drawing_ok": "图纸通过", "drawing_in_progress": "图纸进行中", "drawing_not_ok": "图纸 NOT OK",
            "sample_ok": "样件通过", "sample_in_progress": "样件进行中", "sample_not_ok": "样件 NOT OK",
            "ppap_ok": "PPAP 通过", "ppap_in_progress": "PPAP 进行中", "ppap_not_ok": "PPAP NOT OK",
        }
        record_keys = {(row.record_type, int(row.record_id)) for row in rows}
        document_statuses: dict[tuple[str, int, str], str] = {}
        requirement_ids = [record_id for record_type_value, record_id in record_keys if record_type_value == "single_part"]
        package_ids = [record_id for record_type_value, record_id in record_keys if record_type_value == "installation_package"]
        if requirement_ids:
            for document in (await db.execute(select(GaiboDocumentStatus).where(GaiboDocumentStatus.requirement_id.in_(requirement_ids)))).scalars():
                document_statuses[("single_part", document.requirement_id, document.document_type)] = document.status
        if package_ids:
            for document in (await db.execute(select(GaiboDocumentStatus).where(GaiboDocumentStatus.package_id.in_(package_ids)))).scalars():
                document_statuses[("installation_package", document.package_id, document.document_type)] = document.status
        counts = {key: 0 for key in status_labels}
        for record_type_value, record_id in record_keys:
            for document_type in ("drawing", "sample", "ppap"):
                status = document_statuses.get((record_type_value, record_id, document_type), "in_progress")
                normalized = "ok" if status == "ok" else "not_ok" if status == "not_ok" else "in_progress"
                counts[f"{document_type}_{normalized}"] += 1
        return GaiboFilterOptionsResponse(column_key=column_key, options=[
            GaiboFilterOption(value=key, label=status_labels[key], count=counts[key])
            for key in status_labels if counts[key]
        ])

    labels = {"type": {"single_part": "单件", "installation_package": "安装包"}}
    values: dict[str, set[tuple[str, int]]] = {}
    package_ids = [int(row.record_id) for row in rows if row.record_type == "installation_package"]
    package_components: dict[int, list[GaiboPackageItem]] = {}
    if column_key in {"ibi", "internalComposition"} and package_ids:
        for component in (await db.execute(select(GaiboPackageItem).where(GaiboPackageItem.package_id.in_(package_ids)))).scalars():
            package_components.setdefault(component.package_id, []).append(component)
    row_field = {
        "workspace": "workspace_name", "primaryNumber": "primary_number", "priority": "priority", "dCode": "d_code",
        "tianyuePn": "tianyue_pn", "ibi": "ibi", "internalComposition": "internal_composition", "price": "price", "remark": "remark",
    }.get(column_key)
    for row in rows:
        record_key = (row.record_type, int(row.record_id))
        raw_values: list[object] = []
        if column_key == "type":
            raw_values = [row.record_type]
        elif column_key == "ibi" and row.record_type == "installation_package":
            raw_values = [item.ibi for item in package_components.get(int(row.record_id), [])]
        elif column_key == "internalComposition" and row.record_type == "installation_package":
            raw_values = [item.tianyue_internal_composition for item in package_components.get(int(row.record_id), [])]
        elif column_key in custom_fields:
            raw_values = [(row.extra_data or {}).get(column_key)]
        elif row_field:
            raw_values = [getattr(row, row_field)]
        for raw_value in raw_values:
            value = str(raw_value).strip() if raw_value is not None else ""
            if value:
                values.setdefault(value, set()).add(record_key)
    options = [
        GaiboFilterOption(value=value, label=labels.get(column_key, {}).get(value, value), count=len(record_keys))
        for value, record_keys in values.items()
    ]
    options.sort(key=lambda option: (-option.count, option.label.casefold()))
    return GaiboFilterOptionsResponse(column_key=column_key, options=options[:500])


@router.get("/search", response_model=GaiboSearchPage)
async def search_gaibo(
    db: DbSession,
    current_user: CurrentUser,
    q: Optional[str] = Query(default=None, max_length=200),
    workspace_id: Optional[int] = Query(default=None, gt=0),
    record_type: Optional[str] = Query(default=None, pattern="^(single_part|installation_package)$"),
    status: Optional[str] = Query(default=None, max_length=30),
    column_filters: Optional[str] = Query(default=None, max_length=6000),
    sort_by: str = Query(default="updatedAt", min_length=1, max_length=72),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=100),
) -> GaiboSearchPage:
    require_role(current_user, min_level=1)
    column_filter_values = _parse_column_filters(column_filters)
    custom_sort_field: GaiboCustomFieldDefinition | None = None
    if sort_by not in CORE_SORT_KEYS:
        if workspace_id is None:
            raise HTTPException(status_code=400, detail="客户自定义字段只能在对应客户工作区内排序")
        workspace = await db.get(GaiboCustomerWorkspace, workspace_id)
        if not workspace or not workspace.is_active:
            raise HTTPException(status_code=404, detail="售后客户工作区不存在")
        custom_sort_field = next(
            (field for field in _workspace_custom_fields(workspace) if field.key == sort_by and field.is_active),
            None,
        )
        if custom_sort_field is None:
            raise HTTPException(status_code=400, detail="排序字段无效")
    req_document_status = {
        document_type: select(GaiboDocumentStatus.status)
        .where(
            GaiboDocumentStatus.requirement_id == GaiboCustomerRequirement.id,
            GaiboDocumentStatus.document_type == document_type,
        )
        .limit(1)
        .scalar_subquery()
        for document_type in ("drawing", "sample", "ppap")
    }
    package_document_status = {
        document_type: select(GaiboDocumentStatus.status)
        .where(
            GaiboDocumentStatus.package_id == GaiboInstallationPackage.id,
            GaiboDocumentStatus.document_type == document_type,
        )
        .limit(1)
        .scalar_subquery()
        for document_type in ("drawing", "sample", "ppap")
    }
    req_conditions = [GaiboCustomerRequirement.is_active.is_(True), GaiboCustomerWorkspace.is_active.is_(True)]
    package_conditions = [GaiboInstallationPackage.is_active.is_(True), GaiboCustomerWorkspace.is_active.is_(True)]
    if workspace_id is not None:
        req_conditions.append(GaiboCustomerRequirement.workspace_id == workspace_id)
        package_conditions.append(GaiboInstallationPackage.workspace_id == workspace_id)
    if q and (term := q.strip()):
        pattern = f"%{term}%"
        req_conditions.append(
            or_(
                GaiboCustomerRequirement.customer_part_number.ilike(pattern),
                GaiboCustomerRequirement.ibi.ilike(pattern),
                GaiboCustomerRequirement.tianyue_internal_composition.ilike(pattern),
                GaiboSinglePart.tianyue_internal_part_no.ilike(pattern),
                GaiboSinglePart.name.ilike(pattern),
                GaiboCustomerRequirement.remark.ilike(pattern),
                cast(GaiboCustomerRequirement.extra_data, Text).ilike(pattern),
            )
        )
        package_conditions.append(
            or_(
                GaiboInstallationPackage.package_number.ilike(pattern),
                GaiboInstallationPackage.d_code.ilike(pattern),
                GaiboInstallationPackage.tianyue_pn.ilike(pattern),
                GaiboInstallationPackage.name.ilike(pattern),
                GaiboInstallationPackage.remark.ilike(pattern),
                cast(GaiboInstallationPackage.extra_data, Text).ilike(pattern),
                exists(
                    select(GaiboPackageItem.id).where(
                        GaiboPackageItem.package_id == GaiboInstallationPackage.id,
                        or_(
                            GaiboPackageItem.ibi.ilike(pattern),
                            GaiboPackageItem.tianyue_internal_composition.ilike(pattern),
                            GaiboPackageItem.unlinked_customer_part_number.ilike(pattern),
                        ),
                    )
                ),
            )
        )
    if status and (normalized_status := status.strip()):
        req_conditions.append(
            exists(
                select(GaiboDocumentStatus.id).where(
                    GaiboDocumentStatus.requirement_id == GaiboCustomerRequirement.id,
                    GaiboDocumentStatus.status == normalized_status,
                )
            )
        )
        package_conditions.append(
            or_(
                exists(
                    select(GaiboPackageItem.id).where(
                        GaiboPackageItem.package_id == GaiboInstallationPackage.id,
                        GaiboPackageItem.status == normalized_status,
                    )
                ),
                exists(
                    select(GaiboDocumentStatus.id).where(
                        GaiboDocumentStatus.package_id == GaiboInstallationPackage.id,
                        GaiboDocumentStatus.status == normalized_status,
                    )
                ),
            )
        )
    workspace_for_filters = await db.get(GaiboCustomerWorkspace, workspace_id) if workspace_id is not None else None
    custom_filter_keys = {
        field.key for field in _workspace_custom_fields(workspace_for_filters)
        if field.is_active
    } if workspace_for_filters else set()
    status_filter_map = {
        "drawing_ok": ("drawing", "ok"),
        "drawing_in_progress": ("drawing", "in_progress"),
        "drawing_not_ok": ("drawing", "not_ok"),
        "sample_ok": ("sample", "ok"),
        "sample_in_progress": ("sample", "in_progress"),
        "sample_not_ok": ("sample", "not_ok"),
        "ppap_ok": ("ppap", "ok"),
        "ppap_in_progress": ("ppap", "in_progress"),
        "ppap_not_ok": ("ppap", "not_ok"),
    }
    for key, raw_value in column_filter_values.items():
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        patterns = [f"%{value}%" for value in values]
        if key == "type":
            normalized_types = {value.lower() for value in values}
            wants_single = bool(normalized_types & {"single_part", "single", "单件"})
            wants_package = bool(normalized_types & {"installation_package", "package", "安装包"})
            if wants_single and not wants_package:
                package_conditions.append(false())
            elif wants_package and not wants_single:
                req_conditions.append(false())
            elif not wants_single and not wants_package:
                req_conditions.append(false())
                package_conditions.append(false())
        elif key == "status":
            semantic_statuses = [status_filter_map[value] for value in values if value in status_filter_map]
            if semantic_statuses:
                req_conditions.append(or_(*[
                    exists(select(GaiboDocumentStatus.id).where(
                        GaiboDocumentStatus.requirement_id == GaiboCustomerRequirement.id,
                        GaiboDocumentStatus.document_type == document_type,
                        GaiboDocumentStatus.status == status,
                    ))
                    for document_type, status in semantic_statuses
                ]))
                package_conditions.append(or_(*[
                    or_(
                        exists(select(GaiboDocumentStatus.id).where(
                            GaiboDocumentStatus.package_id == GaiboInstallationPackage.id,
                            GaiboDocumentStatus.document_type == document_type,
                            GaiboDocumentStatus.status == status,
                        )),
                        exists(select(GaiboPackageItem.id).where(
                            GaiboPackageItem.package_id == GaiboInstallationPackage.id,
                            GaiboPackageItem.status == status,
                        )),
                    )
                    for document_type, status in semantic_statuses
                ]))
            else:
                req_conditions.append(exists(select(GaiboDocumentStatus.id).where(
                    GaiboDocumentStatus.requirement_id == GaiboCustomerRequirement.id,
                    or_(*[GaiboDocumentStatus.status.ilike(pattern) for pattern in patterns]),
                )))
                package_conditions.append(or_(
                    exists(select(GaiboPackageItem.id).where(
                        GaiboPackageItem.package_id == GaiboInstallationPackage.id,
                        or_(*[GaiboPackageItem.status.ilike(pattern) for pattern in patterns]),
                    )),
                    exists(select(GaiboDocumentStatus.id).where(
                        GaiboDocumentStatus.package_id == GaiboInstallationPackage.id,
                        or_(*[GaiboDocumentStatus.status.ilike(pattern) for pattern in patterns]),
                    )),
                ))
        elif key == "primaryNumber":
            req_conditions.append(GaiboCustomerRequirement.customer_part_number.in_(values))
            package_conditions.append(GaiboInstallationPackage.package_number.in_(values))
        elif key == "workspace":
            req_conditions.append(GaiboCustomerWorkspace.display_name.in_(values))
            package_conditions.append(GaiboCustomerWorkspace.display_name.in_(values))
        elif key == "priority":
            priorities = [int(value) for value in values if value.isdigit()]
            req_conditions.append(false())
            package_conditions.append(GaiboInstallationPackage.priority.in_(priorities) if priorities else false())
        elif key == "dCode":
            req_conditions.append(false())
            package_conditions.append(GaiboInstallationPackage.d_code.in_(values))
        elif key == "tianyuePn":
            req_conditions.append(GaiboSinglePart.tianyue_internal_part_no.in_(values))
            package_conditions.append(GaiboInstallationPackage.tianyue_pn.in_(values))
        elif key == "ibi":
            req_conditions.append(GaiboCustomerRequirement.ibi.in_(values))
            package_conditions.append(exists(select(GaiboPackageItem.id).where(
                GaiboPackageItem.package_id == GaiboInstallationPackage.id,
                GaiboPackageItem.ibi.in_(values),
            )))
        elif key == "internalComposition":
            req_conditions.append(GaiboCustomerRequirement.tianyue_internal_composition.in_(values))
            package_conditions.append(exists(select(GaiboPackageItem.id).where(
                GaiboPackageItem.package_id == GaiboInstallationPackage.id,
                GaiboPackageItem.tianyue_internal_composition.in_(values),
            )))
        elif key == "price":
            try:
                prices = [Decimal(value) for value in values]
            except (InvalidOperation, ValueError):
                prices = []
            req_conditions.append(GaiboCustomerRequirement.price.in_(prices) if prices else false())
            package_conditions.append(GaiboInstallationPackage.price.in_(prices) if prices else false())
        elif key == "remark":
            req_conditions.append(GaiboCustomerRequirement.remark.in_(values))
            package_conditions.append(GaiboInstallationPackage.remark.in_(values))
        elif key in custom_filter_keys:
            req_conditions.append(GaiboCustomerRequirement.extra_data[key].astext.in_(values))
            package_conditions.append(GaiboInstallationPackage.extra_data[key].astext.in_(values))
    req_stmt = select(
        literal("single_part").label("record_type"),
        GaiboCustomerRequirement.id.label("record_id"),
        GaiboCustomerRequirement.workspace_id.label("workspace_id"),
        GaiboCustomerWorkspace.display_name.label("workspace_name"),
        GaiboCustomerRequirement.customer_part_number.label("customer_part_number"),
        literal(None).label("priority"),
        literal(None).label("d_code"),
        GaiboSinglePart.tianyue_internal_part_no.label("tianyue_pn"),
        GaiboCustomerRequirement.ibi.label("ibi"),
        GaiboCustomerRequirement.tianyue_internal_composition.label("tianyue_internal_composition"),
        GaiboCustomerRequirement.price.label("price"),
        literal(False).label("price_mismatch"),
        GaiboSinglePart.name.label("display_name"),
        GaiboCustomerRequirement.remark.label("remark"),
        GaiboCustomerRequirement.extra_data.label("extra_data"),
        req_document_status["drawing"].label("drawing_status"),
        req_document_status["sample"].label("sample_status"),
        req_document_status["ppap"].label("ppap_status"),
        GaiboCustomerRequirement.updated_at.label("updated_at"),
    ).join(GaiboCustomerWorkspace, GaiboCustomerWorkspace.id == GaiboCustomerRequirement.workspace_id).join(
        GaiboSinglePart, GaiboSinglePart.id == GaiboCustomerRequirement.single_part_id
    ).where(*req_conditions)
    package_stmt = select(
        literal("installation_package").label("record_type"),
        GaiboInstallationPackage.id.label("record_id"),
        GaiboInstallationPackage.workspace_id.label("workspace_id"),
        GaiboCustomerWorkspace.display_name.label("workspace_name"),
        GaiboInstallationPackage.package_number.label("customer_part_number"),
        GaiboInstallationPackage.priority.label("priority"),
        GaiboInstallationPackage.d_code.label("d_code"),
        GaiboInstallationPackage.tianyue_pn.label("tianyue_pn"),
        literal(None).label("ibi"),
        literal(None).label("tianyue_internal_composition"),
        GaiboInstallationPackage.price.label("price"),
        case(
            (
                GaiboInstallationPackage.source_data["legacy_pricing"]["price_mismatch"].as_boolean().is_(True),
                True,
            ),
            else_=False,
        ).label("price_mismatch"),
        GaiboInstallationPackage.name.label("display_name"),
        GaiboInstallationPackage.remark.label("remark"),
        GaiboInstallationPackage.extra_data.label("extra_data"),
        package_document_status["drawing"].label("drawing_status"),
        package_document_status["sample"].label("sample_status"),
        package_document_status["ppap"].label("ppap_status"),
        GaiboInstallationPackage.updated_at.label("updated_at"),
    ).join(GaiboCustomerWorkspace, GaiboCustomerWorkspace.id == GaiboInstallationPackage.workspace_id).where(*package_conditions)
    if record_type == "single_part":
        combined = req_stmt.subquery()
    elif record_type == "installation_package":
        combined = package_stmt.subquery()
    else:
        combined = req_stmt.union_all(package_stmt).subquery()

    summary_row = (
        await db.execute(
            select(
                func.count().label("total_records"),
                func.count().filter(combined.c.price.is_not(None)).label("priced_records"),
                func.count().filter(combined.c.price.is_(None)).label("missing_price_records"),
                func.count().filter(combined.c.drawing_status == "ok").label("drawing_ok_records"),
                func.count().filter(combined.c.sample_status == "ok").label("sample_ok_records"),
                func.count().filter(combined.c.ppap_status == "ok").label("ppap_ok_records"),
            ).select_from(combined)
        )
    ).one()
    summary = GaiboSearchSummary.model_validate(dict(summary_row._mapping))
    total = summary.total_records
    sort_columns = {
        "primaryNumber": combined.c.customer_part_number,
        "priority": combined.c.priority,
        "dCode": combined.c.d_code,
        "tianyuePn": combined.c.tianyue_pn,
        "price": combined.c.price,
        "updatedAt": combined.c.updated_at,
    }
    if custom_sort_field is None:
        sort_column = sort_columns[sort_by]
    else:
        custom_text = combined.c.extra_data[custom_sort_field.key].astext
        if custom_sort_field.data_type == "number":
            sort_column = cast(custom_text, Numeric)
        elif custom_sort_field.data_type == "date":
            sort_column = cast(custom_text, Date)
        elif custom_sort_field.data_type == "boolean":
            sort_column = cast(custom_text, Boolean)
        else:
            sort_column = custom_text
    sort_expression = sort_column.asc().nulls_last() if sort_order == "asc" else sort_column.desc().nulls_last()
    result = await db.execute(
        select(combined)
        .order_by(sort_expression, combined.c.record_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list(result)
    package_ids = [
        int(row._mapping["record_id"])
        for row in rows
        if row._mapping["record_type"] == "installation_package"
    ]
    requirement_ids = [
        int(row._mapping["record_id"])
        for row in rows
        if row._mapping["record_type"] == "single_part"
    ]
    document_event_map: dict[tuple[str, int, str], GaiboDocumentEventResponse | None] = {}
    if package_ids or requirement_ids:
        document_conditions = []
        if package_ids:
            document_conditions.append(GaiboDocumentStatus.package_id.in_(package_ids))
        if requirement_ids:
            document_conditions.append(GaiboDocumentStatus.requirement_id.in_(requirement_ids))
        document_rows = await db.scalars(
            select(GaiboDocumentStatus).where(or_(*document_conditions))
        )
        for document in document_rows:
            owner_type = "installation_package" if document.package_id is not None else "single_part"
            owner_id = document.package_id if document.package_id is not None else document.requirement_id
            if owner_id is not None:
                document_event_map[(owner_type, int(owner_id), document.document_type)] = _latest_event_for_row(document)
    package_display_values: dict[int, tuple[str | None, str | None]] = {}
    package_component_items: dict[int, list[dict[str, object]]] = {}
    if package_ids:
        package_item_result = await db.execute(
            select(
                GaiboPackageItem.package_id,
                GaiboPackageItem.ibi,
                GaiboPackageItem.tianyue_internal_composition,
                GaiboPackageItem.sequence,
                GaiboPackageItem.quantity,
                GaiboPackageItem.status,
            )
            .where(GaiboPackageItem.package_id.in_(package_ids))
            .order_by(GaiboPackageItem.package_id, GaiboPackageItem.sequence)
        )
        package_item_rows = list(package_item_result)
        package_display_values = _aggregate_package_display_values(
            (
                item.package_id,
                item.ibi,
                item.tianyue_internal_composition,
            )
            for item in package_item_rows
        )
        package_component_items = {}
        for item in package_item_rows:
            package_component_items.setdefault(item.package_id, []).append(
                {
                    "sequence": item.sequence,
                    "ibi": item.ibi,
                    "tianyue_internal_composition": item.tianyue_internal_composition,
                    "quantity": item.quantity,
                    "status": item.status,
                }
            )

    items: list[GaiboSearchItem] = []
    for row in rows:
        payload = dict(row._mapping)
        if payload["record_type"] == "installation_package":
            ibi, internal = package_display_values.get(int(payload["record_id"]), (None, None))
            payload["ibi"] = ibi
            payload["tianyue_internal_composition"] = internal
            payload["component_items"] = package_component_items.get(int(payload["record_id"]), [])
        record_key = (payload["record_type"], int(payload["record_id"]))
        payload["drawing_latest_event"] = document_event_map.get((*record_key, "drawing"))
        payload["sample_latest_event"] = document_event_map.get((*record_key, "sample"))
        payload["ppap_latest_event"] = document_event_map.get((*record_key, "ppap"))
        items.append(GaiboSearchItem.model_validate(payload))
    return GaiboSearchPage(items=items, total=total, page=page, page_size=page_size, summary=summary)


@router.get("/workspaces/{workspace_id}/records", response_model=GaiboSearchPage)
async def list_workspace_records(
    workspace_id: int,
    db: DbSession,
    current_user: CurrentUser,
    q: Optional[str] = Query(default=None, max_length=200),
    record_type: Optional[str] = Query(default=None, pattern="^(single_part|installation_package)$"),
    status: Optional[str] = Query(default=None, max_length=30),
    sort_by: str = Query(default="updatedAt", min_length=1, max_length=72),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=100),
) -> GaiboSearchPage:
    """Return one customer's single-part requirements and packages using the same table contract."""
    require_role(current_user, min_level=1)
    return await search_gaibo(
        db=db,
        current_user=current_user,
        q=q,
        workspace_id=workspace_id,
        record_type=record_type,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/single-parts", response_model=list[GaiboSinglePartResponse])
async def list_single_parts(
    db: DbSession,
    current_user: CurrentUser,
    q: Optional[str] = Query(default=None, max_length=200),
) -> list[GaiboSinglePartResponse]:
    require_role(current_user, min_level=1)
    conditions = [GaiboSinglePart.is_active.is_(True)]
    if q and (term := q.strip()):
        pattern = f"%{term}%"
        conditions.append(or_(GaiboSinglePart.name.ilike(pattern), GaiboSinglePart.tianyue_internal_part_no.ilike(pattern)))
    result = await db.execute(
        select(GaiboSinglePart).options(selectinload(GaiboSinglePart.requirements)).where(*conditions).order_by(GaiboSinglePart.updated_at.desc())
    )
    items: list[GaiboSinglePartResponse] = []
    for item in result.scalars():
        data = GaiboSinglePartResponse.model_validate(item, from_attributes=True).model_dump()
        data["requirement_count"] = len(item.requirements)
        items.append(GaiboSinglePartResponse(**data))
    return items


@router.post("/single-parts", response_model=GaiboSinglePartResponse, status_code=201)
async def create_single_part(
    payload: GaiboSinglePartCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboSinglePartResponse:
    require_role(current_user, min_level=2)
    item = GaiboSinglePart(**payload.model_dump())
    db.add(item)
    await db.flush()
    return GaiboSinglePartResponse.model_validate(item, from_attributes=True)


@router.patch("/single-parts/{single_part_id}", response_model=GaiboSinglePartResponse)
async def update_single_part(
    single_part_id: int,
    payload: GaiboSinglePartUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboSinglePartResponse:
    require_role(current_user, min_level=2)
    item = await db.get(GaiboSinglePart, single_part_id, options=[selectinload(GaiboSinglePart.requirements)])
    if not item:
        raise HTTPException(status_code=404, detail="单件档案不存在")
    updates = payload.model_dump(exclude_unset=True)
    changed, data = _changed_values(item, updates)
    if changed and item.requirements:
        workspace_ids = {requirement.workspace_id for requirement in item.requirements}
        for workspace_id in workspace_ids:
            _add_change_log(
                db,
                workspace_id=workspace_id,
                entity_type="single_part",
                entity_id=item.id,
                action="single_part_updated",
                changed_fields=changed,
                change_data=data,
                actor_user_id=current_user.id,
            )
    await db.flush()
    data = GaiboSinglePartResponse.model_validate(item, from_attributes=True).model_dump()
    data["requirement_count"] = len(item.requirements)
    return GaiboSinglePartResponse(**data)


@router.post("/requirements", response_model=GaiboRequirementResponse, status_code=201)
async def create_requirement(
    payload: GaiboRequirementCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboRequirementResponse:
    require_role(current_user, min_level=2)
    values = payload.model_dump()
    values["customer_part_number"] = _text_or_400(values["customer_part_number"], "客户件号")
    values["ibi"] = _text_or_400(values["ibi"], "IBI")
    values["tianyue_internal_composition"] = _text_or_400(values["tianyue_internal_composition"], "天越内部组成")
    values["currency"] = _currency_or_400(values.get("currency")) or "USD"
    workspace = await db.get(GaiboCustomerWorkspace, values["workspace_id"])
    if not workspace or not workspace.is_active:
        raise HTTPException(status_code=404, detail="售后客户工作区不存在")
    values["extra_data"] = _validate_extra_data(
        workspace,
        values.get("extra_data") or {},
        record_type="single_part",
    )
    item = GaiboCustomerRequirement(**values)
    db.add(item)
    await _flush_or_conflict(db, "当前客户下已存在相同的单件需求")
    _add_change_log(
        db,
        workspace_id=item.workspace_id,
        entity_type="requirement",
        entity_id=item.id,
        action="requirement_created",
        changed_fields=list(values),
        change_data=creation_change_data(values),
        actor_user_id=current_user.id,
    )
    return GaiboRequirementResponse.model_validate(item, from_attributes=True)


@router.patch("/requirements/{requirement_id}", response_model=GaiboRequirementResponse)
async def update_requirement(
    requirement_id: int,
    payload: GaiboRequirementUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboRequirementResponse:
    require_role(current_user, min_level=2)
    item = await db.get(GaiboCustomerRequirement, requirement_id)
    if not item:
        raise HTTPException(status_code=404, detail="客户单件需求不存在")
    updates = payload.model_dump(exclude_unset=True)
    _check_updated_at(item, updates.pop("expected_updated_at", None))
    _normalize_requirement_updates(updates)
    if "extra_data" in updates:
        workspace = await db.get(GaiboCustomerWorkspace, item.workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="售后客户工作区不存在")
        updates["extra_data"] = _validate_extra_data(
            workspace,
            updates["extra_data"] or {},
            record_type="single_part",
            existing=item.extra_data,
        )
    changed, data = _changed_values(item, updates)
    if changed:
        _add_change_log(
            db,
            workspace_id=item.workspace_id,
            entity_type="requirement",
            entity_id=item.id,
            action="requirement_updated",
            changed_fields=changed,
            change_data=data,
            actor_user_id=current_user.id,
        )
        await _flush_or_conflict(db, "当前客户下已存在相同的单件需求")
    return GaiboRequirementResponse.model_validate(item, from_attributes=True)


@router.patch("/requirements/{requirement_id}/dossier", response_model=GaiboRequirementDetailResponse)
async def update_requirement_dossier(
    requirement_id: int,
    payload: GaiboRequirementDossierUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboRequirementDetailResponse:
    """Save customer requirement and its shared display name as one transaction."""
    require_role(current_user, min_level=2)
    item = await _get_requirement_detail(db, requirement_id)
    if not item or item.single_part is None:
        raise HTTPException(status_code=404, detail="客户单件需求不存在")

    updates = payload.model_dump(exclude_unset=True)
    _check_updated_at(item, updates.pop("expected_updated_at", None))
    single_part_name = updates.pop("single_part_name", None)
    has_single_part_name = "single_part_name" in payload.model_fields_set
    _normalize_requirement_updates(updates)
    if "extra_data" in updates:
        workspace = await db.get(GaiboCustomerWorkspace, item.workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="售后客户工作区不存在")
        updates["extra_data"] = _validate_extra_data(
            workspace,
            updates["extra_data"] or {},
            record_type="single_part",
            existing=item.extra_data,
        )
    requirement_changed, requirement_data = _changed_values(item, updates)
    if requirement_changed:
        _add_change_log(
            db,
            workspace_id=item.workspace_id,
            entity_type="requirement",
            entity_id=item.id,
            action="requirement_updated",
            changed_fields=requirement_changed,
            change_data=requirement_data,
            actor_user_id=current_user.id,
        )

    if has_single_part_name:
        normalized_name = single_part_name.strip() if isinstance(single_part_name, str) else None
        single_changed, single_data = _changed_values(item.single_part, {"name": normalized_name})
        if single_changed:
            workspace_ids = set(
                (await db.scalars(
                    select(GaiboCustomerRequirement.workspace_id).where(
                        GaiboCustomerRequirement.single_part_id == item.single_part.id,
                    )
                )).all()
            )
            for workspace_id in workspace_ids:
                _add_change_log(
                    db,
                    workspace_id=workspace_id,
                    entity_type="single_part",
                    entity_id=item.single_part.id,
                    action="single_part_updated",
                    changed_fields=single_changed,
                    change_data=single_data,
                    actor_user_id=current_user.id,
                )

    if requirement_changed or (has_single_part_name and item.single_part in db.dirty):
        await _flush_or_conflict(db, "当前客户下已存在相同的单件需求")
    return await get_requirement(requirement_id=requirement_id, db=db, current_user=current_user)


@router.get("/workspaces/{workspace_id}/packages", response_model=list[GaiboPackageResponse])
async def list_packages(
    workspace_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[GaiboPackageResponse]:
    require_role(current_user, min_level=1)
    result = await db.execute(
        select(GaiboInstallationPackage)
        .where(GaiboInstallationPackage.workspace_id == workspace_id, GaiboInstallationPackage.is_active.is_(True))
        .order_by(GaiboInstallationPackage.updated_at.desc())
    )
    return [GaiboPackageResponse.model_validate(item, from_attributes=True) for item in result.scalars()]


@router.post("/packages", response_model=GaiboPackageResponse, status_code=201)
async def create_package(
    payload: GaiboPackageCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboPackageResponse:
    require_role(current_user, min_level=2)
    values = payload.model_dump()
    values["package_number"] = _text_or_400(values["package_number"], "安装包号")
    values["currency"] = _required_currency_or_400(values.get("currency"))
    workspace = await db.get(GaiboCustomerWorkspace, values["workspace_id"])
    if not workspace or not workspace.is_active:
        raise HTTPException(status_code=404, detail="售后客户工作区不存在")
    values["extra_data"] = _validate_extra_data(
        workspace,
        values.get("extra_data") or {},
        record_type="installation_package",
    )
    item = GaiboInstallationPackage(**values)
    db.add(item)
    await _flush_or_conflict(db, "当前客户下已存在相同的安装包号")
    _add_change_log(
        db,
        workspace_id=item.workspace_id,
        entity_type="package",
        entity_id=item.id,
        action="package_created",
        changed_fields=list(values),
        change_data=creation_change_data(values),
        actor_user_id=current_user.id,
    )
    return GaiboPackageResponse.model_validate(item, from_attributes=True)


@router.get("/packages/{package_id}", response_model=GaiboPackageDetailResponse)
async def get_package(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboPackageDetailResponse:
    require_role(current_user, min_level=1)
    item = await _get_package_detail(db, package_id)
    if not item:
        raise HTTPException(status_code=404, detail="安装包档案不存在")
    history = await _get_package_change_history(db, item)
    data = GaiboPackageDetailResponse.model_validate(item, from_attributes=True).model_dump()
    data["documents"] = [_document_response(document) for document in _ordered_documents(item.documents)]
    data["change_history"] = [GaiboChangeLogResponse.model_validate(row, from_attributes=True) for row in history]
    return GaiboPackageDetailResponse(**data)


@router.patch("/packages/{package_id}", response_model=GaiboPackageDetailResponse)
async def update_package(
    package_id: int,
    payload: GaiboPackageUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboPackageDetailResponse:
    require_role(current_user, min_level=2)
    item = await _get_package_detail(db, package_id)
    if not item:
        raise HTTPException(status_code=404, detail="安装包档案不存在")
    updates = payload.model_dump(exclude_unset=True)
    _check_updated_at(item, updates.pop("expected_updated_at", None))
    if "currency" in updates:
        updates["currency"] = _required_currency_or_400(updates["currency"])
    if "package_number" in updates:
        updates["package_number"] = _text_or_400(updates["package_number"], "安装包号")
    if "extra_data" in updates:
        workspace = await db.get(GaiboCustomerWorkspace, item.workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="售后客户工作区不存在")
        updates["extra_data"] = _validate_extra_data(
            workspace,
            updates["extra_data"] or {},
            record_type="installation_package",
            existing=item.extra_data,
        )
    changed, data = _changed_values(item, updates)
    if changed:
        _add_change_log(
            db,
            workspace_id=item.workspace_id,
            entity_type="package",
            entity_id=item.id,
            action="package_updated",
            changed_fields=changed,
            change_data=data,
            actor_user_id=current_user.id,
        )
        await _flush_or_conflict(db, "当前客户下已存在相同的安装包号")
    return await get_package(package_id=package_id, db=db, current_user=current_user)


@router.post("/packages/{package_id}/items", response_model=GaiboPackageItemResponse, status_code=201)
async def create_package_item(
    package_id: int,
    payload: GaiboPackageItemCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboPackageItemResponse:
    require_role(current_user, min_level=2)
    package = await db.get(GaiboInstallationPackage, package_id)
    if not package or not package.is_active:
        raise HTTPException(status_code=404, detail="安装包档案不存在")
    values = payload.model_dump()
    # A source-only item may have an internal composition before its IBI is
    # assigned. Keep that row instead of forcing a fabricated customer number.
    if values.get("ibi") is not None:
        try:
            validate_package_item_reference(values["requirement_id"], values.get("unlinked_customer_part_number"))
        except GaiboValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if values["requirement_id"] is not None:
        requirement = await db.get(GaiboCustomerRequirement, values["requirement_id"])
        if not requirement or requirement.workspace_id != package.workspace_id or not requirement.is_active:
            raise HTTPException(status_code=400, detail="组成项关联的客户单件不属于当前客户")
    values["match_state"] = (
        "linked"
        if values["requirement_id"] is not None
        else "missing_ibi"
        if values.get("ibi") is None
        else "unlinked"
    )
    item = GaiboPackageItem(package_id=package.id, **values)
    db.add(item)
    await _flush_or_conflict(db, "安装包内的组成顺序已存在")
    _add_change_log(
        db,
        workspace_id=package.workspace_id,
        entity_type="package_item",
        entity_id=item.id,
        action="package_item_created",
        changed_fields=list(values),
        change_data=creation_change_data(values),
        actor_user_id=current_user.id,
    )
    await db.flush()
    return GaiboPackageItemResponse.model_validate(item, from_attributes=True)


@router.patch("/packages/{package_id}/items/{item_id}", response_model=GaiboPackageItemResponse)
async def update_package_item(
    package_id: int,
    item_id: int,
    payload: GaiboPackageItemUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboPackageItemResponse:
    require_role(current_user, min_level=2)
    package = await db.get(GaiboInstallationPackage, package_id)
    item = await db.get(GaiboPackageItem, item_id)
    if not package or not package.is_active or not item or item.package_id != package.id:
        raise HTTPException(status_code=404, detail="安装包组成项不存在")
    updates = payload.model_dump(exclude_unset=True)
    _check_updated_at(item, updates.pop("expected_updated_at", None))
    _normalize_required_text_updates(updates, {"tianyue_internal_composition": "天越内部组成"})
    for field, label in (("quantity", "数量"), ("sequence", "顺序")):
        if field in updates and updates[field] is None:
            raise HTTPException(status_code=400, detail=f"{label}不能为空")
    if "requirement_id" in updates and updates["requirement_id"] is not None:
        requirement = await db.get(GaiboCustomerRequirement, updates["requirement_id"])
        if not requirement or requirement.workspace_id != package.workspace_id or not requirement.is_active:
            raise HTTPException(status_code=400, detail="组成项关联的客户单件不属于当前客户")
    effective_requirement_id = updates.get("requirement_id", item.requirement_id)
    effective_unlinked_number = updates.get(
        "unlinked_customer_part_number", item.unlinked_customer_part_number
    )
    effective_ibi = updates.get("ibi", item.ibi)
    if effective_ibi is not None:
        try:
            validate_package_item_reference(effective_requirement_id, effective_unlinked_number)
        except GaiboValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    updates["match_state"] = (
        "linked"
        if effective_requirement_id is not None
        else "missing_ibi"
        if effective_ibi is None
        else "unlinked"
    )
    changed, data = _changed_values(item, updates)
    if changed:
        _add_change_log(
            db,
            workspace_id=package.workspace_id,
            entity_type="package_item",
            entity_id=item.id,
            action="package_item_updated",
            changed_fields=changed,
            change_data=data,
            actor_user_id=current_user.id,
        )
        await _flush_or_conflict(db, "安装包内的组成顺序已存在")
    return GaiboPackageItemResponse.model_validate(item, from_attributes=True)


@router.get("/requirements/{requirement_id}", response_model=GaiboRequirementDetailResponse)
async def get_requirement(
    requirement_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboRequirementDetailResponse:
    require_role(current_user, min_level=1)
    item = await _get_requirement_detail(db, requirement_id)
    if not item:
        raise HTTPException(status_code=404, detail="客户单件需求不存在")
    history = await _get_requirement_change_history(db, item)
    data = GaiboRequirementDetailResponse.model_validate(item, from_attributes=True).model_dump()
    data["documents"] = [_document_response(document) for document in _ordered_documents(item.documents)]
    data["change_history"] = [GaiboChangeLogResponse.model_validate(row, from_attributes=True) for row in history]
    return GaiboRequirementDetailResponse(**data)


@router.post("/requirements/{requirement_id}/drawings", response_model=GaiboDrawingResponse, status_code=201)
async def create_drawing(
    requirement_id: int,
    payload: GaiboDrawingCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboDrawingResponse:
    require_role(current_user, min_level=2)
    requirement = await db.get(GaiboCustomerRequirement, requirement_id)
    if not requirement or not requirement.is_active:
        raise HTTPException(status_code=404, detail="客户单件需求不存在")
    drawing = GaiboDrawing(requirement_id=requirement.id, **payload.model_dump())
    db.add(drawing)
    await _flush_or_conflict(db, "当前单件已存在相同的图纸版本")
    values = payload.model_dump()
    _add_change_log(
        db,
        workspace_id=requirement.workspace_id,
        entity_type="drawing",
        entity_id=drawing.id,
        action="drawing_created",
        changed_fields=list(values),
        change_data=creation_change_data(values),
        actor_user_id=current_user.id,
    )
    return GaiboDrawingResponse.model_validate(drawing, from_attributes=True)


@router.patch("/drawings/{drawing_id}", response_model=GaiboDrawingResponse)
async def update_drawing(
    drawing_id: int,
    payload: GaiboDrawingUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboDrawingResponse:
    require_role(current_user, min_level=2)
    drawing = await db.get(GaiboDrawing, drawing_id)
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸版本不存在")
    updates = payload.model_dump(exclude_unset=True)
    _check_updated_at(drawing, updates.pop("expected_updated_at", None))
    requirement = await db.get(GaiboCustomerRequirement, drawing.requirement_id)
    if not requirement:
        raise HTTPException(status_code=404, detail="客户单件需求不存在")
    _normalize_required_text_updates(
        updates,
        {"version": "图纸版本", "file_key": "图纸文件", "status": "图纸状态"},
    )
    changed, data = _changed_values(drawing, updates)
    if changed:
        _add_change_log(db, workspace_id=requirement.workspace_id, entity_type="drawing", entity_id=drawing.id, action="drawing_updated", changed_fields=changed, change_data=data, actor_user_id=current_user.id)
        await _flush_or_conflict(db, "当前单件已存在相同的图纸版本")
    return GaiboDrawingResponse.model_validate(drawing, from_attributes=True)


@router.post("/requirements/{requirement_id}/process-routes", response_model=GaiboProcessRouteResponse, status_code=201)
async def create_process_route(
    requirement_id: int,
    payload: GaiboProcessRouteCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboProcessRouteResponse:
    require_role(current_user, min_level=2)
    requirement = await db.get(GaiboCustomerRequirement, requirement_id)
    if not requirement or not requirement.is_active:
        raise HTTPException(status_code=404, detail="客户单件需求不存在")
    values = payload.model_dump()
    if values["is_current"]:
        await _demote_current_routes(
            db,
            requirement_id=requirement.id,
            workspace_id=requirement.workspace_id,
            except_route_id=None,
            actor_user_id=current_user.id,
        )
    route = GaiboProcessRoute(requirement_id=requirement.id, **payload.model_dump(exclude={"steps"}))
    route.steps = [GaiboProcessStep(**step.model_dump()) for step in payload.steps]
    db.add(route)
    await _flush_or_conflict(db, "当前单件已存在相同的工艺版本或步骤顺序")
    values["steps"] = [step.model_dump() for step in payload.steps]
    _add_change_log(
        db,
        workspace_id=requirement.workspace_id,
        entity_type="process_route",
        entity_id=route.id,
        action="process_route_created",
        changed_fields=list(values),
        change_data=creation_change_data(values),
        actor_user_id=current_user.id,
    )
    return GaiboProcessRouteResponse.model_validate(route, from_attributes=True)


@router.patch("/process-routes/{route_id}", response_model=GaiboProcessRouteResponse)
async def update_process_route(
    route_id: int,
    payload: GaiboProcessRouteUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboProcessRouteResponse:
    require_role(current_user, min_level=2)
    route = await db.get(GaiboProcessRoute, route_id, options=[selectinload(GaiboProcessRoute.steps)])
    if not route:
        raise HTTPException(status_code=404, detail="工艺路线不存在")
    workspace_id = await db.scalar(
        select(GaiboCustomerRequirement.workspace_id).where(GaiboCustomerRequirement.id == route.requirement_id)
    )
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="客户单件需求不存在")
    updates = payload.model_dump(exclude_unset=True)
    _check_updated_at(route, updates.pop("expected_updated_at", None))
    _normalize_required_text_updates(updates, {"version": "工艺版本", "status": "工艺状态"})
    next_steps = updates.pop("steps", None)
    if updates.get("is_current"):
        await _demote_current_routes(
            db,
            requirement_id=route.requirement_id,
            workspace_id=workspace_id,
            except_route_id=route.id,
            actor_user_id=current_user.id,
        )
    changed, data = _changed_values(route, updates)
    if next_steps is not None:
        before_steps = [GaiboProcessStepResponse.model_validate(step, from_attributes=True).model_dump() for step in route.steps]
        route.steps.clear()
        route.steps.extend(GaiboProcessStep(**step) for step in next_steps)
        changed.append("steps")
        data["steps"] = {"before": before_steps, "after": next_steps}
    if changed:
        _add_change_log(db, workspace_id=workspace_id, entity_type="process_route", entity_id=route.id, action="process_route_updated", changed_fields=changed, change_data=data, actor_user_id=current_user.id)
        await _flush_or_conflict(db, "当前单件已存在相同的工艺版本或步骤顺序")
    return GaiboProcessRouteResponse.model_validate(route, from_attributes=True)


@router.post("/requirements/{requirement_id}/documents", response_model=GaiboDocumentStatusResponse, status_code=201)
async def create_requirement_document(
    requirement_id: int,
    payload: GaiboDocumentStatusCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboDocumentStatusResponse:
    require_role(current_user, min_level=2)
    requirement = await db.get(GaiboCustomerRequirement, requirement_id)
    if not requirement or not requirement.is_active:
        raise HTTPException(status_code=404, detail="客户单件需求不存在")
    document = GaiboDocumentStatus(requirement_id=requirement.id, **payload.model_dump())
    document.source_data = append_status_event({}, status=document.status, document_type=document.document_type)
    db.add(document)
    await _flush_or_conflict(db, "当前单件已存在相同的资料类型")
    values = payload.model_dump()
    _add_change_log(
        db,
        workspace_id=requirement.workspace_id,
        entity_type="document",
        entity_id=document.id,
        action="document_created",
        changed_fields=list(values),
        change_data=creation_change_data(values),
        actor_user_id=current_user.id,
    )
    return _document_response(document)


@router.post("/packages/{package_id}/documents", response_model=GaiboDocumentStatusResponse, status_code=201)
async def create_package_document(
    package_id: int,
    payload: GaiboDocumentStatusCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboDocumentStatusResponse:
    require_role(current_user, min_level=2)
    package = await db.get(GaiboInstallationPackage, package_id)
    if not package or not package.is_active:
        raise HTTPException(status_code=404, detail="安装包档案不存在")
    document = GaiboDocumentStatus(package_id=package.id, **payload.model_dump())
    document.source_data = append_status_event({}, status=document.status, document_type=document.document_type)
    db.add(document)
    await _flush_or_conflict(db, "当前安装包已存在相同的资料类型")
    values = payload.model_dump()
    _add_change_log(
        db,
        workspace_id=package.workspace_id,
        entity_type="document",
        entity_id=document.id,
        action="document_created",
        changed_fields=list(values),
        change_data=creation_change_data(values),
        actor_user_id=current_user.id,
    )
    return _document_response(document)


@router.patch("/documents/{document_id}", response_model=GaiboDocumentStatusResponse)
async def update_document(
    document_id: int,
    payload: GaiboDocumentStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GaiboDocumentStatusResponse:
    require_role(current_user, min_level=2)
    document = await db.get(GaiboDocumentStatus, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="资料状态不存在")
    workspace_id: int | None = None
    if document.requirement_id:
        workspace_id = await db.scalar(select(GaiboCustomerRequirement.workspace_id).where(GaiboCustomerRequirement.id == document.requirement_id))
    elif document.package_id:
        workspace_id = await db.scalar(select(GaiboInstallationPackage.workspace_id).where(GaiboInstallationPackage.id == document.package_id))
    if workspace_id is None:
        raise HTTPException(status_code=409, detail="资料状态缺少所属客户")
    updates = payload.model_dump(exclude_unset=True)
    _check_updated_at(document, updates.pop("expected_updated_at", None))
    _normalize_required_text_updates(updates, {"document_type": "资料类型", "status": "资料状态"})
    next_document_type = updates.get("document_type", document.document_type)
    next_status = updates.get("status")
    if next_status is not None:
        document.source_data = append_status_event(
            document.source_data,
            status=next_status,
            document_type=next_document_type,
        )
    changed, data = _changed_values(document, updates)
    if changed:
        _add_change_log(db, workspace_id=workspace_id, entity_type="document", entity_id=document.id, action="document_updated", changed_fields=changed, change_data=data, actor_user_id=current_user.id)
        await _flush_or_conflict(db, "当前档案已存在相同的资料类型")
    return _document_response(document)


@router.get("/history", response_model=list[GaiboChangeLogResponse])
async def list_history(
    db: DbSession,
    current_user: CurrentUser,
    workspace_id: Optional[int] = Query(default=None, gt=0),
    entity_type: Optional[str] = Query(default=None, max_length=50),
    entity_id: Optional[int] = Query(default=None, gt=0),
) -> list[GaiboChangeLogResponse]:
    require_role(current_user, min_level=1)
    conditions = []
    if workspace_id is not None:
        conditions.append(GaiboChangeLog.workspace_id == workspace_id)
    if entity_type:
        conditions.append(GaiboChangeLog.entity_type == entity_type)
    if entity_id is not None:
        conditions.append(GaiboChangeLog.entity_id == entity_id)
    result = await db.scalars(select(GaiboChangeLog).where(*conditions).order_by(GaiboChangeLog.created_at.desc()).limit(200))
    return [GaiboChangeLogResponse.model_validate(row, from_attributes=True) for row in result]
