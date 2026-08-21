"""API endpoints for explicit part display grouping.

Stage 2: LV2+ users create/update/delete explicit groups and manage membership.
No automatic inference from names, suffixes, or Excel text.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.part_display_group import (
    PartDisplayGroupDef,
    PartDisplayGroupMember,
    SharedFieldGroupDef,
    SharedFieldGroupMember,
)
from app.models.part import Part
from app.models.tooling import Tooling
from app.models.part_customer_alias import PartCustomerAlias
from app.models.user import User
from app.schemas.part_display_group import (
    PartDisplayGroupDefCreate,
    PartDisplayGroupDefUpdate,
    PartDisplayGroupDefResponse,
    PartDisplayGroupMemberCreate,
    SharedFieldGroupDefCreate,
    SharedFieldGroupDefUpdate,
    SharedFieldGroupDefResponse,
    SharedFieldGroupMemberCreate,
)

router = APIRouter(prefix="/part-display-groups", tags=["Part Display Groups"])


def _tooling_business_number(tooling: Tooling | None) -> Optional[str]:
    if not tooling:
        return None
    return tooling.tooling_number


async def _resolve_part_id(db: DbSession, part_id: Optional[int], customer_part_no: Optional[str]) -> int:
    if part_id:
        part = await db.get(Part, part_id)
        if not part:
            raise HTTPException(status_code=400, detail=f"Part not found")
        return part.id

    number = (customer_part_no or "").strip()
    if not number:
        raise HTTPException(status_code=400, detail="Customer part number is required")

    parts = (await db.execute(
        select(PartCustomerAlias.part_id).where(
            PartCustomerAlias.customer_part_no == number,
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.data_quality_status == "approved",
        )
    )).scalars().all()
    if not parts:
        raise HTTPException(status_code=400, detail=f"Customer part number '{number}' not found")
    if len(parts) > 1:
        raise HTTPException(status_code=400, detail=f"Customer part number '{number}' matches multiple parts")
    return parts[0]


async def _resolve_tooling_id(db: DbSession, tooling_id: Optional[int], tooling_number: Optional[str]) -> int:
    if tooling_id:
        tooling = await db.get(Tooling, tooling_id)
        if not tooling:
            raise HTTPException(status_code=400, detail="Tooling not found")
        return tooling.id

    number = (tooling_number or "").strip()
    if not number:
        raise HTTPException(status_code=400, detail="Tooling number is required")

    toolings = (await db.execute(
        select(Tooling).where(
            Tooling.is_deleted == False,
            Tooling.tooling_number == number,
        )
    )).scalars().all()
    if not toolings:
        raise HTTPException(status_code=400, detail=f"Tooling number '{number}' not found")
    if len(toolings) > 1:
        raise HTTPException(status_code=400, detail=f"Tooling number '{number}' matches multiple toolings")
    return toolings[0].id


async def _display_group_response(db: DbSession, group: PartDisplayGroupDef) -> PartDisplayGroupDefResponse:
    part_ids = [member.part_id for member in group.members]
    parts = {}
    customer_part_numbers = {}
    if part_ids:
        rows = (await db.execute(select(Part).where(Part.id.in_(part_ids)))).scalars().all()
        parts = {part.id: part for part in rows}
        alias_rows = (await db.execute(
            select(PartCustomerAlias)
            .where(
                PartCustomerAlias.part_id.in_(part_ids),
                PartCustomerAlias.is_active == True,
                PartCustomerAlias.data_quality_status == "approved",
            )
            .order_by(PartCustomerAlias.part_id, PartCustomerAlias.id)
        )).scalars().all()
        for alias in alias_rows:
            customer_part_numbers.setdefault(alias.part_id, alias.customer_part_no)
    return PartDisplayGroupDefResponse(
        id=group.id,
        group_type=group.group_type,
        group_key=group.group_key,
        display_name=group.display_name,
        source_sheet=group.source_sheet,
        source_rows=group.source_rows,
        is_active=group.is_active,
        remark=group.remark,
        created_by=group.created_by,
        created_at=group.created_at,
        updated_by=group.updated_by,
        updated_at=group.updated_at,
        members=[
            {
                "id": member.id,
                "group_id": member.group_id,
                "part_id": member.part_id,
                "customer_part_no": customer_part_numbers.get(member.part_id),
                "part_name": parts.get(member.part_id).internal_name if member.part_id in parts else None,
                "position": member.position,
                "sequence": member.sequence,
                "source_row": member.source_row,
                "created_at": member.created_at,
            }
            for member in group.members
        ],
    )


async def _shared_field_response(db: DbSession, group: SharedFieldGroupDef) -> SharedFieldGroupDefResponse:
    part_ids = [member.part_id for member in group.members if member.part_id]
    tooling_ids = [member.tooling_id for member in group.members if member.tooling_id]
    parts = {}
    toolings = {}
    if part_ids:
        rows = (await db.execute(select(Part).where(Part.id.in_(part_ids)))).scalars().all()
        parts = {part.id: part for part in rows}
    if tooling_ids:
        rows = (await db.execute(select(Tooling).where(Tooling.id.in_(tooling_ids)))).scalars().all()
        toolings = {tooling.id: tooling for tooling in rows}
    return SharedFieldGroupDefResponse(
        id=group.id,
        group_key=group.group_key,
        display_name=group.display_name,
        shares_material=group.shares_material,
        shares_thickness=group.shares_thickness,
        shares_width=group.shares_width,
        shares_pitch=group.shares_pitch,
        shares_cavity=group.shares_cavity,
        source_sheet=group.source_sheet,
        source_rows=group.source_rows,
        is_active=group.is_active,
        remark=group.remark,
        created_by=group.created_by,
        created_at=group.created_at,
        updated_by=group.updated_by,
        updated_at=group.updated_at,
        members=[
            {
                "id": member.id,
                "group_id": member.group_id,
                "part_id": member.part_id,
                "customer_part_no": None,
                "part_name": parts.get(member.part_id).internal_name if member.part_id in parts else None,
                "tooling_id": member.tooling_id,
                "tooling_number": _tooling_business_number(toolings.get(member.tooling_id)) if member.tooling_id in toolings else None,
                "tooling_name": toolings.get(member.tooling_id).tooling_name if member.tooling_id in toolings else None,
                "source_row": member.source_row,
                "created_at": member.created_at,
            }
            for member in group.members
        ],
    )


# ========== Part Display Groups ==========

@router.get("", response_model=list[PartDisplayGroupDefResponse])
async def list_part_display_groups(
    db: DbSession,
    current_user: CurrentUser,
    group_type: Optional[str] = Query(default=None, pattern="^(left_right|shared_source)$"),
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PartDisplayGroupDefResponse]:
    """List all part display groups with optional filtering."""
    q = select(PartDisplayGroupDef).options(selectinload(PartDisplayGroupDef.members))

    if group_type:
        q = q.where(PartDisplayGroupDef.group_type == group_type)
    if is_active is not None:
        q = q.where(PartDisplayGroupDef.is_active == is_active)

    q = q.order_by(PartDisplayGroupDef.created_at.desc()).offset(skip).limit(limit)

    groups = (await db.execute(q)).scalars().all()
    return [await _display_group_response(db, group) for group in groups]


@router.post("", response_model=PartDisplayGroupDefResponse, status_code=status.HTTP_201_CREATED)
async def create_part_display_group(
    data: PartDisplayGroupDefCreate,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> PartDisplayGroupDefResponse:
    """Create a new part display group (LV2+ only).

    Validates:
    - group_key is unique
    - all part_ids exist
    - left_right groups have exactly 2 members with positions 'left' and 'right'
    - shared_source groups have at least 2 members
    - no part appears in multiple active groups
    """
    # Check group_key uniqueness
    existing = (await db.execute(
        select(PartDisplayGroupDef).where(PartDisplayGroupDef.group_key == data.group_key)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Group key '{data.group_key}' already exists")

    resolved_members = []
    for member in data.members:
        resolved_members.append(
            PartDisplayGroupMemberCreate(
                part_id=await _resolve_part_id(db, member.part_id, member.customer_part_no),
                position=member.position,
                sequence=member.sequence,
            )
        )
    part_ids = [m.part_id for m in resolved_members if m.part_id]

    # Validate left_right group constraints
    if data.group_type == "left_right":
        if len(resolved_members) != 2:
            raise HTTPException(
                status_code=400,
                detail=f"left_right groups must have exactly 2 members, got {len(resolved_members)}"
            )
        positions = {m.position for m in resolved_members if m.position}
        if positions != {"left", "right"}:
            raise HTTPException(
                status_code=400,
                detail=f"left_right groups must have positions 'left' and 'right', got {positions}"
            )

    # Validate shared_source group constraints
    if data.group_type == "shared_source":
        if len(resolved_members) < 2:
            raise HTTPException(
                status_code=400,
                detail=f"shared_source groups must have at least 2 members, got {len(resolved_members)}"
            )

    # Check no part is in another active group
    if part_ids:
        existing_members = (await db.execute(
            select(PartDisplayGroupMember)
            .join(PartDisplayGroupDef)
            .where(
                PartDisplayGroupMember.part_id.in_(part_ids),
                PartDisplayGroupDef.is_active == True
            )
        )).scalars().all()
        if existing_members:
            conflicting_parts = {m.part_id for m in existing_members}
            raise HTTPException(
                status_code=400,
                detail=f"Parts already in active groups: {sorted(conflicting_parts)}"
            )

    # Create group
    group = PartDisplayGroupDef(
        group_type=data.group_type,
        group_key=data.group_key,
        display_name=data.display_name,
        remark=data.remark,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(group)
    await db.flush()

    # Add members
    for member_data in resolved_members:
        member = PartDisplayGroupMember(
            group_id=group.id,
            part_id=member_data.part_id,
            position=member_data.position,
            sequence=member_data.sequence,
        )
        db.add(member)

    await db.commit()
    await db.refresh(group, ["members"])
    return await _display_group_response(db, group)


# ========== Shared Field Groups ==========
# NOTE: Static /shared-fields routes MUST be registered before /{group_id} dynamic routes
# to avoid FastAPI capturing "shared-fields" as an integer group_id

@router.get("/shared-fields", response_model=list[SharedFieldGroupDefResponse])
async def list_shared_field_groups(
    db: DbSession,
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SharedFieldGroupDefResponse]:
    """List all shared field groups with optional filtering."""
    q = select(SharedFieldGroupDef).options(selectinload(SharedFieldGroupDef.members))

    if is_active is not None:
        q = q.where(SharedFieldGroupDef.is_active == is_active)

    q = q.order_by(SharedFieldGroupDef.created_at.desc()).offset(skip).limit(limit)

    groups = (await db.execute(q)).scalars().all()
    return [await _shared_field_response(db, group) for group in groups]


@router.post("/shared-fields", response_model=SharedFieldGroupDefResponse, status_code=status.HTTP_201_CREATED)
async def create_shared_field_group(
    data: SharedFieldGroupDefCreate,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> SharedFieldGroupDefResponse:
    """Create a new shared field group (LV2+ only).

    Validates:
    - group_key is unique
    - all part_ids and tooling_ids exist
    - at least 2 members
    - at least one shared field flag is true
    """
    # Check group_key uniqueness
    existing = (await db.execute(
        select(SharedFieldGroupDef).where(SharedFieldGroupDef.group_key == data.group_key)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Group key '{data.group_key}' already exists")

    # Validate at least one shared field
    if not any([
        data.shares_material,
        data.shares_thickness,
        data.shares_width,
        data.shares_pitch,
        data.shares_cavity,
    ]):
        raise HTTPException(status_code=400, detail="At least one shared field must be true")

    resolved_members = []
    for member in data.members:
        if member.part_id or member.customer_part_no:
            resolved_members.append(
                SharedFieldGroupMemberCreate(
                    part_id=await _resolve_part_id(db, member.part_id, member.customer_part_no)
                )
            )
        elif member.tooling_id or member.tooling_number:
            resolved_members.append(
                SharedFieldGroupMemberCreate(
                    tooling_id=await _resolve_tooling_id(db, member.tooling_id, member.tooling_number)
                )
            )
        else:
            raise HTTPException(status_code=400, detail="Member must have part number or tooling number")

    # Validate at least 2 members
    if len(resolved_members) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Shared field groups must have at least 2 members, got {len(resolved_members)}"
        )

    # Create group
    group = SharedFieldGroupDef(
        group_key=data.group_key,
        display_name=data.display_name,
        shares_material=data.shares_material,
        shares_thickness=data.shares_thickness,
        shares_width=data.shares_width,
        shares_pitch=data.shares_pitch,
        shares_cavity=data.shares_cavity,
        remark=data.remark,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(group)
    await db.flush()

    # Add members
    for member_data in resolved_members:
        if not member_data.part_id and not member_data.tooling_id:
            raise HTTPException(status_code=400, detail="Member must have part_id or tooling_id")

        member = SharedFieldGroupMember(
            group_id=group.id,
            part_id=member_data.part_id,
            tooling_id=member_data.tooling_id,
        )
        db.add(member)

    await db.commit()
    await db.refresh(group, ["members"])
    return await _shared_field_response(db, group)


@router.get("/shared-fields/{group_id}", response_model=SharedFieldGroupDefResponse)
async def get_shared_field_group(
    group_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SharedFieldGroupDefResponse:
    """Get a shared field group by ID."""
    group = (await db.execute(
        select(SharedFieldGroupDef)
        .where(SharedFieldGroupDef.id == group_id)
        .options(selectinload(SharedFieldGroupDef.members))
    )).scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return await _shared_field_response(db, group)


@router.patch("/shared-fields/{group_id}", response_model=SharedFieldGroupDefResponse)
async def update_shared_field_group(
    group_id: int,
    data: SharedFieldGroupDefUpdate,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> SharedFieldGroupDefResponse:
    """Update a shared field group (LV2+ only)."""
    group = await db.get(SharedFieldGroupDef, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(group, field, value)

    group.updated_by = current_user.id
    await db.commit()
    await db.refresh(group, ["members"])
    return await _shared_field_response(db, group)


@router.delete("/shared-fields/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shared_field_group(
    group_id: int,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> None:
    """Delete a shared field group (LV2+ only). Cascade deletes members."""
    group = await db.get(SharedFieldGroupDef, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await db.delete(group)
    await db.commit()


@router.post("/shared-fields/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_shared_field_group_member(
    group_id: int,
    member_data: SharedFieldGroupMemberCreate,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> dict:
    """Add a member to a shared field group (LV2+ only)."""
    group = await db.get(SharedFieldGroupDef, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if member_data.part_id or member_data.customer_part_no:
        member_data.part_id = await _resolve_part_id(db, member_data.part_id, member_data.customer_part_no)
        member_data.tooling_id = None
    elif member_data.tooling_id or member_data.tooling_number:
        member_data.tooling_id = await _resolve_tooling_id(db, member_data.tooling_id, member_data.tooling_number)
        member_data.part_id = None
    else:
        raise HTTPException(status_code=400, detail="Member must have part number or tooling number")

    # Check not already in this group
    existing = (await db.execute(
        select(SharedFieldGroupMember).where(
            SharedFieldGroupMember.group_id == group_id,
            SharedFieldGroupMember.part_id == member_data.part_id,
            SharedFieldGroupMember.tooling_id == member_data.tooling_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Member already in this group")

    member = SharedFieldGroupMember(
        group_id=group_id,
        part_id=member_data.part_id,
        tooling_id=member_data.tooling_id,
    )
    db.add(member)
    await db.commit()
    return {"message": "Member added successfully", "member_id": member.id}


@router.delete("/shared-fields/{group_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_shared_field_group_member(
    group_id: int,
    member_id: int,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> None:
    """Remove a member from a shared field group (LV2+ only)."""
    member = (await db.execute(
        select(SharedFieldGroupMember).where(
            SharedFieldGroupMember.id == member_id,
            SharedFieldGroupMember.group_id == group_id,
        )
    )).scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found in this group")

    await db.delete(member)
    await db.commit()


# ========== Part Display Group Dynamic Routes ==========
# These /{group_id} routes come AFTER all static /shared-fields routes

@router.get("/{group_id}", response_model=PartDisplayGroupDefResponse)
async def get_part_display_group(
    group_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PartDisplayGroupDefResponse:
    """Get a part display group by ID."""
    group = (await db.execute(
        select(PartDisplayGroupDef)
        .where(PartDisplayGroupDef.id == group_id)
        .options(selectinload(PartDisplayGroupDef.members))
    )).scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return await _display_group_response(db, group)


@router.patch("/{group_id}", response_model=PartDisplayGroupDefResponse)
async def update_part_display_group(
    group_id: int,
    data: PartDisplayGroupDefUpdate,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> PartDisplayGroupDefResponse:
    """Update a part display group (LV2+ only)."""
    group = await db.get(PartDisplayGroupDef, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(group, field, value)

    group.updated_by = current_user.id
    await db.commit()
    await db.refresh(group, ["members"])
    return await _display_group_response(db, group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part_display_group(
    group_id: int,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> None:
    """Delete a part display group (LV2+ only). Cascade deletes members."""
    group = await db.get(PartDisplayGroupDef, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await db.delete(group)
    await db.commit()


@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_part_display_group_member(
    group_id: int,
    member_data: PartDisplayGroupMemberCreate,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> dict:
    """Add a member to a part display group (LV2+ only)."""
    group = await db.get(PartDisplayGroupDef, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    member_data.part_id = await _resolve_part_id(db, member_data.part_id, member_data.customer_part_no)

    # Check part not already in this group
    existing = (await db.execute(
        select(PartDisplayGroupMember).where(
            PartDisplayGroupMember.group_id == group_id,
            PartDisplayGroupMember.part_id == member_data.part_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Part already in this group")

    # Check part not in another active group
    other_membership = (await db.execute(
        select(PartDisplayGroupMember)
        .join(PartDisplayGroupDef)
        .where(
            PartDisplayGroupMember.part_id == member_data.part_id,
            PartDisplayGroupDef.is_active == True,
            PartDisplayGroupDef.id != group_id,
        )
    )).scalar_one_or_none()
    if other_membership:
        raise HTTPException(
            status_code=400,
            detail=f"Part already in active group {other_membership.group_id}"
        )

    member = PartDisplayGroupMember(
        group_id=group_id,
        part_id=member_data.part_id,
        position=member_data.position,
        sequence=member_data.sequence,
    )
    db.add(member)
    await db.commit()
    return {"message": "Member added successfully", "member_id": member.id}


@router.delete("/{group_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_part_display_group_member(
    group_id: int,
    member_id: int,
    db: DbSession,
    current_user: User = Depends(require_role(min_level=2)),
) -> None:
    """Remove a member from a part display group (LV2+ only)."""
    member = (await db.execute(
        select(PartDisplayGroupMember).where(
            PartDisplayGroupMember.id == member_id,
            PartDisplayGroupMember.group_id == group_id,
        )
    )).scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found in this group")

    await db.delete(member)
    await db.commit()
