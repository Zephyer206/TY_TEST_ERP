"""Business logic for coating (spray painting) management."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.coating import CoatingRecipe, CoatingRecord
from src.models.part import Part


def generate_recipe_no() -> str:
    """Generate a unique recipe number."""
    now = datetime.utcnow()
    return f"REC-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


def generate_record_no() -> str:
    """Generate a unique coating record number."""
    now = datetime.utcnow()
    return f"COT-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


async def create_recipe(
    db: AsyncSession,
    name: str,
    coating_type: str,
    color_type: str = "custom",
    color_code: Optional[str] = None,
    primer_type: Optional[str] = None,
    primer_thickness: Optional[float] = None,
    topcoat_type: Optional[str] = None,
    topcoat_thickness: Optional[float] = None,
    spray_pressure: Optional[float] = None,
    spray_distance: Optional[float] = None,
    spray_speed: Optional[float] = None,
    curing_temp: Optional[float] = None,
    curing_time: Optional[int] = None,
    material_consumption: Optional[float] = None,
    notes: Optional[str] = None,
) -> CoatingRecipe:
    """Create a new coating recipe."""
    recipe_no = generate_recipe_no()

    from src.models.coating import CoatingType, CoatingColor

    # Convert string to enum
    coating_type_enum = CoatingType(coating_type)
    color_type_enum = CoatingColor(color_type)

    recipe = CoatingRecipe(
        recipe_no=recipe_no,
        name=name,
        coating_type=coating_type_enum,
        color_type=color_type_enum,
        color_code=color_code,
        primer_type=primer_type,
        primer_thickness=primer_thickness,
        topcoat_type=topcoat_type,
        topcoat_thickness=topcoat_thickness,
        spray_pressure=spray_pressure,
        spray_distance=spray_distance,
        spray_speed=spray_speed,
        curing_temp=curing_temp,
        curing_time=curing_time,
        material_consumption=material_consumption,
        notes=notes,
    )
    db.add(recipe)
    await db.commit()
    await db.refresh(recipe)
    return recipe


async def get_recipe(
    db: AsyncSession,
    recipe_id: int,
) -> Optional[CoatingRecipe]:
    """Get a coating recipe by ID."""
    result = await db.execute(
        select(CoatingRecipe).where(CoatingRecipe.id == recipe_id)
    )
    return result.scalar_one_or_none()


async def get_recipes(
    db: AsyncSession,
    coating_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[CoatingRecipe]:
    """Get coating recipes with filters."""
    query = select(CoatingRecipe)

    if coating_type:
        from src.models.coating import CoatingType
        query = query.where(CoatingRecipe.coating_type == CoatingType(coating_type))
    if is_active is not None:
        query = query.where(CoatingRecipe.is_active == is_active)

    query = query.order_by(CoatingRecipe.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def update_recipe(
    db: AsyncSession,
    recipe: CoatingRecipe,
    name: Optional[str] = None,
    coating_type: Optional[str] = None,
    color_type: Optional[str] = None,
    color_code: Optional[str] = None,
    primer_type: Optional[str] = None,
    primer_thickness: Optional[float] = None,
    topcoat_type: Optional[str] = None,
    topcoat_thickness: Optional[float] = None,
    spray_pressure: Optional[float] = None,
    spray_distance: Optional[float] = None,
    spray_speed: Optional[float] = None,
    curing_temp: Optional[float] = None,
    curing_time: Optional[int] = None,
    material_consumption: Optional[float] = None,
    notes: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> CoatingRecipe:
    """Update a coating recipe."""
    from src.models.coating import CoatingType, CoatingColor

    if name is not None:
        recipe.name = name
    if coating_type is not None:
        recipe.coating_type = CoatingType(coating_type)
    if color_type is not None:
        recipe.color_type = CoatingColor(color_type)
    if color_code is not None:
        recipe.color_code = color_code
    if primer_type is not None:
        recipe.primer_type = primer_type
    if primer_thickness is not None:
        recipe.primer_thickness = primer_thickness
    if topcoat_type is not None:
        recipe.topcoat_type = topcoat_type
    if topcoat_thickness is not None:
        recipe.topcoat_thickness = topcoat_thickness
    if spray_pressure is not None:
        recipe.spray_pressure = spray_pressure
    if spray_distance is not None:
        recipe.spray_distance = spray_distance
    if spray_speed is not None:
        recipe.spray_speed = spray_speed
    if curing_temp is not None:
        recipe.curing_temp = curing_temp
    if curing_time is not None:
        recipe.curing_time = curing_time
    if material_consumption is not None:
        recipe.material_consumption = material_consumption
    if notes is not None:
        recipe.notes = notes
    if is_active is not None:
        recipe.is_active = is_active

    await db.commit()
    await db.refresh(recipe)
    return recipe


async def create_coating_record(
    db: AsyncSession,
    recipe_id: int,
    part_id: int,
    processed_qty: int,
    qualified_qty: int,
    rejected_qty: int = 0,
    material_used: Optional[float] = None,
    batch_no: Optional[str] = None,
    notes: Optional[str] = None,
    operator_id: Optional[int] = None,
) -> CoatingRecord:
    """Create a coating production record."""
    record_no = generate_record_no()

    record = CoatingRecord(
        record_no=record_no,
        recipe_id=recipe_id,
        part_id=part_id,
        processed_qty=processed_qty,
        qualified_qty=qualified_qty,
        rejected_qty=rejected_qty,
        material_used=material_used,
        batch_no=batch_no,
        notes=notes,
        operator_id=operator_id,
    )
    db.add(record)

    # Record audit event
    await _record_audit(
        db,
        action="coating_record",
        entity_type="CoatingRecord",
        entity_id=0,
        user_id=operator_id,
        details=f"Part {part_id}: processed={processed_qty}, qualified={qualified_qty}",
    )

    await db.commit()
    await db.refresh(record)
    return record


async def get_coating_record(
    db: AsyncSession,
    record_id: int,
) -> Optional[CoatingRecord]:
    """Get a coating record by ID."""
    result = await db.execute(
        select(CoatingRecord)
        .options(
            joinedload(CoatingRecord.recipe),
            joinedload(CoatingRecord.part),
        )
        .where(CoatingRecord.id == record_id)
    )
    return result.scalar_one_or_none()


async def get_coating_records(
    db: AsyncSession,
    recipe_id: Optional[int] = None,
    part_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[CoatingRecord]:
    """Get coating records with filters."""
    query = (
        select(CoatingRecord)
        .options(
            joinedload(CoatingRecord.recipe),
            joinedload(CoatingRecord.part),
        )
    )

    if recipe_id:
        query = query.where(CoatingRecord.recipe_id == recipe_id)
    if part_id:
        query = query.where(CoatingRecord.part_id == part_id)

    query = query.order_by(CoatingRecord.coating_date.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def _record_audit(
    db: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: int,
    user_id: Optional[int],
    details: str,
) -> None:
    """Record an audit event for coating operations."""
    from src.models.audit import AuditLog

    audit = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        details=details,
        ip_address=None,
    )
    db.add(audit)
