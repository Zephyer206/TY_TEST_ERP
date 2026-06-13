"""Warehouse and material batch management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.warehouse import (
    BatchStatus,
    BatchTransaction,
    IQCResult,
    Material,
    MaterialBatch,
    MaterialBatchChild,
    Supplier,
)
from app.schemas.warehouse import (
    BatchConsumeRequest,
    BatchScrapRequest,
    BatchSplitRequest,
    BatchTraceResponse,
    BatchTransactionResponse,
    IQCUpdate,
    MaterialBatchCreate,
    MaterialBatchDetailResponse,
    MaterialBatchResponse,
    MaterialBatchChildResponse,
    MaterialCreate,
    MaterialResponse,
    SupplierCreate,
    SupplierResponse,
)
from app.services import material_batch_service

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


def _batch_to_response(batch: MaterialBatch) -> MaterialBatchResponse:
    """Convert MaterialBatch to response."""
    return MaterialBatchResponse(
        id=batch.id,
        batch_no=batch.batch_no,
        qr_code=batch.qr_code,
        material_id=batch.material_id,
        supplier_id=batch.supplier_id,
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        gross_weight=batch.gross_weight,
        net_weight=batch.net_weight,
        current_weight=batch.current_weight,
        status=batch.status,
        iqc_result=batch.iqc_result,
        iqc_time=batch.iqc_time,
        iqc_by=batch.iqc_by,
        iqc_notes=batch.iqc_notes,
        parent_batch_id=batch.parent_batch_id,
        po_no=batch.po_no,
        received_at=batch.received_at,
        created_at=batch.created_at,
    )


def _batch_detail_to_response(batch: MaterialBatch) -> MaterialBatchDetailResponse:
    """Convert MaterialBatch to detail response."""
    children = []
    if batch.children:
        for child in batch.children:
            children.append(
                MaterialBatchChildResponse(
                    id=child.id,
                    child_batch_no=child.child_batch_no,
                    child_qr_code=child.child_qr_code,
                    width=child.width,
                    length=child.length,
                    current_weight=child.current_weight,
                    status=child.status,
                    created_at=child.created_at,
                )
            )

    return MaterialBatchDetailResponse(
        id=batch.id,
        batch_no=batch.batch_no,
        qr_code=batch.qr_code,
        material_id=batch.material_id,
        material_name=batch.material.name if batch.material else None,
        material_grade=batch.material.grade if batch.material else None,
        supplier_id=batch.supplier_id,
        supplier_name=batch.supplier.name if batch.supplier else None,
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        gross_weight=batch.gross_weight,
        net_weight=batch.net_weight,
        current_weight=batch.current_weight,
        status=batch.status,
        iqc_result=batch.iqc_result,
        iqc_time=batch.iqc_time,
        iqc_by=batch.iqc_by,
        iqc_notes=batch.iqc_notes,
        parent_batch_id=batch.parent_batch_id,
        po_no=batch.po_no,
        received_at=batch.received_at,
        created_at=batch.created_at,
        children=children,
    )


@router.post("/material-batches", response_model=MaterialBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_material_batch(
    data: MaterialBatchCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Create a new material batch (register incoming material)."""
    require_role(current_user, min_level=3)

    # Verify material exists
    result = await db.execute(select(Material).where(Material.id == data.material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Verify supplier if provided
    if data.supplier_id:
        result = await db.execute(select(Supplier).where(Supplier.id == data.supplier_id))
        supplier = result.scalar_one_or_none()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")

    batch = await material_batch_service.create_material_batch(
        db,
        material_id=data.material_id,
        gross_weight=data.gross_weight,
        supplier_id=data.supplier_id,
        thickness=data.thickness,
        width=data.width,
        length=data.length,
        po_no=data.po_no,
    )
    return _batch_to_response(batch)


@router.get("/material-batches", response_model=list[MaterialBatchResponse])
async def list_material_batches(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[BatchStatus] = Query(default=None, alias="status"),
    material_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[MaterialBatchResponse]:
    """List material batches with optional filters."""
    batches = await material_batch_service.get_batches(
        db,
        status=status_filter,
        material_id=material_id,
        skip=skip,
        limit=limit,
    )
    return [_batch_to_response(b) for b in batches]


@router.get("/material-batches/{batch_id}", response_model=MaterialBatchDetailResponse)
async def get_material_batch(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchDetailResponse:
    """Get material batch details."""
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")
    return _batch_detail_to_response(batch)


@router.get("/material-batches/by-no/{batch_no}", response_model=MaterialBatchDetailResponse)
async def get_material_batch_by_no(
    batch_no: str,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchDetailResponse:
    """Get material batch by batch number."""
    batch = await material_batch_service.get_batch_by_no(db, batch_no)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")
    return _batch_detail_to_response(batch)


@router.put("/material-batches/{batch_id}/iqc", response_model=MaterialBatchResponse)
async def perform_iqc(
    batch_id: int,
    data: IQCUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Perform IQC inspection on a material batch."""
    require_role(current_user, min_level=3)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    try:
        batch = await material_batch_service.perform_iqc(
            db, batch, data.result, current_user.id, data.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _batch_to_response(batch)


@router.post("/material-batches/{batch_id}/split", response_model=list[MaterialBatchChildResponse])
async def split_material_batch(
    batch_id: int,
    data: BatchSplitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[MaterialBatchChildResponse]:
    """Split a material batch into child batches."""
    require_role(current_user, min_level=3)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    splits = [s.model_dump() for s in data.splits]

    try:
        children = await material_batch_service.split_batch(
            db, batch, splits, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return [
        MaterialBatchChildResponse(
            id=c.id,
            child_batch_no=c.child_batch_no,
            child_qr_code=c.child_qr_code,
            width=c.width,
            length=c.length,
            current_weight=c.current_weight,
            status=c.status,
            created_at=c.created_at,
        )
        for c in children
    ]


@router.post("/material-batches/{batch_id}/consume", response_model=MaterialBatchResponse)
async def consume_material(
    batch_id: int,
    data: BatchConsumeRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Consume material from a batch (called during production)."""
    require_role(current_user, min_level=1)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    try:
        batch = await material_batch_service.consume_material(
            db,
            batch,
            weight=data.weight,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            operator_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _batch_to_response(batch)


@router.post("/material-batches/{batch_id}/scrap", response_model=MaterialBatchResponse)
async def scrap_material_batch(
    batch_id: int,
    data: BatchScrapRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Scrap a material batch."""
    require_role(current_user, min_level=3)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    try:
        batch = await material_batch_service.scrap_batch(
            db, batch, data.reason, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _batch_to_response(batch)


@router.get("/material-batches/{batch_id}/trace", response_model=BatchTraceResponse)
async def trace_material_batch(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> BatchTraceResponse:
    """Trace a material batch with all its transactions."""
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    transactions = await material_batch_service.get_batch_transactions(db, batch_id)

    return BatchTraceResponse(
        batch=_batch_detail_to_response(batch),
        transactions=[
            BatchTransactionResponse(
                id=t.id,
                batch_id=t.batch_id,
                batch_no=t.batch_no,
                transaction_type=t.transaction_type,
                quantity_change=t.quantity_change,
                weight_after=t.weight_after,
                reference_type=t.reference_type,
                reference_id=t.reference_id,
                operator_id=t.operator_id,
                notes=t.notes,
                created_at=t.created_at,
            )
            for t in transactions
        ],
    )


# Supplier endpoints

@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierResponse:
    """Create a new supplier."""
    require_role(current_user, min_level=5)

    supplier = await material_batch_service.create_supplier(
        db,
        name=data.name,
        contact_person=data.contact_person,
        contact_phone=data.contact_phone,
        address=data.address,
        notes=data.notes,
    )

    return SupplierResponse(
        id=supplier.id,
        supplier_no=supplier.supplier_no,
        name=supplier.name,
        contact_person=supplier.contact_person,
        contact_phone=supplier.contact_phone,
        address=supplier.address,
        notes=supplier.notes,
        is_active=supplier.is_active,
        created_at=supplier.created_at,
    )


@router.get("/suppliers", response_model=list[SupplierResponse])
async def list_suppliers(
    db: DbSession,
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[SupplierResponse]:
    """List suppliers."""
    suppliers = await material_batch_service.get_suppliers(
        db, is_active=is_active, skip=skip, limit=limit
    )

    return [
        SupplierResponse(
            id=s.id,
            supplier_no=s.supplier_no,
            name=s.name,
            contact_person=s.contact_person,
            contact_phone=s.contact_phone,
            address=s.address,
            notes=s.notes,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        for s in suppliers
    ]


# Material catalog endpoints

@router.post("/materials", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: MaterialCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialResponse:
    """Create a new material in the catalog."""
    require_role(current_user, min_level=4)

    material = await material_batch_service.create_material(
        db,
        name=data.name,
        grade=data.grade,
        thickness=data.thickness,
        width=data.width,
        weight_per_unit=data.weight_per_unit,
        unit=data.unit,
        supplier_id=data.supplier_id,
    )

    return MaterialResponse(
        id=material.id,
        material_no=material.material_no,
        name=material.name,
        grade=material.grade,
        thickness=material.thickness,
        width=material.width,
        weight_per_unit=material.weight_per_unit,
        unit=material.unit,
        supplier_id=material.supplier_id,
        supplier_name=material.supplier.name if material.supplier else None,
        is_active=material.is_active,
        created_at=material.created_at,
    )


@router.get("/materials", response_model=list[MaterialResponse])
async def list_materials(
    db: DbSession,
    current_user: CurrentUser,
    grade: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[MaterialResponse]:
    """List materials in the catalog."""
    materials = await material_batch_service.get_materials(
        db, grade=grade, skip=skip, limit=limit
    )

    return [
        MaterialResponse(
            id=m.id,
            material_no=m.material_no,
            name=m.name,
            grade=m.grade,
            thickness=m.thickness,
            width=m.width,
            weight_per_unit=m.weight_per_unit,
            unit=m.unit,
            supplier_id=m.supplier_id,
            supplier_name=m.supplier.name if m.supplier else None,
            is_active=m.is_active,
            created_at=m.created_at,
        )
        for m in materials
    ]
