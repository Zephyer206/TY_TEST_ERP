"""Coating (spray painting) management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from src.api.deps import CurrentUser, DbSession, require_role
from src.models.coating import CoatingRecipe, CoatingRecord
from src.models.part import Part
from src.schemas.coating import (
    CoatingRecipeCreate,
    CoatingRecipeResponse,
    CoatingRecipeUpdate,
    CoatingRecordCreate,
    CoatingRecordResponse,
)
from src.services import coating_service

router = APIRouter(prefix="/coating", tags=["Coating"])


def _recipe_to_response(recipe: CoatingRecipe) -> CoatingRecipeResponse:
    """Convert CoatingRecipe to response."""
    return CoatingRecipeResponse(
        id=recipe.id,
        recipe_no=recipe.recipe_no,
        name=recipe.name,
        coating_type=recipe.coating_type,
        color_type=recipe.color_type,
        color_code=recipe.color_code,
        primer_type=recipe.primer_type,
        primer_thickness=recipe.primer_thickness,
        topcoat_type=recipe.topcoat_type,
        topcoat_thickness=recipe.topcoat_thickness,
        spray_pressure=recipe.spray_pressure,
        spray_distance=recipe.spray_distance,
        spray_speed=recipe.spray_speed,
        curing_temp=recipe.curing_temp,
        curing_time=recipe.curing_time,
        material_consumption=recipe.material_consumption,
        notes=recipe.notes,
        is_active=recipe.is_active,
        created_at=recipe.created_at,
    )


def _record_to_response(record: CoatingRecord) -> CoatingRecordResponse:
    """Convert CoatingRecord to response."""
    return CoatingRecordResponse(
        id=record.id,
        record_no=record.record_no,
        recipe_id=record.recipe_id,
        recipe_name=record.recipe.name if record.recipe else None,
        part_id=record.part_id,
        processed_qty=record.processed_qty,
        qualified_qty=record.qualified_qty,
        rejected_qty=record.rejected_qty,
        material_used=record.material_used,
        batch_no=record.batch_no,
        notes=record.notes,
        operator_id=record.operator_id,
        coating_date=record.coating_date,
        created_at=record.created_at,
    )


# Recipe endpoints

@router.post("/recipes", response_model=CoatingRecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    data: CoatingRecipeCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecipeResponse:
    """Create a new coating recipe.

    Used by coating supervisors to configure spray painting formulas.
    """
    require_role(current_user, min_level=3)

    recipe = await coating_service.create_recipe(
        db,
        name=data.name,
        coating_type=data.coating_type.value,
        color_type=data.color_type.value,
        color_code=data.color_code,
        primer_type=data.primer_type,
        primer_thickness=data.primer_thickness,
        topcoat_type=data.topcoat_type,
        topcoat_thickness=data.topcoat_thickness,
        spray_pressure=data.spray_pressure,
        spray_distance=data.spray_distance,
        spray_speed=data.spray_speed,
        curing_temp=data.curing_temp,
        curing_time=data.curing_time,
        material_consumption=data.material_consumption,
        notes=data.notes,
    )
    return _recipe_to_response(recipe)


@router.get("/recipes", response_model=list[CoatingRecipeResponse])
async def list_recipes(
    db: DbSession,
    current_user: CurrentUser,
    coating_type: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[CoatingRecipeResponse]:
    """List coating recipes."""
    recipes = await coating_service.get_recipes(
        db,
        coating_type=coating_type,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return [_recipe_to_response(r) for r in recipes]


@router.get("/recipes/{recipe_id}", response_model=CoatingRecipeResponse)
async def get_recipe(
    recipe_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecipeResponse:
    """Get a coating recipe by ID."""
    recipe = await coating_service.get_recipe(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Coating recipe not found")
    return _recipe_to_response(recipe)


@router.put("/recipes/{recipe_id}", response_model=CoatingRecipeResponse)
async def update_recipe(
    recipe_id: int,
    data: CoatingRecipeUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecipeResponse:
    """Update a coating recipe."""
    require_role(current_user, min_level=3)

    recipe = await coating_service.get_recipe(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Coating recipe not found")

    recipe = await coating_service.update_recipe(
        db,
        recipe,
        name=data.name,
        coating_type=data.coating_type.value if data.coating_type else None,
        color_type=data.color_type.value if data.color_type else None,
        color_code=data.color_code,
        primer_type=data.primer_type,
        primer_thickness=data.primer_thickness,
        topcoat_type=data.topcoat_type,
        topcoat_thickness=data.topcoat_thickness,
        spray_pressure=data.spray_pressure,
        spray_distance=data.spray_distance,
        spray_speed=data.spray_speed,
        curing_temp=data.curing_temp,
        curing_time=data.curing_time,
        material_consumption=data.material_consumption,
        notes=data.notes,
        is_active=data.is_active,
    )
    return _recipe_to_response(recipe)


# Record endpoints

@router.post("/records", response_model=CoatingRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_coating_record(
    data: CoatingRecordCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecordResponse:
    """Create a coating production record.

    Used by coating operators to record spray painting work.
    """
    require_role(current_user, min_level=1)

    # Verify recipe exists
    recipe = await coating_service.get_recipe(db, data.recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Coating recipe not found")

    # Verify part exists
    result = await db.execute(select(Part).where(Part.id == data.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Validate quantities
    if data.qualified_qty > data.processed_qty:
        raise HTTPException(
            status_code=400,
            detail="Qualified quantity cannot exceed processed quantity",
        )

    record = await coating_service.create_coating_record(
        db,
        recipe_id=data.recipe_id,
        part_id=data.part_id,
        processed_qty=data.processed_qty,
        qualified_qty=data.qualified_qty,
        rejected_qty=data.rejected_qty,
        material_used=data.material_used,
        batch_no=data.batch_no,
        notes=data.notes,
        operator_id=current_user.id,
    )
    return _record_to_response(record)


@router.get("/records", response_model=list[CoatingRecordResponse])
async def list_coating_records(
    db: DbSession,
    current_user: CurrentUser,
    recipe_id: Optional[int] = Query(default=None),
    part_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[CoatingRecordResponse]:
    """List coating records."""
    records = await coating_service.get_coating_records(
        db,
        recipe_id=recipe_id,
        part_id=part_id,
        skip=skip,
        limit=limit,
    )
    return [_record_to_response(r) for r in records]


@router.get("/records/{record_id}", response_model=CoatingRecordResponse)
async def get_coating_record(
    record_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecordResponse:
    """Get a coating record by ID."""
    record = await coating_service.get_coating_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Coating record not found")
    return _record_to_response(record)
