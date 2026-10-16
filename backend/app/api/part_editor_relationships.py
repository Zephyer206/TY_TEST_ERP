"""Stage 3 Part Editor - Relationship Management APIs.

Provides atomic, transactional editing of:
- Customer aliases (upsert by ID, explicit deletes)
- Tooling-part associations (upsert by ID, explicit deletes)
- TWP specifications (upsert by ID preserving source fields, explicit deletes)

All operations use optimistic locking via expected_updated_at.
Source fields (source_sheet/source_row/source_note) are read-only and preserved during upsert.
Request schemas use extra='forbid' to reject source field inputs.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, delete, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.events import audit_event
from app.models.audit import AuditAction
from app.models.customer import Customer
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.models.part_tooling_spec import PartToolingSpec
from app.models.packaging import Inventory
from app.models.tooling import Tooling, ToolingPart
from app.schemas.part_editor_relationships import (
    CustomerAliasesUpdateRequest,
    CustomerAliasResponse,
    PartEditorBulkUpdateRequest,
    PartEditorBulkUpdateResponse,
    PartEditorDetailResponse,
    ToolingBriefInfo,
    ToolingPartItem,
    ToolingPartResponse,
    ToolingPartsUpdateRequest,
    TWPSpecItem,
    TWPSpecResponse,
    TWPSpecsUpdateRequest,
)

router = APIRouter(prefix="/parts", tags=["Part Editor - Relationships"])


# ==================== Helper Functions ====================

async def _validate_customer_ids(db: DbSession, customer_ids: list[int]) -> None:
    """Validate that all customer IDs exist."""
    if not customer_ids:
        return

    result = await db.execute(
        select(Customer.id).where(Customer.id.in_(customer_ids))
    )
    found_ids = {row[0] for row in result.fetchall()}
    missing = set(customer_ids) - found_ids

    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Customer IDs not found: {sorted(missing)}"
        )


async def _validate_tooling_ids(db: DbSession, tooling_ids: list[int]) -> dict[int, Tooling]:
    """Validate tooling IDs exist, not deleted, and return tooling map."""
    if not tooling_ids:
        return {}

    result = await db.execute(
        select(Tooling).where(Tooling.id.in_(tooling_ids))
    )
    toolings = result.scalars().all()
    tooling_map = {t.id: t for t in toolings}

    missing = set(tooling_ids) - set(tooling_map.keys())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tooling IDs not found: {sorted(missing)}"
        )

    # Check for deleted tooling
    deleted_ids = [tid for tid, t in tooling_map.items() if t.is_deleted]
    if deleted_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot associate deleted tooling: {sorted(deleted_ids)}"
        )

    return tooling_map


def _validate_primary_constraints(
    tooling_parts: list[ToolingPartItem],
    tooling_map: dict[int, Tooling]
) -> None:
    """Enforce primary tooling constraints.

    Rules:
    - Max one primary ToolingPart total across all toolings
    - If any linked tooling is continuous, that continuous tooling must be the primary
    """
    if not tooling_parts:
        return

    has_continuous = any(tooling_map[tp.tooling_id].is_continuous for tp in tooling_parts)
    primary_requested = [tp for tp in tooling_parts if tp.is_primary]

    if len(primary_requested) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most one tooling may be marked as primary. Found {len(primary_requested)} primaries."
        )

    if has_continuous and primary_requested:
        # The primary must be continuous
        primary_tp = primary_requested[0]
        if not tooling_map[primary_tp.tooling_id].is_continuous:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="When any tooling is continuous, only continuous toolings may be primary"
            )


def _validate_twp_primary_scope(specs: list[TWPSpecItem]) -> None:
    """Validate that each (part, tooling) has at most one primary spec.

    TWP primary is scoped to (part_id, tooling_id), not global.
    """
    tooling_primaries: dict[int, int] = {}  # tooling_id -> count of primaries

    for spec in specs:
        if spec.is_primary:
            tooling_primaries[spec.tooling_id] = tooling_primaries.get(spec.tooling_id, 0) + 1

    multiple_primaries = {tid: count for tid, count in tooling_primaries.items() if count > 1}
    if multiple_primaries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Each tooling may have at most one primary TWP spec. "
                   f"Toolings with multiple primaries: {list(multiple_primaries.keys())}"
        )


async def _validate_effective_state(
    db: DbSession,
    part_id: int,
    request: PartEditorBulkUpdateRequest
) -> None:
    """Validate the final effective state after applying the bulk update.

    Prevents:
    - Multiple primary ToolingPart records for one part
    - Multiple primary TWP specs for one (part_id, tooling_id)
    - Tooling_id mutation on existing ToolingPart records
    - Tooling_id mutation on existing PartToolingSpec records
    """
    # Build effective ToolingPart state
    if request.tooling_parts is not None:
        # Fetch current state
        current_tp_result = await db.execute(
            select(ToolingPart).where(ToolingPart.part_id == part_id)
        )
        current_tps = {tp.id: tp for tp in current_tp_result.scalars().all()}

        # Remove deleted
        for del_id in request.delete_tooling_part_ids:
            current_tps.pop(del_id, None)

        # Build effective state: start with retained rows
        effective_tps = []
        request_ids_seen = set()

        for tp_item in request.tooling_parts:
            if tp_item.id is not None:
                request_ids_seen.add(tp_item.id)
                if tp_item.id in current_tps:
                    # Validate immutable tooling_id
                    existing = current_tps[tp_item.id]
                    if existing.tooling_id != tp_item.tooling_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Cannot change tooling_id on existing ToolingPart ID {tp_item.id}. "
                                   f"Delete and create new association instead."
                        )
                    effective_tps.append(tp_item)
                else:
                    # Unknown ID
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"ToolingPart ID {tp_item.id} not found for part {part_id}"
                    )
            else:
                # New record
                effective_tps.append(tp_item)

        # Add retained rows not in request
        for existing_tp in current_tps.values():
            if existing_tp.id not in request_ids_seen:
                effective_tps.append(ToolingPartItem(
                    id=existing_tp.id,
                    tooling_id=existing_tp.tooling_id,
                    position=existing_tp.position,
                    sequence=existing_tp.sequence,
                    is_primary=existing_tp.is_primary,
                ))

        # Validate at most one primary
        primary_count = sum(1 for tp in effective_tps if tp.is_primary)
        if primary_count > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"At most one tooling may be marked as primary. Found {primary_count} primaries in final state."
            )

        # Validate continuous-only-primary constraint
        if effective_tps:
            tooling_ids = [tp.tooling_id for tp in effective_tps]
            tooling_result = await db.execute(
                select(Tooling).where(Tooling.id.in_(tooling_ids))
            )
            tooling_map = {t.id: t for t in tooling_result.scalars().all()}
            _validate_primary_constraints(effective_tps, tooling_map)

        # Check for duplicate tooling_ids in final state
        final_tooling_ids = [tp.tooling_id for tp in effective_tps]
        if len(final_tooling_ids) != len(set(final_tooling_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Final state would have duplicate tooling associations"
            )

    # Build effective TWP spec state
    if request.twp_specs is not None:
        # Fetch current state
        current_spec_result = await db.execute(
            select(PartToolingSpec).where(PartToolingSpec.part_id == part_id)
        )
        current_specs = {s.id: s for s in current_spec_result.scalars().all()}

        # Remove deleted
        for del_id in request.delete_spec_ids:
            current_specs.pop(del_id, None)

        # Build effective state: start with retained rows
        effective_specs = []
        request_ids_seen = set()

        for spec_item in request.twp_specs:
            if spec_item.id is not None:
                request_ids_seen.add(spec_item.id)
                if spec_item.id in current_specs:
                    # Validate immutable tooling_id
                    existing = current_specs[spec_item.id]
                    if existing.tooling_id != spec_item.tooling_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Cannot change tooling_id on existing PartToolingSpec ID {spec_item.id}. "
                                   f"Delete and create new spec instead."
                        )
                    effective_specs.append(spec_item)
                else:
                    # Unknown ID
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Spec ID {spec_item.id} not found for part {part_id}"
                    )
            else:
                # New record
                effective_specs.append(spec_item)

        # Add retained rows not in request
        for existing_spec in current_specs.values():
            if existing_spec.id not in request_ids_seen:
                effective_specs.append(TWPSpecItem(
                    id=existing_spec.id,
                    tooling_id=existing_spec.tooling_id,
                    spec_twph=existing_spec.spec_twph,
                    thickness=existing_spec.thickness,
                    width=existing_spec.width,
                    pitch=existing_spec.pitch,
                    is_primary=existing_spec.is_primary,
                ))

        # Validate at most one primary per (part_id, tooling_id)
        _validate_twp_primary_scope(effective_specs)

        # A tooling may legitimately have multiple TWP tuples. Reject only an
        # exact duplicate tuple within the same tooling, not a different revision.
        spec_keys = [
            (
                spec_item.tooling_id,
                spec_item.spec_twph,
                spec_item.thickness,
                spec_item.width,
                spec_item.pitch,
            )
            for spec_item in effective_specs
        ]
        if len(spec_keys) != len(set(spec_keys)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Final state would have duplicate TWP tuples for the same tooling"
            )


async def _build_editor_detail_response(
    db: DbSession,
    part: Part,
    include_tooling_catalog: bool = False,
) -> PartEditorDetailResponse:
    """Build complete editor detail response."""
    # Fetch customer aliases
    alias_result = await db.execute(
        select(PartCustomerAlias)
        .where(PartCustomerAlias.part_id == part.id)
        .order_by(PartCustomerAlias.customer_id, PartCustomerAlias.revision)
    )
    aliases = alias_result.scalars().all()

    # Fetch tooling associations with continuous sorting
    tooling_result = await db.execute(
        select(ToolingPart, Tooling)
        .join(Tooling, ToolingPart.tooling_id == Tooling.id)
        .where(ToolingPart.part_id == part.id)
        .order_by(
            Tooling.is_continuous.desc(),  # Continuous first
            ToolingPart.sequence,
            ToolingPart.id
        )
    )
    tooling_rows = tooling_result.all()

    # Fetch TWP specs
    spec_result = await db.execute(
        select(PartToolingSpec)
        .where(PartToolingSpec.part_id == part.id)
        .order_by(
            PartToolingSpec.tooling_id,
            PartToolingSpec.is_primary.desc(),
            PartToolingSpec.id
        )
    )
    specs = spec_result.scalars().all()

    all_toolings = []
    if include_tooling_catalog:
        all_toolings_result = await db.execute(
            select(Tooling)
            .where(Tooling.is_deleted == False)
            .order_by(Tooling.is_continuous.desc(), Tooling.tooling_number)
        )
        all_toolings = all_toolings_result.scalars().all()

    inventory_qty = (
        await db.execute(
            select(Inventory.stock_qty)
            .where(Inventory.part_id == part.id)
        )
    ).scalars().all()
    stock_pcs = sum(int(qty or 0) for qty in inventory_qty) if inventory_qty else int(part.stock_pcs or 0)

    return PartEditorDetailResponse(
        id=part.id,
        part_name=part.internal_name,
        customer_id=aliases[0].customer_id if aliases else None,
        customer_part_no=aliases[0].customer_part_no if aliases else None,
        customer_part_name=aliases[0].customer_part_name if aliases else None,
        vehicle_model=part.vehicle_model,
        material_id=part.material_id,
        material_name=part.material_name,
        drawing_url=part.drawing_url,
        spec_info=part.spec_info,
        spec_twph=part.spec_twph,
        thickness=part.thickness,
        width=part.width,
        pitch=part.pitch,
        height=part.height,
        gross_weight=part.gross_weight,
        net_weight=part.net_weight,
        part_position=part.part_position,
        part_status=part.part_status,
        # ``status`` is a deprecated compatibility field.  The canonical
        # lifecycle value is ``part_status``; emit an explicit null so older
        # response-model deployments cannot fail on a missing key.
        status=None,
        remark=part.remark,
        press_tonnage=part.press_tonnage,
        ppap_no=part.ppap_no,
        stock_pcs=stock_pcs,
        is_deleted=part.is_deleted,
        created_at=part.created_at,
        updated_at=part.updated_at,
        version=part.version or "V1.0",
        customer_aliases=[
            CustomerAliasResponse(
                id=a.id,
                part_id=a.part_id,
                customer_id=a.customer_id,
                customer_part_no=a.customer_part_no or "",
                customer_part_name=a.customer_part_name,
                revision=a.revision,
                vehicle_model=a.vehicle_model,
                remark=a.remark,
                is_active=a.is_active,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in aliases
        ],
        tooling_associations=[
            ToolingPartResponse(
                id=tp.id,
                tooling_id=tp.tooling_id,
                part_id=tp.part_id,
                position=tp.position,
                sequence=tp.sequence,
                is_primary=tp.is_primary,
                created_at=tp.created_at,
                tooling_number=tooling.tooling_number,
                tooling_name=tooling.tooling_name,
                mold_type=tooling.mold_type,
                is_continuous=tooling.is_continuous,
            )
            for tp, tooling in tooling_rows
        ],
        twp_specs=[
            TWPSpecResponse(
                id=s.id,
                part_id=s.part_id,
                tooling_id=s.tooling_id,
                spec_twph=s.spec_twph,
                thickness=s.thickness,
                width=s.width,
                pitch=s.pitch,
                is_primary=s.is_primary,
                source_sheet=s.source_sheet,
                source_row=s.source_row,
                source_note=s.source_note,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in specs
        ],
        available_toolings=[
            ToolingBriefInfo(
                id=t.id,
                tooling_number=t.tooling_number,
                tooling_name=t.tooling_name,
                mold_type=t.mold_type,
                is_continuous=t.is_continuous,
            )
            for t in all_toolings
        ],
    )


# ==================== GET Detail Endpoint ====================

@router.get("/{part_id}/editor/detail", response_model=PartEditorDetailResponse)
async def get_part_editor_detail(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
    include_tooling_catalog: bool = Query(False),
) -> PartEditorDetailResponse:
    """Get complete part detail for editor with all relationships.

    Returns:
    - Part basic info
    - All customer aliases
    - All tooling associations (sorted: continuous first, then by sequence)
    - All TWP specs (grouped by tooling, primary first)
    - Available toolings for selection

    Authorization: Requires role level >= 2 (LV2+)
    """
    if current_user.role_level < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Minimum role level required: LV2, you have LV{current_user.role_level}"
        )

    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id} not found"
        )

    if part.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id} has been deleted"
        )

    return await _build_editor_detail_response(db, part, include_tooling_catalog)


# ==================== Bulk Update ====================

@router.put("/{part_id}/editor/bulk")
async def bulk_update_relationships(
    part_id: int,
    request: PartEditorBulkUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PartEditorBulkUpdateResponse:
    """Atomically update all relationship categories with optimistic locking.

    Features:
    - Upsert by ID (preserves existing records when ID matches)
    - Explicit delete lists (delete_alias_ids, delete_tooling_part_ids, delete_spec_ids)
    - Source field preservation for TWP specs (source_sheet/source_row/source_note)
    - Optimistic locking via expected_updated_at (returns 409 on mismatch)
    - Validation: deleted tooling, primary constraints, deletion ordering

    Processing order:
    1. Validate optimistic lock (expected_updated_at matches part.updated_at)
    2. Validate all inputs before mutations
    3. Delete customer aliases (explicit IDs)
    4. Upsert customer aliases (by ID if present)
    5. Check orphaned TWP specs before deleting tooling associations
    6. Delete tooling associations (explicit IDs)
    7. Upsert tooling associations (by ID if present)
    8. Flush to make new associations visible
    9. Delete TWP specs (explicit IDs)
    10. Upsert TWP specs (by ID if present, preserving source fields)
    11. Update part.updated_at and commit

    Authorization: Requires role level >= 2 (LV2+)
    """
    if current_user.role_level < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Minimum role level required: LV2, you have LV{current_user.role_level}"
        )

    # Validate part exists
    part = await db.get(Part, part_id)
    if not part or part.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id} not found"
        )

    # Optimistic lock check
    server_ts = part.updated_at or part.created_at
    client_ts = request.expected_updated_at

    # Truncate to seconds for comparison (avoid microsecond precision issues)
    server_ts_sec = server_ts.replace(microsecond=0) if server_ts else None
    client_ts_sec = client_ts.replace(microsecond=0)

    if server_ts_sec != client_ts_sec:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "optimistic_lock_conflict",
                "message": "Part was modified by another user",
                "client_timestamp": client_ts.isoformat(),
                "server_timestamp": server_ts.isoformat() if server_ts else None,
            }
        )

    existing_tooling_count = len((await db.execute(
        select(ToolingPart.id).where(ToolingPart.part_id == part_id)
    )).scalars().all())
    existing_spec_count = len((await db.execute(
        select(PartToolingSpec.id).where(PartToolingSpec.part_id == part_id)
    )).scalars().all())

    try:
        counts = {"aliases": 0, "tooling_parts": 0, "specs": 0}

        # ========== Phase 1: Validate All Inputs ==========

        # Validate deletion IDs belong to this part
        if request.delete_alias_ids:
            alias_result = await db.execute(
                select(PartCustomerAlias.id).where(
                    and_(
                        PartCustomerAlias.part_id == part_id,
                        PartCustomerAlias.id.in_(request.delete_alias_ids)
                    )
                )
            )
            valid_alias_ids = {row[0] for row in alias_result.fetchall()}
            invalid_alias_ids = set(request.delete_alias_ids) - valid_alias_ids
            if invalid_alias_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Alias IDs not found or don't belong to part {part_id}: {sorted(invalid_alias_ids)}"
                )

        if request.delete_tooling_part_ids:
            tp_result = await db.execute(
                select(ToolingPart.id).where(
                    and_(
                        ToolingPart.part_id == part_id,
                        ToolingPart.id.in_(request.delete_tooling_part_ids)
                    )
                )
            )
            valid_tp_ids = {row[0] for row in tp_result.fetchall()}
            invalid_tp_ids = set(request.delete_tooling_part_ids) - valid_tp_ids
            if invalid_tp_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"ToolingPart IDs not found or don't belong to part {part_id}: {sorted(invalid_tp_ids)}"
                )

        if request.delete_spec_ids:
            spec_result = await db.execute(
                select(PartToolingSpec.id).where(
                    and_(
                        PartToolingSpec.part_id == part_id,
                        PartToolingSpec.id.in_(request.delete_spec_ids)
                    )
                )
            )
            valid_spec_ids = {row[0] for row in spec_result.fetchall()}
            invalid_spec_ids = set(request.delete_spec_ids) - valid_spec_ids
            if invalid_spec_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Spec IDs not found or don't belong to part {part_id}: {sorted(invalid_spec_ids)}"
                )

        # Check for collisions between upsert IDs and delete IDs
        if request.customer_aliases is not None:
            upsert_alias_ids = {a.id for a in request.customer_aliases if a.id is not None}
            delete_alias_ids_set = set(request.delete_alias_ids)
            collision = upsert_alias_ids & delete_alias_ids_set
            if collision:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Alias IDs cannot be in both upsert and delete lists: {sorted(collision)}"
                )

        if request.tooling_parts is not None:
            upsert_tp_ids = {tp.id for tp in request.tooling_parts if tp.id is not None}
            delete_tp_ids_set = set(request.delete_tooling_part_ids)
            collision = upsert_tp_ids & delete_tp_ids_set
            if collision:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"ToolingPart IDs cannot be in both upsert and delete lists: {sorted(collision)}"
                )

        if request.twp_specs is not None:
            upsert_spec_ids = {s.id for s in request.twp_specs if s.id is not None}
            delete_spec_ids_set = set(request.delete_spec_ids)
            collision = upsert_spec_ids & delete_spec_ids_set
            if collision:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Spec IDs cannot be in both upsert and delete lists: {sorted(collision)}"
                )

        # Check for duplicate identities in upsert requests
        if request.customer_aliases is not None:
            alias_keys = [(a.customer_id, a.customer_part_no, a.revision) for a in request.customer_aliases]
            if len(alias_keys) != len(set(alias_keys)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate customer alias identities (customer_id, customer_part_no, revision) in request"
                )

        if request.tooling_parts is not None:
            # Check for duplicate association IDs
            tp_ids = [tp.id for tp in request.tooling_parts if tp.id is not None]
            if len(tp_ids) != len(set(tp_ids)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate ToolingPart IDs in request"
                )

            # Check for duplicate tooling_ids in request
            tp_tooling_ids = [tp.tooling_id for tp in request.tooling_parts]
            if len(tp_tooling_ids) != len(set(tp_tooling_ids)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate tooling_id in request"
                )

        if request.twp_specs is not None:
            # Check for duplicate spec IDs
            spec_ids = [s.id for s in request.twp_specs if s.id is not None]
            if len(spec_ids) != len(set(spec_ids)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate TWP spec IDs in request"
                )

        # Validate customer IDs
        if request.customer_aliases is not None:
            customer_ids = [a.customer_id for a in request.customer_aliases]
            await _validate_customer_ids(db, customer_ids)

        # Validate tooling IDs and check deleted
        if request.tooling_parts is not None:
            tooling_ids = [tp.tooling_id for tp in request.tooling_parts]
            tooling_map = await _validate_tooling_ids(db, tooling_ids)

        # Validate TWP specs
        if request.twp_specs is not None:
            spec_tooling_ids = list({s.tooling_id for s in request.twp_specs})
            await _validate_tooling_ids(db, spec_tooling_ids)

        # Validate effective final state for primary constraints
        await _validate_effective_state(db, part_id, request)

        # ========== Phase 2: Customer Aliases ==========

        if request.customer_aliases is not None or request.delete_alias_ids:
            # Delete explicit IDs
            if request.delete_alias_ids:
                await db.execute(
                    delete(PartCustomerAlias).where(
                        and_(
                            PartCustomerAlias.part_id == part_id,
                            PartCustomerAlias.id.in_(request.delete_alias_ids)
                        )
                    )
                )

            # Upsert aliases
            if request.customer_aliases is not None:
                for alias_item in request.customer_aliases:
                    if alias_item.id is not None:
                        # Update existing by ID
                        existing = await db.get(PartCustomerAlias, alias_item.id)
                        if existing and existing.part_id == part_id:
                            existing.customer_id = alias_item.customer_id
                            existing.customer_part_no = alias_item.customer_part_no
                            existing.customer_part_name = alias_item.customer_part_name
                            existing.revision = alias_item.revision
                            existing.vehicle_model = alias_item.vehicle_model
                            existing.remark = alias_item.remark
                            existing.is_active = alias_item.is_active
                            existing.updated_at = datetime.utcnow()
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Alias ID {alias_item.id} not found for part {part_id}"
                            )
                    else:
                        # Create new
                        new_alias = PartCustomerAlias(
                            part_id=part_id,
                            customer_id=alias_item.customer_id,
                            customer_part_no=alias_item.customer_part_no,
                            customer_part_name=alias_item.customer_part_name,
                            revision=alias_item.revision,
                            vehicle_model=alias_item.vehicle_model,
                            remark=alias_item.remark,
                            is_active=alias_item.is_active,
                        )
                        db.add(new_alias)

                counts["aliases"] = len(request.customer_aliases)

        # ========== Phase 3: Check Orphaned Specs Before Deleting Tooling ==========

        if request.delete_tooling_part_ids:
            # Get tooling IDs being deleted
            tp_result = await db.execute(
                select(ToolingPart.tooling_id).where(
                    and_(
                        ToolingPart.part_id == part_id,
                        ToolingPart.id.in_(request.delete_tooling_part_ids)
                    )
                )
            )
            deleting_tooling_ids = {row[0] for row in tp_result.fetchall()}

            # Check for specs that would be orphaned
            spec_result = await db.execute(
                select(PartToolingSpec.id).where(
                    and_(
                        PartToolingSpec.part_id == part_id,
                        PartToolingSpec.tooling_id.in_(deleting_tooling_ids),
                        PartToolingSpec.id.not_in(request.delete_spec_ids or [])
                    )
                )
            )
            orphaned_spec_ids = [row[0] for row in spec_result.fetchall()]

            if orphaned_spec_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot remove tooling associations while specs exist. "
                           f"Delete specs {orphaned_spec_ids} first or include them in delete_spec_ids."
                )

        # ========== Phase 4: Tooling Associations ==========

        if request.tooling_parts is not None or request.delete_tooling_part_ids:
            # Delete explicit IDs
            if request.delete_tooling_part_ids:
                await db.execute(
                    delete(ToolingPart).where(
                        and_(
                            ToolingPart.part_id == part_id,
                            ToolingPart.id.in_(request.delete_tooling_part_ids)
                        )
                    )
                )

            # Upsert tooling associations
            if request.tooling_parts is not None:
                for tp_item in request.tooling_parts:
                    if tp_item.id is not None:
                        # Update existing by ID
                        existing = await db.get(ToolingPart, tp_item.id)
                        if existing and existing.part_id == part_id:
                            # Immutability check already done in validation, but double-check
                            if existing.tooling_id != tp_item.tooling_id:
                                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Cannot change tooling_id on existing ToolingPart ID {tp_item.id}"
                                )
                            # Update mutable fields only
                            existing.position = tp_item.position
                            existing.sequence = tp_item.sequence
                            existing.is_primary = tp_item.is_primary
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"ToolingPart ID {tp_item.id} not found for part {part_id}"
                            )
                    else:
                        # Create new
                        new_tp = ToolingPart(
                            tooling_id=tp_item.tooling_id,
                            part_id=part_id,
                            position=tp_item.position,
                            sequence=tp_item.sequence,
                            is_primary=tp_item.is_primary,
                        )
                        db.add(new_tp)

                counts["tooling_parts"] = len(request.tooling_parts)

            # Flush to make new associations visible for TWP validation
            await db.flush()

        # ========== Phase 5: TWP Specs ==========

        if request.twp_specs is not None or request.delete_spec_ids:
            # Get current associations for validation
            result = await db.execute(
                select(ToolingPart.tooling_id).where(ToolingPart.part_id == part_id)
            )
            associated_tooling_ids = {row[0] for row in result.fetchall()}

            # Validate TWP specs reference associated toolings
            if request.twp_specs is not None:
                spec_tooling_ids = {s.tooling_id for s in request.twp_specs}
                unassociated = spec_tooling_ids - associated_tooling_ids
                if unassociated:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"TWP specs reference unassociated toolings: {sorted(unassociated)}. "
                               f"Add tooling associations first."
                    )

            # Delete explicit IDs
            if request.delete_spec_ids:
                await db.execute(
                    delete(PartToolingSpec).where(
                        and_(
                            PartToolingSpec.part_id == part_id,
                            PartToolingSpec.id.in_(request.delete_spec_ids)
                        )
                    )
                )

            # Upsert specs (preserving source fields)
            if request.twp_specs is not None:
                for spec_item in request.twp_specs:
                    if spec_item.id is not None:
                        # Update existing by ID, preserving source fields
                        existing = await db.get(PartToolingSpec, spec_item.id)
                        if existing and existing.part_id == part_id:
                            # Immutability check already done in validation, but double-check
                            if existing.tooling_id != spec_item.tooling_id:
                                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Cannot change tooling_id on existing PartToolingSpec ID {spec_item.id}"
                                )
                            # Update mutable fields only
                            existing.spec_twph = spec_item.spec_twph
                            existing.thickness = spec_item.thickness
                            existing.width = spec_item.width
                            existing.pitch = spec_item.pitch
                            existing.is_primary = spec_item.is_primary
                            # source_sheet/source_row/source_note preserved (not touched)
                            existing.updated_at = datetime.utcnow()
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Spec ID {spec_item.id} not found for part {part_id}"
                            )
                    else:
                        # Create new (source fields null for editor-created specs)
                        new_spec = PartToolingSpec(
                            part_id=part_id,
                            tooling_id=spec_item.tooling_id,
                            spec_twph=spec_item.spec_twph,
                            thickness=spec_item.thickness,
                            width=spec_item.width,
                            pitch=spec_item.pitch,
                            is_primary=spec_item.is_primary,
                            # source_sheet, source_row, source_note remain NULL
                        )
                        db.add(new_spec)

                counts["specs"] = len(request.twp_specs)

        # Update part timestamp
        part.updated_at = datetime.utcnow()
        await audit_event(
            db=db,
            action=AuditAction.UPDATE,
            entity_type="part",
            entity_id=part.id,
            user_id=current_user.id,
            username=getattr(current_user, "username", None),
            old_values={"模具关联": existing_tooling_count, "TWP 规格": existing_spec_count},
            new_values={"模具关联": counts["tooling_parts"], "TWP 规格": counts["specs"]},
            extra_data={"scope": "模具关联与 TWP", "summary": "模具关联与 TWP 规格已保存"},
        )

        await db.commit()
        await db.refresh(part)

        return PartEditorBulkUpdateResponse(
            success=True,
            part_id=part_id,
            updated_at=part.updated_at or datetime.utcnow(),
            customer_aliases_count=counts["aliases"],
            tooling_parts_count=counts["tooling_parts"],
            twp_specs_count=counts["specs"],
            message="Bulk update completed successfully"
        )

    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError as e:
        await db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integrity constraint violation: {error_msg}"
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during bulk update: {str(e)}"
        )
