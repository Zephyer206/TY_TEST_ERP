"""Coating (spray painting) API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.coating import RecipeStatus, RecordStatus
from app.schemas.coating import (
    CoatingMaterialInventoryResponse,
    CoatingRecipeCreate,
    CoatingRecipeResponse,
    CoatingRecipeUpdate,
    CoatingRecordCreate,
    CoatingRecordListResponse,
    CoatingRecordResponse,
    CoatingRecordUpdate,
)
from app.services import coating_service

router = APIRouter(prefix="/coating", tags=["Coating"])


# Recipe Endpoints

@router.post("/recipes", response_model=CoatingRecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    data: CoatingRecipeCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecipeResponse:
    """Create a new coating recipe (requires role_level >= 4)."""
    require_role(current_user, min_level=4)

    recipe = await coating_service.create_recipe(db, data.model_dump())
    return _recipe_to_response(recipe)


@router.get("/recipes", response_model=list[CoatingRecipeResponse])
async def list_recipes(
    db: DbSession,
    current_user: CurrentUser,
    status: Optional[RecipeStatus] = Query(default=None),
    coating_type: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[CoatingRecipeResponse]:
    """List coating recipes."""
    recipes = await coating_service.get_recipes(
        db, status=status, coating_type=coating_type, skip=skip, limit=limit
    )
    return [_recipe_to_response(r) for r in recipes]


@router.get("/recipes/{recipe_id}", response_model=CoatingRecipeResponse)
async def get_recipe(
    recipe_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecipeResponse:
    """Get coating recipe by ID."""
    recipe = await coating_service.get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _recipe_to_response(recipe)


@router.patch("/recipes/{recipe_id}", response_model=CoatingRecipeResponse)
async def update_recipe(
    recipe_id: int,
    data: CoatingRecipeUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecipeResponse:
    """Update a coating recipe (requires role_level >= 4)."""
    require_role(current_user, min_level=4)

    recipe = await coating_service.get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe = await coating_service.update_recipe(db, recipe, data.model_dump(exclude_unset=True))
    return _recipe_to_response(recipe)


# Record Endpoints

@router.post("/records", response_model=CoatingRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_coating_record(
    data: CoatingRecordCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecordResponse:
    """Create a new coating record (requires role_level >= 1)."""
    require_role(current_user, min_level=1)

    try:
        record = await coating_service.create_coating_record(
            db, data.model_dump(), current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _record_to_response(record)


@router.get("/records", response_model=list[CoatingRecordListResponse])
async def list_coating_records(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    recipe_id: Optional[int] = Query(default=None),
    status: Optional[RecordStatus] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[CoatingRecordListResponse]:
    """List coating records."""
    records = await coating_service.get_records(
        db, part_id=part_id, recipe_id=recipe_id, status=status, skip=skip, limit=limit
    )
    return [_record_to_list_response(r) for r in records]


@router.get("/records/{record_id}", response_model=CoatingRecordResponse)
async def get_coating_record(
    record_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecordResponse:
    """Get coating record by ID."""
    record = await coating_service.get_record_by_id(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Coating record not found")
    return _record_to_response(record)


@router.get("/records/barcode/{barcode}", response_model=CoatingRecordResponse)
async def get_record_by_barcode(
    barcode: str,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecordResponse:
    """Get coating record by work order barcode."""
    record = await coating_service.get_record_by_barcode(db, barcode)
    if not record:
        raise HTTPException(status_code=404, detail="Coating record not found")
    return _record_to_response(record)


@router.post("/records/{record_id}/start", response_model=CoatingRecordResponse)
async def start_coating(
    record_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecordResponse:
    """Start coating operation (requires role_level >= 1)."""
    require_role(current_user, min_level=1)

    record = await coating_service.get_record_by_id(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Coating record not found")

    try:
        record = await coating_service.start_coating(db, record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _record_to_response(record)


@router.post("/records/{record_id}/complete", response_model=CoatingRecordResponse)
async def complete_coating(
    record_id: int,
    data: CoatingRecordUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> CoatingRecordResponse:
    """Complete coating operation (requires role_level >= 1)."""
    require_role(current_user, min_level=1)

    record = await coating_service.get_record_by_id(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Coating record not found")

    try:
        record = await coating_service.complete_coating(
            db,
            record,
            passed_qty=data.passed_qty,
            rejected_qty=data.rejected_qty or 0,
            paint_used_kg=data.paint_used_kg,
            solvent_used_kg=data.solvent_used_kg,
            actual_params=data.actual_params,
            quality_check_result=data.quality_check_result,
            quality_check_notes=data.quality_check_notes,
            operator=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _record_to_response(record)


@router.post("/records/{record_id}/reject", response_model=CoatingRecordResponse)
async def reject_coating(
    record_id: int,
    rejected_qty: int,
    db: DbSession,
    current_user: CurrentUser,
    notes: Optional[str] = None,
) -> CoatingRecordResponse:
    """Reject coating operation (requires role_level >= 2)."""
    require_role(current_user, min_level=2)

    record = await coating_service.get_record_by_id(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Coating record not found")

    try:
        record = await coating_service.reject_coating(
            db, record, rejected_qty, notes, current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _record_to_response(record)


# Material Inventory Endpoints

@router.get("/materials", response_model=list[CoatingMaterialInventoryResponse])
async def list_materials(
    db: DbSession,
    current_user: CurrentUser,
    material_type: Optional[str] = Query(default=None),
) -> list[CoatingMaterialInventoryResponse]:
    """List coating material inventory."""
    materials = await coating_service.get_material_inventory(db, material_type=material_type)
    return [CoatingMaterialInventoryResponse.model_validate(m) for m in materials]


# Helper functions

def _recipe_to_response(recipe) -> CoatingRecipeResponse:
    """Convert CoatingRecipe to response."""
    return CoatingRecipeResponse(
        id=recipe.id,
        recipe_no=recipe.recipe_no,
        name=recipe.name,
        color_code=recipe.color_code,
        color_name=recipe.color_name,
        coating_type=recipe.coating_type,
        process_params=recipe.process_params,
        material_consumption=recipe.material_consumption,
        coating_cost_per_part=recipe.coating_cost_per_part,
        quality_standards=recipe.quality_standards,
        status=recipe.status,
        compatible_parts=recipe.compatible_parts,
        notes=recipe.notes,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )


def _record_to_response(record) -> CoatingRecordResponse:
    """Convert CoatingRecord to response."""
    return CoatingRecordResponse(
        id=record.id,
        record_no=record.record_no,
        part_id=record.part_id,
        part_no=record.part.part_no if record.part else None,
        part_name=record.part.part_name if record.part else None,
        recipe_id=record.recipe_id,
        recipe_name=record.recipe.name if record.recipe else None,
        production_batch_no=record.production_batch_no,
        process_flow_no=record.process_flow_no,
        work_order_barcode=record.work_order_barcode,
        input_qty=record.input_qty,
        passed_qty=record.passed_qty,
        rejected_qty=record.rejected_qty,
        paint_used_kg=record.paint_used_kg,
        solvent_used_kg=record.solvent_used_kg,
        actual_consumption_per_part=record.actual_consumption_per_part,
        actual_params=record.actual_params,
        status=record.status,
        quality_check_result=record.quality_check_result,
        quality_check_notes=record.quality_check_notes,
        quality_check_by=record.quality_check_by,
        quality_check_at=record.quality_check_at,
        operator_id=record.operator_id,
        equipment_id=record.equipment_id,
        booth_no=record.booth_no,
        started_at=record.started_at,
        completed_at=record.completed_at,
        notes=record.notes,
        created_at=record.created_at,
    )


def _record_to_list_response(record) -> CoatingRecordListResponse:
    """Convert CoatingRecord to list response."""
    return CoatingRecordListResponse(
        id=record.id,
        record_no=record.record_no,
        part_id=record.part_id,
        part_no=record.part.part_no if record.part else None,
        part_name=record.part.part_name if record.part else None,
        recipe_name=record.recipe.name if record.recipe else None,
        input_qty=record.input_qty,
        passed_qty=record.passed_qty,
        rejected_qty=record.rejected_qty,
        status=record.status,
        operator_id=record.operator_id,
        started_at=record.started_at,
        completed_at=record.completed_at,
    )
