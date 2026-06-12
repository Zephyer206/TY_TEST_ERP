"""Parts API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.part import Part, PartState
from app.schemas.part import (
    PartImportRow,
    PartResponse,
    PartUpdate,
)
from app.services import part_service

router = APIRouter(prefix="/parts", tags=["Parts"])


def _part_to_response(part: Part) -> PartResponse:
    """Convert Part model to response."""
    return PartResponse(
        id=part.id,
        part_no=part.part_no,
        part_name=part.part_name,
        customer_id=part.customer_id,
        customer_name=part.customer.name if part.customer else None,
        quote_id=part.quote_id,
        state=part.state,
        customer_part_no=part.customer_part_no,
        vehicle_model=part.vehicle_model,
        drawing_no=part.drawing_no,
        material=part.material,
        thickness=part.thickness,
        width=part.width,
        weight_kg=part.weight_kg,
        cavity_count=part.cavity_count,
        tonnage=part.tonnage,
        mold_id=part.mold_id,
        mold_no=part.mold_no,
        mold_type=part.mold_type,
        ppap_no=part.ppap_no,
        price_snapshot=part.price_snapshot,
        stock_pcs=part.stock_pcs,
        drawing_path=part.drawing_path,
        created_at=part.created_at,
        updated_at=part.updated_at,
    )


@router.get("/{part_id}", response_model=PartResponse)
async def get_part(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PartResponse:
    """Get part by ID."""
    part = await part_service.get_part_by_id(db, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return _part_to_response(part)


@router.get("", response_model=list[PartResponse])
async def list_parts(
    db: DbSession,
    current_user: CurrentUser,
    customer_id: Optional[int] = Query(default=None),
    state: Optional[PartState] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PartResponse]:
    """List parts with optional filters."""
    query = (
        select(Part)
        .options(selectinload(Part.customer))
        .where(Part.is_deleted == False)
    )
    if customer_id:
        query = query.where(Part.customer_id == customer_id)
    if state:
        query = query.where(Part.state == state)

    query = query.order_by(Part.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    parts = result.scalars().all()

    return [_part_to_response(p) for p in parts]


@router.patch("/{part_id}", response_model=PartResponse)
async def update_part(
    part_id: int,
    data: PartUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> PartResponse:
    """Update part fields."""
    require_role(current_user, min_level=4)

    part = await part_service.get_part_by_id(db, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        if hasattr(part, field):
            setattr(part, field, value)

    await db.commit()
    await db.refresh(part)
    return _part_to_response(part)


@router.post("/{part_id}/transition-state", response_model=PartResponse)
async def transition_part_state(
    part_id: int,
    new_state: PartState,
    db: DbSession,
    current_user: CurrentUser,
) -> PartResponse:
    """Transition part to a new state."""
    require_role(current_user, min_level=4)

    part = await part_service.get_part_by_id(db, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    try:
        part = await part_service.update_part_state(db, part, new_state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _part_to_response(part)


@router.post("/{part_id}/to-mass-production", response_model=PartResponse)
async def transition_to_mass_production(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PartResponse:
    """Transition part from Sampling to MassProduction."""
    require_role(current_user, min_level=4)

    part = await part_service.get_part_by_id(db, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    try:
        part = await part_service.transition_to_mass_production(db, part)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _part_to_response(part)


@router.post("/{part_id}/import-excel", response_model=list[PartResponse], status_code=status.HTTP_201_CREATED)
async def import_parts_from_excel(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> list[PartResponse]:
    """Import part parameters from Excel template after fix confirmation.

    Accepts an Excel file with columns:
    - material: 材质
    - net_weight_kg: 净重 (kg)
    - gross_weight_kg: 毛重 (kg)
    - material_unit_price: 材料单价
    - scrap_price: 废料价
    - surface_treatment: 表面处理工艺类型
    - drawing_path: 图纸/产品图 (file path or URL)
    """
    require_role(current_user, min_level=5)

    part = await part_service.get_part_by_id(db, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    import openpyxl
    from io import BytesIO

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files (.xlsx, .xls) are supported",
        )

    contents = await file.read()
    try:
        wb = openpyxl.load_workbook(BytesIO(contents))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse Excel file: {str(e)}",
        )

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel file must have header and at least one data row")

    headers = [str(h).strip() if h else "" for h in rows[0]]
    data_rows = rows[1:]

    column_map = {}
    for idx, header in enumerate(headers):
        h = header.lower()
        if "材质" in h or "material" in h:
            column_map["material"] = idx
        elif "净重" in h or "net_weight" in h:
            column_map["net_weight_kg"] = idx
        elif "毛重" in h or "gross_weight" in h:
            column_map["gross_weight_kg"] = idx
        elif "材料单价" in h or "material_price" in h:
            column_map["material_unit_price"] = idx
        elif "废料" in h or "scrap" in h:
            column_map["scrap_price"] = idx
        elif "表面处理" in h or "surface" in h:
            column_map["surface_treatment"] = idx
        elif "图纸" in h or "drawing" in h:
            column_map["drawing_path"] = idx

    updated_parts = []
    for row_idx, row in enumerate(data_rows):
        if not any(row):
            continue

        from app.core.file_service import migrate_drawing, get_drawing_path
        from app.models.price import PriceAccount
        from app.services.price_service import create_price_account, get_price_account_by_part_customer

        material = _get_cell(row, column_map.get("material"))
        net_weight = _get_float(row, column_map.get("net_weight_kg"))
        gross_weight = _get_float(row, column_map.get("gross_weight_kg"))
        material_unit_price = _get_decimal(row, column_map.get("material_unit_price"))
        scrap_price = _get_decimal(row, column_map.get("scrap_price"))
        surface_treatment = _get_cell(row, column_map.get("surface_treatment"))
        drawing_path = _get_cell(row, column_map.get("drawing_path"))

        if material:
            part.material = material
        if net_weight is not None:
            part.net_weight_kg = net_weight
        if gross_weight is not None:
            part.gross_weight_kg = gross_weight
        if drawing_path:
            safe_name = f"{part.part_name}_{part.created_at.strftime('%Y%m%d')}"
            new_path = get_drawing_path(
                customer_name=part.customer.name if part.customer else "unknown",
                part_name=safe_name,
                filename=drawing_path,
            )
            part.drawing_path = new_path

        await db.commit()
        await db.refresh(part)
        updated_parts.append(part)

        if material_unit_price is not None or scrap_price is not None:
            existing = await get_price_account_by_part_customer(db, part.id, part.customer_id)
            if not existing:
                await create_price_account(
                    db,
                    part_id=part.id,
                    customer_id=part.customer_id,
                    material=material or part.material,
                    net_weight_kg=net_weight,
                    gross_weight_kg=gross_weight,
                    material_unit_price=material_unit_price,
                    scrap_price=scrap_price,
                    reduction_pct=0.0,
                )

    return [_part_to_response(p) for p in updated_parts]


def _get_cell(row, idx: Optional[int]) -> Optional[str]:
    if idx is None or idx >= len(row):
        return None
    val = row[idx]
    if val is None:
        return None
    return str(val).strip()


def _get_float(row, idx: Optional[int]) -> Optional[float]:
    val = _get_cell(row, idx)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_decimal(row, idx: Optional[int]) -> Optional["Decimal"]:
    val = _get_float(row, idx)
    if val is None:
        return None
    from decimal import Decimal
    return Decimal(str(val))
