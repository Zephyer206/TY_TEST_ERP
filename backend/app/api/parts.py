"""Parts API endpoints - 匹配实际数据库字段."""

from datetime import datetime
from functools import lru_cache
import json
from pathlib import Path
from collections import defaultdict
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.customer import Customer
from app.models.part import Part
from app.models.tooling import Tooling, ToolingPart
from app.models.part_customer_alias import PartCustomerAlias
from app.models.part_tooling_spec import PartToolingSpec
from app.models.excel_import import ExcelImportRow
from app.models.material_dict import MaterialDict
from app.models.user import User
from app.models.packaging import Inventory
from app.schemas.part import (
    PartCreate,
    PartDisplayGroup,
    PartDisplayPage,
    PartResponse,
    PartUpdate,
)
from app.schemas.part_editor import (
    PartEditorUpdateRequest,
    PartEditorUpdateResponse,
    PartEditorConflictDetail,
    PartEditorConflictResponse,
)

router = APIRouter(prefix="/parts", tags=["Parts"])


def _summarize_mold_types(values) -> Optional[str]:
    """Return the distinct mold types associated with a part.

    Mold type is authoritative on the linked tooling records.  A part can
    have more than one tooling, so keep all distinct source values rather
    than copying one arbitrary value into the part row.
    """
    mold_types = sorted({
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip()
    })
    return " / ".join(mold_types) or None


def _summarize_cavity_counts(values) -> Optional[str]:
    """Return distinct positive cavity counts from linked tooling records."""
    cavity_counts = set()
    for value in values:
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            cavity_counts.add(count)
    return " / ".join(str(count) for count in sorted(cavity_counts)) or None


def _select_primary_tooling(tooling_records):
    """Select the tooling shown as the part-list primary mold.

    A part may have both a continuous mold and a simple mold.  The continuous
    mold is the business primary whenever one exists; within that type, keep
    the explicit ``is_primary`` relation as the tie-breaker.  If no continuous
    mold exists, preserve the existing primary relation.
    """
    if not tooling_records:
        return None

    continuous_records = [
        record for record in tooling_records
        if record[1].is_continuous
    ]
    preferred_records = continuous_records or tooling_records
    return sorted(
        preferred_records,
        key=lambda record: (
            not record[0].is_primary,
            str(record[1].tooling_number or ""),
            record[1].id,
        ),
    )[0]


def _select_primary_twp(twp_options):
    """Return the sole explicit primary TWP option, otherwise no selection.

    A missing or invalid primary must remain visible as unresolved rather than
    silently choosing the first source row or borrowing a different tooling's
    specification.
    """
    primary_options = [option for option in twp_options if option.is_primary]
    return primary_options[0] if len(primary_options) == 1 else None


def _select_display_twp(twp_options):
    """Select a list-display TWP without inventing a cross-tooling primary.

    An explicit primary always wins.  When the selected tooling has exactly
    one source-backed option, that option is also unambiguous for display, but
    it remains unmarked as a primary in the database.
    """
    primary = _select_primary_twp(twp_options)
    if primary is not None:
        return primary
    return twp_options[0] if len(twp_options) == 1 else None


async def _load_hidden_simple_part_ids(db) -> set[int]:
    """Find simple-only part records hidden by a continuous counterpart.

    The source data can represent one customer part number with more than one
    internal ``parts`` row.  Grouping is therefore based on the authoritative
    customer + active customer-part-number relation, not on a guessed suffix
    or on the internal row id.
    """
    rows = (await db.execute(
        select(
            PartCustomerAlias.customer_id,
            PartCustomerAlias.customer_part_no,
            ToolingPart.part_id,
            Tooling.is_continuous,
        )
        .join(ToolingPart, ToolingPart.part_id == PartCustomerAlias.part_id)
        .join(Tooling, Tooling.id == ToolingPart.tooling_id)
        .where(
            PartCustomerAlias.is_active == True,
            Tooling.is_deleted == False,
            PartCustomerAlias.customer_part_no.is_not(None),
            PartCustomerAlias.customer_part_no != "",
        )
    )).all()

    grouped = {}
    for customer_id, customer_part_no, part_id, is_continuous in rows:
        identity = (customer_id, customer_part_no.strip())
        entry = grouped.setdefault(identity, {"continuous": set(), "simple": set()})
        entry["continuous" if is_continuous else "simple"].add(part_id)

    hidden = set()
    continuous_part_ids = set()
    for entry in grouped.values():
        if entry["continuous"] and entry["simple"]:
            continuous_part_ids.update(entry["continuous"])
            hidden.update(entry["simple"])

    # A part that is continuous for one authoritative customer-part identity
    # must remain visible even if another alias also has a simple-only link.
    return hidden - continuous_part_ids


