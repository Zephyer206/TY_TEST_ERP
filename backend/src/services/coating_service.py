"""Business logic for coating (spray painting) management."""

import secrets
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.coating import (
    CoatingMaterialInventory,
    CoatingRecipe,
    CoatingRecord,
    RecipeStatus,
    RecordStatus,
)
from app.models.part import Part
from app.models.user import User


def generate_recipe_no(db: AsyncSession) -> str:
    """Generate a unique recipe number."""
    suffix = secrets.token_hex(3).upper()[:6]
    return f"REC-{suffix}"


def generate_record_no(db: AsyncSession) -> str:
    """Generate a unique coating record number."""
    now = datetime.utcnow()
    suffix = secrets.token_hex(3).upper()[:6]
    return f"COAT-{now.strftime('%Y%m%d')}-{suffix}"


# Recipe Operations

async def create_recipe(
    db: AsyncSession,
    data: dict,
) -> CoatingRecipe:
    """Create a new coating recipe."""
    recipe_no = generate_recipe_no(db)

    recipe = CoatingRecipe(
        recipe_no=recipe_no,
        name=data["name"],
        color_code=data.get("color_code"),
        color_name=data.get("color_name"),
        coating_type=data["coating_type"],
        process_params=data.get("process_params"),
        material_consumption=data.get("material_consumption"),
        coating_cost_per_part=data.get("coating_cost_per_part"),
        quality_standards=data.get("quality_standards"),
        status=data.get("status", RecipeStatus.ACTIVE),
        compatible_parts=data.get("compatible_parts"),
        notes=data.get("notes"),
    )
    db.add(recipe)
    await db.commit()
    await db.refresh(recipe)
    return recipe


