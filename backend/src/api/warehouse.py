"""Warehouse and material batch API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.warehouse import MaterialStatus
from app.schemas.warehouse import (
    IQCUpdate,
    MaterialBatchCreate,
    MaterialBatchListResponse,
    MaterialBatchResponse,
    MaterialBatchUpdate,
    SplitRequest,
    SplitResultResponse,
    SupplierCreate,
    SupplierResponse,
    TraceResponse,
    TraceEntry,
)
from app.services import material_batch_service

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierResponse:
    """Create a new supplier."""
    require_role(current_user, min_level=4)

    supplier = await material_batch_service.create_supplier(db, data.model_dump())
    return SupplierResponse.model_validate(supplier)


@router.get("/suppliers", response_model=list[SupplierResponse])
async def list_suppliers(
    db: DbSession,
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(default=None),
) -> list[SupplierResponse]:
    """List all suppliers."""
    suppliers = await material_batch_service.get_suppliers(db, is_active=is_active)
    return [SupplierResponse.model_validate(s) for s in suppliers]


@router.post("/material-batches", response_model=MaterialBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_material_batch(
    data: MaterialBatchCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Register a new material batch (requires role_level >= 3)."""
    require_role(current_user, min_level=3)

    batch = await material_batch_service.create_material_batch(db, data, current_user)
    return _batch_to_response(batch)


@router.get("/material-batches", response_model=list[MaterialBatchListResponse])
async def list_material_batches(
    db: DbSession,
    current_user: CurrentUser,
    status: Optional[MaterialStatus] = Query(default=None),
    material_grade: Optional[str] = Query(default=None),
    supplier_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[MaterialBatchListResponse]:
    """List material batches with optional filters."""
    batches = await material_batch_service.get_batches(
        db,
        status=status,
        material_grade=material_grade,
        supplier_id=supplier_id,
        skip=skip,
        limit=limit,
    )

    return [
        MaterialBatchListResponse(
            id=b.id,
            batch_no=b.batch_no,
            qr_code=b.qr_code,
            material_grade=b.material_grade,
            material_type=b.material_type,
            weight_kg=b.weight_kg,
            status=b.status,
            supplier_name=b.supplier.name if b.supplier else None,
            warehouse_location=b.warehouse_location,
            received_at=b.received_at,
        )
        for b in batches
    ]


@router.get("/material-batches/{batch_id}", response_model=MaterialBatchResponse)
async def get_material_batch(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Get material batch by ID."""
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")
    return _batch_to_response(batch)


@router.get("/material-batches/lookup/{batch_no}", response_model=MaterialBatchResponse)
async def lookup_material_batch(
    batch_no: str,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Lookup material batch by batch number or QR code."""
    batch = await material_batch_service.get_batch_by_no(db, batch_no)
    if not batch:
        # Try QR code lookup
        batch = await material_batch_service.get_batch_by_qr(db, batch_no)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")
    return _batch_to_response(batch)


@router.patch("/material-batches/{batch_id}", response_model=MaterialBatchResponse)
async def update_material_batch(
    batch_id: int,
    data: MaterialBatchUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Update material batch fields."""
    require_role(current_user, min_level=3)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    batch = await material_batch_service.update_batch(db, batch, data)
    return _batch_to_response(batch)


@router.put("/material-batches/{batch_id}/iqc", response_model=MaterialBatchResponse)
async def process_iqc(
    batch_id: int,
    data: IQCUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Process incoming quality check (IQC) for a material batch."""
    require_role(current_user, min_level=2)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    try:
        batch = await material_batch_service.process_iqc(db, batch, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _batch_to_response(batch)


@router.post("/material-batches/{batch_id}/split", response_model=SplitResultResponse)
async def split_material_batch(
    batch_id: int,
    data: SplitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> SplitResultResponse:
    """Split a material batch into multiple child batches."""
    require_role(current_user, min_level=3)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    try:
        result = await material_batch_service.split_batch(db, batch, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.schemas.warehouse import MaterialBatchChildResponse

    return SplitResultResponse(
        parent_batch_id=result["parent_batch_id"],
        parent_batch_no=result["parent_batch_no"],
        parent_status=result["parent_status"],
        children=[
            MaterialBatchChildResponse(
                id=c.id,
                child_batch_no=c.child_batch_no,
                qr_code=c.qr_code,
                parent_batch_id=c.parent_batch_id,
                width=c.width,
                weight_kg=c.weight_kg,
                pieces=c.pieces,
                position_index=c.position_index,
                status=c.status,
                warehouse_location=c.warehouse_location,
                shelf_location=c.shelf_location,
                created_at=c.created_at,
            )
            for c in result["children"]
        ],
    )


@router.get("/material-batches/{batch_id}/children", response_model=list[dict])
async def get_batch_children(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[dict]:
    """Get child batches for a parent batch."""
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    children = await material_batch_service.get_batch_children(db, batch_id)

    from app.schemas.warehouse import MaterialBatchChildResponse

    return [
        MaterialBatchChildResponse(
            id=c.id,
            child_batch_no=c.child_batch_no,
            qr_code=c.qr_code,
            parent_batch_id=c.parent_batch_id,
            width=c.width,
            weight_kg=c.weight_kg,
            pieces=c.pieces,
            position_index=c.position_index,
            status=c.status,
            warehouse_location=c.warehouse_location,
            shelf_location=c.shelf_location,
            created_at=c.created_at,
        ).model_dump()
        for c in children
    ]


@router.get("/material-batches/{batch_id}/trace", response_model=TraceResponse)
async def trace_material_batch(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> TraceResponse:
    """Get trace history for a material batch."""
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    trace = await material_batch_service.trace_batch(db, batch)

    return TraceResponse(
        batch_id=trace["batch_id"],
        batch_no=trace["batch_no"],
        qr_code=trace["qr_code"],
        material_grade=trace["material_grade"],
        current_status=trace["current_status"],
        original_weight_kg=trace["original_weight_kg"],
        current_weight_kg=trace["current_weight_kg"],
        entries=[
            TraceEntry(
                timestamp=e["timestamp"],
                event_type=e["event_type"],
                description=e["description"],
                operator_id=e.get("operator_id"),
                reference_no=e.get("reference_no"),
                details=e.get("details"),
            )
            for e in trace["entries"]
        ],
    )


def _batch_to_response(batch) -> MaterialBatchResponse:
    """Convert MaterialBatch to response."""
    return MaterialBatchResponse(
        id=batch.id,
        batch_no=batch.batch_no,
        qr_code=batch.qr_code,
        material_grade=batch.material_grade,
        material_type=batch.material_type,
        thickness=batch.thickness,
        width=batch.width,
        weight_kg=batch.weight_kg,
        original_weight_kg=batch.original_weight_kg,
        supplier_id=batch.supplier_id,
        supplier_name=batch.supplier.name if batch.supplier else None,
        purchase_order_no=batch.purchase_order_no,
        invoice_no=batch.invoice_no,
        unit_price=batch.unit_price,
        total_amount=batch.total_amount,
        slit_width=batch.slit_width,
        slit_pieces=batch.slit_pieces,
        status=batch.status,
        iqc_result=batch.iqc_result,
        iqc_by=batch.iqc_by,
        iqc_at=batch.iqc_at,
        iqc_notes=batch.iqc_notes,
        parent_id=batch.parent_id,
        warehouse_location=batch.warehouse_location,
        shelf_location=batch.shelf_location,
        consumed_qty=batch.consumed_qty,
        received_at=batch.received_at,
        created_at=batch.created_at,
    )