async def _load_cavity_evidence(db, tooling_numbers: set[str]) -> dict[str, list[Optional[int]]]:
    """Load source-row cavity evidence for tooling numbers.

    A tooling number can occur on several Excel rows (different operations or
    material specifications).  A positive cavity value is displayable only
    when every imported source row for that tooling number has an explicit
    cavity value.  Mixed explicit/blank source rows are intentionally treated
    as unknown so one specification cannot leak its cavity count into another.
    """
    if not tooling_numbers:
        return {}

    rows = (await db.execute(
        select(
            ExcelImportRow.parsed_tooling_number,
            ExcelImportRow.parsed_cavity_count,
        )
        .where(
            ExcelImportRow.validation_status == "IMPORTED",
            ExcelImportRow.parsed_tooling_number.in_(tooling_numbers),
        )
    )).all()

    evidence: dict[str, list[Optional[int]]] = {}
    for tooling_number, cavity_count in rows:
        evidence.setdefault(tooling_number, []).append(cavity_count)
    return evidence


def _has_complete_cavity_evidence(
    tooling_number: Optional[str],
    evidence: dict[str, list[Optional[int]]],
) -> bool:
    values = evidence.get(tooling_number or "")
    return bool(values) and all(value is not None for value in values)


def _resolve_customer_product_fields(
    aliases: list[PartCustomerAlias],
    canonical_no: Optional[str],
    canonical_name: Optional[str],
    customer_id: Optional[int] = None,
    search: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve display customer part fields without overwriting canonical data.

    Customer part numbers are customer-specific aliases, not global part
    numbers.  When a customer filter is active, use that customer's alias;
    otherwise show all distinct active aliases so a known part number is not
    rendered as missing.
    """
    active_aliases = [
        alias for alias in aliases
        if alias.is_active and alias.data_quality_status == "approved" and (
            (alias.customer_part_no and alias.customer_part_no.strip())
            or (alias.customer_part_name and alias.customer_part_name.strip())
        )
    ]
    if customer_id is not None:
        active_aliases = [
            alias for alias in active_aliases
            if alias.customer_id == customer_id
        ]

    # When a search term is present, keep the list row focused on aliases that
    # contain it. Do not narrow the result to an exact alias: every search
    # field in the parts workspace uses contains matching.
    normalized_search = search.strip().lower() if search and search.strip() else None
    if normalized_search:
        matching_aliases = [
            alias for alias in active_aliases
            if (alias.customer_part_no and normalized_search in alias.customer_part_no.lower())
            or (alias.customer_part_name and normalized_search in alias.customer_part_name.lower())
        ]
        if matching_aliases:
            active_aliases = matching_aliases

    alias_numbers = []
    alias_names = []
    for alias in active_aliases:
        if alias.customer_part_no and alias.customer_part_no.strip():
            value = alias.customer_part_no.strip()
            if value not in alias_numbers:
                alias_numbers.append(value)
        if alias.customer_part_name and alias.customer_part_name.strip():
            value = alias.customer_part_name.strip()
            if value not in alias_names:
                alias_names.append(value)

    display_no = canonical_no.strip() if canonical_no and canonical_no.strip() else None
    display_name = canonical_name.strip() if canonical_name and canonical_name.strip() else None
    return (
        display_no or " / ".join(alias_numbers) or None,
        display_name or " / ".join(alias_names) or None,
    )


async def _part_tooling_summary(db, part_id: int) -> tuple[Optional[str], Optional[str]]:
    """Resolve display tooling number and type from active tooling links."""
    result = await db.execute(
        select(Tooling.tooling_number, Tooling.mold_type)
        .join(ToolingPart, ToolingPart.tooling_id == Tooling.id)
        .where(
            ToolingPart.part_id == part_id,
            Tooling.is_deleted == False,
        )
        .order_by(
            ToolingPart.is_primary.desc(),
            Tooling.is_continuous.desc(),
            ToolingPart.sequence,
            Tooling.id,
        )
    )
    rows = result.all()
    if not rows:
        return None, None
    tooling_number = rows[0][0]
    return tooling_number, _summarize_mold_types(value for _, value in rows)


def _customer_name_search_part_ids(search: str):
    """Return parts linked to customers whose name or code matches search."""
    pattern = f"%{search}%"
    return select(PartCustomerAlias.part_id).join(
        Customer, Customer.id == PartCustomerAlias.customer_id
    ).where(
        PartCustomerAlias.is_active == True,
        PartCustomerAlias.data_quality_status == "approved",
        or_(
            Customer.name.ilike(pattern),
            Customer.customer_code.ilike(pattern),
            Customer.short_name.ilike(pattern),
        )
    )


def _apply_part_filters(
    q,
    search,
    customer_id,
    part_status,
    material,
):
    """Apply the shared parts-list filters to a SELECT statement."""
    # Soft-deleted repair/import duplicates must never appear in list or count
    # endpoints.  Historical rows remain auditable in the database, but are
    # excluded from the active ERP UI.
    q = q.where(Part.is_deleted == False)
    if search and search.strip():
        search_term = search.strip()
        customer_alias_subq = select(PartCustomerAlias.part_id).where(
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.data_quality_status == "approved",
            or_(
                PartCustomerAlias.customer_part_no.ilike(f"%{search_term}%"),
                PartCustomerAlias.customer_part_name.ilike(f"%{search_term}%"),
            ),
        )
        customer_alias_filter = Part.id.in_(customer_alias_subq)
        tooling_subq = select(ToolingPart.part_id).join(
            Tooling, ToolingPart.tooling_id == Tooling.id
        ).where(
            or_(
                Tooling.tooling_number.ilike(f"%{search_term}%"),
            )
        )
        q = q.where(or_(
            Part.internal_part_no.ilike(f"%{search_term}%"),
            Part.internal_name.ilike(f"%{search_term}%"),
            Part.customer_part_no.ilike(f"%{search_term}%"),
            Part.customer_part_name.ilike(f"%{search_term}%"),
            customer_alias_filter,
            Part.id.in_(_customer_name_search_part_ids(search_term)),
            Part.id.in_(tooling_subq),
        ))

    if customer_id:
        customer_part_subq = select(PartCustomerAlias.part_id).where(
            PartCustomerAlias.customer_id == customer_id
        )
        q = q.where(Part.id.in_(customer_part_subq))

    if part_status:
        q = q.where(Part.part_status == part_status)
    else:
        # The active parts workspace must not show retired records.  Older
        # delete operations only changed part_status to OBSOLETE, so keep the
        # default list clean even for those historical soft-deleted rows.
        q = q.where(func.upper(Part.part_status) != "OBSOLETE")
    if material:
        q = q.where(Part.material_name.ilike(f"%{material}%"))

    return q


async def _to_resp(db, p: Part) -> PartResponse:
    aliases_result = await db.execute(
        select(PartCustomerAlias).where(
            PartCustomerAlias.part_id == p.id,
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.data_quality_status == "approved",
        )
    )
    aliases = list(aliases_result.scalars())
    customer_part_no, customer_part_name = _resolve_customer_product_fields(aliases, None, None)
    customer_ids = {alias.customer_id for alias in aliases}
    customers = {
        customer.id: customer
        for customer in (await db.execute(select(Customer).where(Customer.id.in_(customer_ids)))).scalars()
    } if customer_ids else {}
    customer = next(iter(customers.values()), None)
    tooling_number, tooling_type = await _part_tooling_summary(db, p.id)
    inventory_row = (
        await db.execute(
            select(func.count(Inventory.id), func.coalesce(func.sum(Inventory.stock_qty), 0))
            .where(Inventory.part_id == p.id)
        )
    ).one()
    stock_pcs = int(inventory_row[1] or 0) if inventory_row[0] else int(p.stock_pcs or 0)
    return PartResponse(
        id=p.id,
        part_name=p.internal_name,
        customer_id=customer.id if customer else None,
        customer_name=customer.name if customer else None,
        customer_part_no=customer_part_no,
        customer_part_name=customer_part_name,
        vehicle_model=p.vehicle_model,
        material_name=p.material_name,
        part_status=p.part_status,
        stock_pcs=stock_pcs,
        tooling_number=tooling_number,
        tooling_type=tooling_type,
        press_tonnage=p.press_tonnage,
        ppap_no=p.ppap_no,
        thickness=float(p.thickness) if p.thickness else None,
        width=float(p.width) if p.width else None,
        pitch=float(p.pitch) if p.pitch else None,
        spec_twph=p.spec_twph,
        part_position=p.part_position,
        remark=p.remark,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def _build_part_responses(
    db,
    parts: list[Part],
    filter_customer_id: Optional[int] = None,
    filter_search: Optional[str] = None,
) -> list[PartResponse]:
    """Build list-page responses with relation-based customer/tooling summaries.

    When filter_customer_id is provided, populate customer_part_no/customer_part_name
    from that customer's active aliases as a fallback for display when canonical fields are NULL.
    """
    if not parts:
        return []

    part_ids = [p.id for p in parts]

    inventory_rows = (
        await db.execute(
            select(
                Inventory.part_id,
                func.sum(Inventory.stock_qty).label("stock_qty"),
            )
            .where(Inventory.part_id.in_(part_ids))
            .group_by(Inventory.part_id)
        )
    ).all()
    inventory_stock_by_part = {
        part_id: int(stock_qty or 0)
        for part_id, stock_qty in inventory_rows
    }

    customer_aliases = {}
    aliases_result = await db.execute(
        select(PartCustomerAlias).where(PartCustomerAlias.part_id.in_(part_ids))
    )
    for alias in aliases_result.scalars():
        customer_aliases.setdefault(alias.part_id, []).append(alias)

    cust_ids = list({
        alias.customer_id
        for aliases in customer_aliases.values()
        for alias in aliases
    })
    customers = {}
    if cust_ids:
        customers = {c.id: c for c in (await db.execute(
            select(Customer).where(Customer.id.in_(cust_ids))
        )).scalars()}

    tooling_parts_map = {}
    tp_result = await db.execute(
        select(ToolingPart).where(ToolingPart.part_id.in_(part_ids))
    )
    for tp in tp_result.scalars():
        tooling_parts_map.setdefault(tp.part_id, []).append(tp)

    tooling_ids = list({
        tp.tooling_id
        for tps in tooling_parts_map.values()
        for tp in tps
    })
    toolings = {}
    if tooling_ids:
        toolings = {t.id: t for t in (await db.execute(
            select(Tooling).where(Tooling.id.in_(tooling_ids))
        )).scalars()}

    # Load TWP specs keyed by (part_id, tooling_id) for selected-tooling lookup
    specs_by_key: dict[tuple[int, int], list[PartToolingSpec]] = {}
    if part_ids:
        specs_result = await db.execute(
            select(PartToolingSpec)
            .where(PartToolingSpec.part_id.in_(part_ids))
            .order_by(PartToolingSpec.source_row, PartToolingSpec.id)
        )
        for spec in specs_result.scalars().all():
            specs_by_key.setdefault((spec.part_id, spec.tooling_id), []).append(spec)

    cavity_evidence = await _load_cavity_evidence(
        db,
        {
            toolings[tp.tooling_id].tooling_number
            for tps in tooling_parts_map.values()
            for tp in tps
            if tp.tooling_id in toolings
        },
    )

    material_ids = list({p.material_id for p in parts if p.material_id})
    materials = {}
    if material_ids:
        materials = {m.id: m for m in (await db.execute(
            select(MaterialDict).where(MaterialDict.id.in_(material_ids))
        )).scalars()}

    results = []
    for p in parts:
        aliases = customer_aliases.get(p.id, [])
        customer_summary = None
        if aliases:
            names = sorted({
                customers[a.customer_id].name
                for a in aliases
                if a.customer_id in customers
            })
            customer_summary = ", ".join(names[:3])
            if len(names) > 3:
                customer_summary += f" (+{len(names) - 3})"

        customer_part_no_display, customer_part_name_display = _resolve_customer_product_fields(
            aliases,
            None,
            None,
            customer_id=filter_customer_id,
            search=filter_search,
        )

        tps = tooling_parts_map.get(p.id, [])
        mold_summary = None
        mold_type_summary = None
        cavity_count_summary = None
        primary_tooling_id = None

        if tps:
            tooling_records = [
                (tp, toolings[tp.tooling_id])
                for tp in tps
                if tp.tooling_id in toolings
            ]
            primary_record = _select_primary_tooling(tooling_records)
            if primary_record:
                primary_tp, primary_tooling = primary_record
                primary_tooling_id = primary_tooling.id
                mold_summary = (
                    primary_tooling.tooling_number
                )
                mold_type_summary = primary_tooling.mold_type
                primary_tooling_number = (
                    primary_tooling.tooling_number
                )
                if _has_complete_cavity_evidence(
                    primary_tooling_number,
                    cavity_evidence,
                ):
                    cavity_count_summary = _summarize_cavity_counts(
                        [primary_tooling.cavity_count]
                    )

        # TWP display logic: use primary spec from selected tooling only
        selected_tooling_specs = specs_by_key.get((p.id, primary_tooling_id), []) if primary_tooling_id else []
        # Count all TWP options across all toolings for this part
        all_twp_count = sum(len(specs) for key, specs in specs_by_key.items() if key[0] == p.id)
        primary_spec = _select_primary_twp(selected_tooling_specs)
        display_twp = _select_display_twp(selected_tooling_specs)

        # Use the part-row TWP values only when no source-backed option exists
        # for this part. Never borrow another tooling's TWP or hide an
        # unresolved continuous-tooling conflict behind a different source.
        display_spec = display_twp.spec_twph if display_twp else (p.spec_twph if all_twp_count == 0 else None)
        display_thickness = (
            display_twp.thickness if display_twp else (p.thickness if all_twp_count == 0 else None)
        )
        display_width = display_twp.width if display_twp else (p.width if all_twp_count == 0 else None)
        display_pitch = display_twp.pitch if display_twp else (p.pitch if all_twp_count == 0 else None)

        results.append(PartResponse(
            id=p.id,
            part_name=p.internal_name,
            customer_id=None,
            customer_name=customer_summary,
            customer_part_no=customer_part_no_display,
            customer_part_name=customer_part_name_display,
            vehicle_model=p.vehicle_model,
            material_name=p.material_name,
            material_name_full=materials[p.material_id].name if p.material_id in materials else None,
            part_status=p.part_status,
            stock_pcs=inventory_stock_by_part.get(p.id, int(p.stock_pcs or 0)),
            tooling_number=mold_summary,
            tooling_type=mold_type_summary,
            press_tonnage=p.press_tonnage,
            ppap_no=p.ppap_no,
            spec_twph=display_spec,
            thickness=display_thickness,
            width=display_width,
            pitch=display_pitch,
            twp_options_count=all_twp_count,
            has_primary_twp=primary_spec is not None,
            height=p.height,
            gross_weight=p.gross_weight,
            net_weight=p.net_weight,
            part_position=p.part_position,
            cavity_count=cavity_count_summary,
            remark=p.remark,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))

    return results


async def _load_left_right_pair_lookup(db):
    """Return only explicitly documented multi-output left/right pairs.

    A trailing ``-1``/``-2`` is a part/tooling identifier convention in the
    source workbook, not evidence that one press stroke produces two parts.
    It may be used to locate the two sides of a candidate family, but a pair
    is eligible for display grouping only when both sides have a linked
    tooling record with an explicit cavity count greater than one.
    """
    rows = (await db.execute(
        select(
            ToolingPart.part_id,
            Tooling.tooling_number,
            Part.part_position,
            Tooling.cavity_count,
        )
        .join(Tooling, ToolingPart.tooling_id == Tooling.id)
        .join(Part, Part.id == ToolingPart.part_id)
        .where(
            Part.part_position.in_(["left", "right"]),
            Tooling.is_deleted == False,
            Tooling.cavity_count > 1,
        )
    )).all()

    cavity_evidence = await _load_cavity_evidence(
        db,
        {
            tooling_number
            for _, tooling_number, _, _ in rows
            if tooling_number
        },
    )

    candidates = {}
    for part_id, tooling_number, position, cavity_count in rows:
        if not tooling_number or not tooling_number.endswith(("-1", "-2")):
            continue
        if not _has_complete_cavity_evidence(tooling_number, cavity_evidence):
            continue
        base_number = tooling_number[:-2]
        candidates.setdefault(base_number, {}).setdefault(position, set()).add(part_id)

    lookup = {}
    for base_number, positions in candidates.items():
        left_ids = positions.get("left", set())
        right_ids = positions.get("right", set())
        if len(left_ids) != 1 or len(right_ids) != 1:
            continue
        left_id = next(iter(left_ids))
        right_id = next(iter(right_ids))
        if left_id == right_id:
            continue
        member_ids = [left_id, right_id]
        lookup[left_id] = (base_number, member_ids)
        lookup[right_id] = (base_number, member_ids)

    return lookup


@lru_cache(maxsize=1)
def _load_audited_source_groups() -> list[dict]:
    """Load the read-only Excel audit produced for shared source blocks.

    The audit is generated from the authoritative workbook and contains only
    mergeable groups.  If it is absent (for example, before an import audit
    has been run) the endpoint safely falls back to the legacy left/right
    grouping behavior.
    """
    path = Path(__file__).resolve().parents[3] / "scripts" / "analysis" / "shared_mold_blocks_audit.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return []
    return [group for group in payload.get("groups", []) if group.get("classification") == "mergeable"]


async def _load_persistent_group_lookup(db) -> dict[int, tuple[str, str, list[int]]]:
    """Load active persistent PartDisplayGroupDef/Member records as display groups.

    Returns a lookup mapping part_id -> (group_key, group_type, member_part_ids).
    Active persistent groups take precedence over legacy inferred/audit grouping.
    """
    from app.models.part_display_group import PartDisplayGroupDef, PartDisplayGroupMember

    result = await db.execute(
        select(PartDisplayGroupDef)
        .where(PartDisplayGroupDef.is_active == True)
        .options(selectinload(PartDisplayGroupDef.members))
    )
    groups = result.scalars().all()

    lookup: dict[int, tuple[str, str, list[int]]] = {}
    for group in groups:
        # Preserve explicit member ordering by sequence, then member id
        sorted_members = sorted(group.members, key=lambda m: (m.sequence, m.id))
        member_ids = [m.part_id for m in sorted_members]
        if len(member_ids) < 1:
            continue
        for part_id in member_ids:
            lookup[part_id] = (group.group_key, group.group_type, member_ids)

    return lookup


async def _load_source_group_lookup(db) -> dict[int, tuple[str, list[int]]]:
    """Map resolved part ids to audited shared-source display groups.

    ExcelImportRow retains the authoritative sheet/row and resolved formal
    ids.  We use those links to apply the audit result without changing or
    merging the underlying parts/tooling rows.
    """
    audited_groups = _load_audited_source_groups()
    if not audited_groups:
        return {}

    row_to_group: dict[tuple[str, int], str] = {}
    group_rows: dict[str, list[dict]] = {}
    for index, group in enumerate(audited_groups):
        key = f"source:{group.get('sheet_index', index)}:{','.join(str(row) for row in group.get('rows', []))}"
        group_rows[key] = group.get("parts", [])
        for part in group.get("parts", []):
            try:
                row_to_group[(group.get("sheet", ""), int(part["row"]))] = key
            except (KeyError, TypeError, ValueError):
                continue

    if not row_to_group:
        return {}

    rows = (await db.execute(
        select(
            ExcelImportRow.source_sheet,
            ExcelImportRow.source_row,
            ExcelImportRow.resolved_part_id,
            ExcelImportRow.resolved_tooling_id,
            ExcelImportRow.validation_status,
        ).where(ExcelImportRow.validation_status == "IMPORTED")
    )).all()

    members_by_group: dict[str, set[int]] = defaultdict(set)
    toolings_by_group: dict[str, set[int]] = defaultdict(set)
    for source_sheet, source_row, part_id, tooling_id, _status in rows:
        key = row_to_group.get((source_sheet, source_row))
        if not key or part_id is None or tooling_id is None:
            continue
        members_by_group[key].add(part_id)
        toolings_by_group[key].add(tooling_id)

    # A display group is valid only when the formal links preserve the audit's
    # distinct part and tooling identities.  Ambiguous/partial resolutions are
    # intentionally excluded and remain visible as independent rows.
    lookup: dict[int, tuple[str, list[int]]] = {}
    claimed_parts: set[int] = set()
    for key in sorted(members_by_group):
        member_ids = sorted(members_by_group[key])
        if len(member_ids) < 2 or len(toolings_by_group[key]) < 2:
            continue
        if claimed_parts.intersection(member_ids):
            continue
        claimed_parts.update(member_ids)
        for part_id in member_ids:
            lookup[part_id] = (key, member_ids)
    return lookup


@router.get("/count")
async def count_parts(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None, description="Customer name/code, customer part number, part name, or tooling number"),
    customer_id: Optional[int] = Query(default=None),
    part_status: Optional[str] = Query(default=None),
    material: Optional[str] = Query(default=None),
) -> dict[str, int]:
    """Count parts with the same filters as list_parts - returns total distinct parts."""
    q = _apply_part_filters(
        select(Part.id), search, customer_id, part_status, material,
    )

    # Count distinct parts
    result = await db.execute(select(distinct(Part.id)).select_from(Part).where(Part.id.in_(q)))
    total = len(result.all())

    return {"total": total}


@router.get("", response_model=list[PartResponse])
async def list_parts(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None, description="Customer name/code, customer part number, part name, or tooling number"),
    customer_id: Optional[int] = Query(default=None),
    part_status: Optional[str] = Query(default=None),
    material: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PartResponse]:
    q = _apply_part_filters(
        select(Part), search, customer_id, part_status, material,
    )

    # Stable ordering: created_at DESC, then id DESC for deterministic pagination
    q = q.order_by(Part.created_at.desc().nulls_last(), Part.id.desc()).offset(skip).limit(limit)
    parts = (await db.execute(q)).scalars().all()
    return await _build_part_responses(
        db,
        parts,
        filter_customer_id=customer_id,
        filter_search=search,
    )


@router.get("/grouped", response_model=PartDisplayPage)
async def list_grouped_parts(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None, description="Customer name/code, customer part number, part name, or tooling number"),
    customer_id: Optional[int] = Query(default=None),
    part_status: Optional[str] = Query(default=None),
    material: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> PartDisplayPage:
    """List parts as display groups, merging valid left/right pairs into one row.

    Pairing is intentionally strict: both parts must have explicit left/right
    positions, same-base ``-1``/``-2`` identifiers, and linked tooling records
    with an explicit cavity count greater than one.  The suffix alone never
    creates a one-out-two display group. Filtering matches either member and
    returns the complete pair.
    """
    id_query = _apply_part_filters(
        select(Part.id), search, customer_id, part_status, material,
    ).order_by(Part.created_at.desc().nulls_last(), Part.id.desc())
    filtered_ids = list((await db.execute(id_query)).scalars().all())
    hidden_simple_part_ids = await _load_hidden_simple_part_ids(db)
    filtered_ids = [part_id for part_id in filtered_ids if part_id not in hidden_simple_part_ids]

    persistent_group_lookup = await _load_persistent_group_lookup(db)
    pair_lookup = await _load_left_right_pair_lookup(db)
    source_group_lookup = await _load_source_group_lookup(db)
    descriptors = []
    seen_groups = set()

    for part_id in filtered_ids:
        # Explicit persistent groups take precedence
        persistent_info = persistent_group_lookup.get(part_id)
        if persistent_info:
            persistent_key, persistent_type, member_ids = persistent_info
            if persistent_key in seen_groups:
                continue
            seen_groups.add(persistent_key)
            # Use explicit group_type from database, never infer from key prefix
            is_pair = persistent_type == "left_right"
            is_source = persistent_type == "shared_source"
            descriptors.append((persistent_key, is_pair, is_source, member_ids))
            continue

        source_info = source_group_lookup.get(part_id)
        if source_info:
            source_key, member_ids = source_info
            if source_key in seen_groups:
                continue
            seen_groups.add(source_key)
            descriptors.append((source_key, False, True, member_ids))
            continue

        pair_info = pair_lookup.get(part_id)
        if pair_info:
            base_number, member_ids = pair_info
            pair_key = f"pair:{base_number}"
            if pair_key in seen_groups:
                continue
            seen_groups.add(pair_key)
            descriptors.append((pair_key, True, False, member_ids))
        else:
            descriptors.append((f"part:{part_id}", False, False, [part_id]))

    total = len(descriptors)
    page_descriptors = descriptors[skip:skip + limit]
    selected_ids = list({
        part_id
        for _, _, _, member_ids in page_descriptors
        for part_id in member_ids
    })

    if not selected_ids:
        return PartDisplayPage(total=total, items=[])

    selected_parts = (await db.execute(
        select(Part).where(Part.id.in_(selected_ids))
    )).scalars().all()
    selected_parts.sort(
        key=lambda p: (
            0 if p.part_position == "left" else 1 if p.part_position == "right" else 2,
            p.id,
        )
    )
    responses = await _build_part_responses(
        db,
        selected_parts,
        filter_customer_id=customer_id,
        filter_search=search,
    )
    response_by_id = {response.id: response for response in responses}

    items = []
    for key, is_pair, is_source_group, member_ids in page_descriptors:
        members = [response_by_id[part_id] for part_id in member_ids if part_id in response_by_id]
        if not members:
            continue
        items.append(PartDisplayGroup(
            key=key,
            is_left_right_pair=is_pair and len(members) == 2,
            is_shared_source_group=is_source_group and len(members) > 1,
            members=members,
        ))

    return PartDisplayPage(total=total, items=items)


@router.post("", response_model=PartResponse, status_code=status.HTTP_201_CREATED)
async def create_part(data: PartCreate, db: DbSession, current_user: CurrentUser) -> PartResponse:
    await require_role(2)(current_user)
    """
    existing = (await db.execute(select(Part).where(Part.id == -1))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="零件编号已存在")
    """
    part = Part(
        internal_name=data.internal_name,
        vehicle_model=data.vehicle_model,
        material_name=data.material_name,
        remark=data.remark,
        part_status="DRAFT",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(part)
    await db.flush()
    if data.customer_id and data.customer_part_no:
        from app.services.part_identity_service import upsert_part_alias
        await upsert_part_alias(
            db,
            part_id=part.id,
            customer_id=data.customer_id,
            customer_part_no=data.customer_part_no,
            customer_part_name=data.customer_part_name,
            vehicle_model=data.vehicle_model,
        )
    await db.commit()
    await db.refresh(part)
    return await _to_resp(db, part)


@router.get("/{part_id}", response_model=PartResponse)
async def get_part(part_id: int, db: DbSession, current_user: CurrentUser) -> PartResponse:
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return await _to_resp(db, part)


@router.patch("/{part_id}", response_model=PartResponse)
async def update_part(part_id: int, data: PartUpdate, db: DbSession, current_user: CurrentUser) -> PartResponse:
    await require_role(2)(current_user)
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    update_data = data.model_dump(exclude_unset=True)
    alias_fields = {"customer_id", "customer_part_no", "customer_part_name"}
    for field, value in update_data.items():
        if field not in alias_fields:
            setattr(part, field, value)
    if data.customer_id and data.customer_part_no:
        from app.services.part_identity_service import upsert_part_alias
        await upsert_part_alias(
            db,
            part_id=part.id,
            customer_id=data.customer_id,
            customer_part_no=data.customer_part_no,
            customer_part_name=data.customer_part_name,
            vehicle_model=data.vehicle_model,
        )
    part.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(part)
    return await _to_resp(db, part)


@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part(part_id: int, db: DbSession, current_user: CurrentUser) -> None:
    await require_role(2)(current_user)
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    # 软删除：保留历史记录，但从所有默认业务列表中隐藏。
    part.part_status = "OBSOLETE"
    part.is_deleted = True
    part.updated_at = datetime.utcnow()
    await db.commit()