async def get_recipe_by_id(
    db: AsyncSession,
    recipe_id: int,
) -> Optional[CoatingRecipe]:
    """Get coating recipe by ID."""
    result = await db.execute(
        select(CoatingRecipe).where(
            CoatingRecipe.id == recipe_id,
            CoatingRecipe.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_recipes(
    db: AsyncSession,
    status: Optional[RecipeStatus] = None,
    coating_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[CoatingRecipe]:
    """Get coating recipes with filters."""
    query = select(CoatingRecipe).where(CoatingRecipe.is_deleted == False)

    if status:
        query = query.where(CoatingRecipe.status == status)
    if coating_type:
        query = query.where(CoatingRecipe.coating_type == coating_type)

    query = query.order_by(CoatingRecipe.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_recipe(
    db: AsyncSession,
    recipe: CoatingRecipe,
    data: dict,
) -> CoatingRecipe:
    """Update a coating recipe."""
    for field, value in data.items():
        if value is not None and hasattr(recipe, field):
            setattr(recipe, field, value)

    await db.commit()
    await db.refresh(recipe)
    return recipe


# Record Operations

async def create_coating_record(
    db: AsyncSession,
    data: dict,
    operator: User,
) -> CoatingRecord:
    """Create a new coating record."""
    # Validate part exists
    part_result = await db.execute(select(Part).where(Part.id == data["part_id"]))
    part = part_result.scalar_one_or_none()
    if not part:
        raise ValueError("Part not found")

    # Validate recipe if provided
    if data.get("recipe_id"):
        recipe_result = await db.execute(
            select(CoatingRecipe).where(CoatingRecipe.id == data["recipe_id"])
        )
        recipe = recipe_result.scalar_one_or_none()
        if not recipe:
            raise ValueError("Recipe not found")

    record_no = generate_record_no(db)

    record = CoatingRecord(
        record_no=record_no,
        part_id=data["part_id"],
        recipe_id=data.get("recipe_id"),
        work_order_barcode=data.get("work_order_barcode"),
        production_batch_no=data.get("production_batch_no"),
        process_flow_no=data.get("process_flow_no"),
        input_qty=data["input_qty"],
        equipment_id=data.get("equipment_id"),
        booth_no=data.get("booth_no"),
        notes=data.get("notes"),
        status=RecordStatus.PENDING,
        operator_id=operator.id if hasattr(operator, 'id') else None,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_record_by_id(
    db: AsyncSession,
    record_id: int,
) -> Optional[CoatingRecord]:
    """Get coating record by ID."""
    result = await db.execute(
        select(CoatingRecord)
        .options(
            selectinload(CoatingRecord.part),
            selectinload(CoatingRecord.recipe),
        )
        .where(
            CoatingRecord.id == record_id,
            CoatingRecord.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_record_by_barcode(
    db: AsyncSession,
    barcode: str,
) -> Optional[CoatingRecord]:
    """Get coating record by work order barcode."""
    result = await db.execute(
        select(CoatingRecord)
        .options(
            selectinload(CoatingRecord.part),
            selectinload(CoatingRecord.recipe),
        )
        .where(
            CoatingRecord.work_order_barcode == barcode,
            CoatingRecord.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_records(
    db: AsyncSession,
    part_id: Optional[int] = None,
    recipe_id: Optional[int] = None,
    status: Optional[RecordStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[CoatingRecord]:
    """Get coating records with filters."""
    query = (
        select(CoatingRecord)
        .options(
            selectinload(CoatingRecord.part),
            selectinload(CoatingRecord.recipe),
        )
        .where(CoatingRecord.is_deleted == False)
    )

    if part_id:
        query = query.where(CoatingRecord.part_id == part_id)
    if recipe_id:
        query = query.where(CoatingRecord.recipe_id == recipe_id)
    if status:
        query = query.where(CoatingRecord.status == status)

    query = query.order_by(CoatingRecord.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def start_coating(
    db: AsyncSession,
    record: CoatingRecord,
) -> CoatingRecord:
    """Mark coating as in progress."""
    if record.status != RecordStatus.PENDING:
        raise ValueError(f"Cannot start coating from status: {record.status.value}")

    record.status = RecordStatus.IN_PROGRESS
    record.started_at = datetime.utcnow()

    await db.commit()
    await db.refresh(record)
    return record


async def complete_coating(
    db: AsyncSession,
    record: CoatingRecord,
    passed_qty: int,
    rejected_qty: int,
    paint_used_kg: Optional[float],
    solvent_used_kg: Optional[float],
    actual_params: Optional[dict],
    quality_check_result: Optional[str],
    quality_check_notes: Optional[str],
    operator: User,
) -> CoatingRecord:
    """Complete coating operation and record results."""
    # Validate quantities
    if passed_qty + rejected_qty > record.input_qty:
        raise ValueError("passed_qty + rejected_qty cannot exceed input_qty")

    # Calculate actual consumption
    total_output = passed_qty + rejected_qty
    if total_output > 0:
        actual_consumption = (paint_used_kg or 0) / total_output if paint_used_kg else None
    else:
        actual_consumption = None

    record.passed_qty = passed_qty
    record.rejected_qty = rejected_qty
    record.paint_used_kg = paint_used_kg
    record.solvent_used_kg = solvent_used_kg
    record.actual_consumption_per_part = actual_consumption
    record.actual_params = actual_params
    record.status = RecordStatus.COMPLETED
    record.quality_check_result = quality_check_result
    record.quality_check_notes = quality_check_notes
    record.quality_check_by = operator.id if hasattr(operator, 'id') else None
    record.quality_check_at = datetime.utcnow()
    record.completed_at = datetime.utcnow()

    # Update material inventory
    if paint_used_kg:
        await _deduct_material(
            db, "paint", paint_used_kg, operator
        )
    if solvent_used_kg:
        await _deduct_material(
            db, "solvent", solvent_used_kg, operator
        )

    await db.commit()
    await db.refresh(record)
    return record


async def _deduct_material(
    db: AsyncSession,
    material_type: str,
    quantity_kg: float,
    operator: User,
) -> None:
    """Deduct material from coating inventory."""
    result = await db.execute(
        select(CoatingMaterialInventory)
        .where(CoatingMaterialInventory.material_type == material_type)
        .order_by(CoatingMaterialInventory.updated_at.desc())
        .limit(1)
    )
    inventory = result.scalar_one_or_none()

    if inventory:
        if inventory.current_qty_kg < quantity_kg:
            raise ValueError(f"Insufficient {material_type} inventory")
        inventory.current_qty_kg -= quantity_kg


async def reject_coating(
    db: AsyncSession,
    record: CoatingRecord,
    rejected_qty: int,
    notes: Optional[str],
    operator: User,
) -> CoatingRecord:
    """Reject coating operation."""
    if rejected_qty > record.input_qty - record.passed_qty:
        raise ValueError("rejected_qty exceeds remaining quantity")

    record.rejected_qty = rejected_qty
    record.status = RecordStatus.REJECTED
    record.notes = notes
    record.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(record)
    return record


# Material Inventory Operations

async def get_material_inventory(
    db: AsyncSession,
    material_type: Optional[str] = None,
) -> Sequence[CoatingMaterialInventory]:
    """Get coating material inventory."""
    query = select(CoatingMaterialInventory).where(
        CoatingMaterialInventory.is_deleted == False
    )

    if material_type:
        query = query.where(CoatingMaterialInventory.material_type == material_type)

    result = await db.execute(query)
    return result.scalars().all()


async def create_material(
    db: AsyncSession,
    data: dict,
) -> CoatingMaterialInventory:
    """Create a new coating material."""
    material = CoatingMaterialInventory(
        material_type=data["material_type"],
        material_name=data["material_name"],
        color_code=data.get("color_code"),
        current_qty_kg=data.get("current_qty_kg", 0),
        unit=data.get("unit", "kg"),
        reorder_point_kg=data.get("reorder_point_kg"),
        supplier_id=data.get("supplier_id"),
        warehouse_location=data.get("warehouse_location"),
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material


async def update_material_qty(
    db: AsyncSession,
    material_id: int,
    quantity_kg: float,
) -> CoatingMaterialInventory:
    """Update material quantity (for receiving)."""
    result = await db.execute(
        select(CoatingMaterialInventory).where(
            CoatingMaterialInventory.id == material_id
        )
    )
    material = result.scalar_one_or_none()
    if not material:
        raise ValueError("Material not found")

    material.current_qty_kg += quantity_kg
    await db.commit()
    await db.refresh(material)
    return material
