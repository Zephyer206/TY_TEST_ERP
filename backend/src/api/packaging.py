"""Packaging management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.packaging import PackagingStatus
from app.schemas.packaging import (
    InventoryAdjustRequest,
    InventoryResponse,
    PackagingInspectRequest,
    PackagingRecordListResponse,
    PackagingRecordResponse,
    PackagingScanRequest,
    TransactionResponse,
)
from app.services import packaging_service

router = APIRouter(prefix="/packaging", tags=["Packaging"])


@router.post("/scan", response_model=PackagingRecordResponse, status_code=status.HTTP_201_CREATED)
async def scan_packaging(
    data: PackagingScanRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PackagingRecordResponse:
    """Scan packaging and create a record (requires role_level >= 1)."""
    require_role(current_user, min_level=1)

    try:
        record = await packaging_service.create_packaging_record(
            db, data.model_dump(), current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _record_to_response(record)


@router.post("/inspect", response_model=PackagingRecordResponse)
async def inspect_packaging(
    data: PackagingInspectRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PackagingRecordResponse:
    """Process visual inspection and update stock (requires role_level >= 2)."""
    require_role(current_user, min_level=2)

    record = await packaging_service.get_record_by_id(db, data.record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Packaging record not found")

    try:
        record = await packaging_service.process_inspection(
            db,
            record,
            inspected_qty=data.inspected_qty,
            passed_qty=data.passed_qty,
            rejected_qty=data.rejected_qty,
            visual_result=data.visual_result.value if data.visual_result else None,
            notes=data.inspection_notes,
            warehouse_location=data.warehouse_location,
            shelf_location=data.shelf_location,
            inspector=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _record_to_response(record)


@router.get("/records", response_model=list[PackagingRecordListResponse])
async def list_packaging_records(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    status: Optional[PackagingStatus] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PackagingRecordListResponse]:
    """List packaging records."""
    records = await packaging_service.get_records(
        db, part_id=part_id, status=status, skip=skip, limit=limit
    )

    return [
        PackagingRecordListResponse(
            id=r.id,
            record_no=r.record_no,
            part_id=r.part_id,
            part_no=r.part.part_no if r.part else None,
            part_name=r.part.part_name if r.part else None,
            quantity=r.quantity,
            box_barcode=r.box_barcode,
            status=r.status,
            warehouse_location=r.warehouse_location,
            scanned_at=r.scanned_at,
        )
        for r in records
    ]


@router.get("/records/{record_id}", response_model=PackagingRecordResponse)
async def get_packaging_record(
    record_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PackagingRecordResponse:
    """Get packaging record by ID."""
    record = await packaging_service.get_record_by_id(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Packaging record not found")

    return _record_to_response(record)


@router.get("/records/barcode/{box_barcode}", response_model=PackagingRecordResponse)
async def get_record_by_barcode(
    box_barcode: str,
    db: DbSession,
    current_user: CurrentUser,
) -> PackagingRecordResponse:
    """Get packaging record by box barcode."""
    record = await packaging_service.get_record_by_barcode(db, box_barcode)
    if not record:
        raise HTTPException(status_code=404, detail="Packaging record not found")

    return _record_to_response(record)


# Inventory Endpoints

@router.get("/inventory", response_model=list[InventoryResponse])
async def list_inventory(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    warehouse_location: Optional[str] = Query(default=None),
) -> list[InventoryResponse]:
    """List finished goods inventory."""
    inventory = await packaging_service.get_inventory(
        db, part_id=part_id, warehouse_location=warehouse_location
    )

    return [
        InventoryResponse(
            id=i.id,
            part_id=i.part_id,
            part_no=i.part.part_no if i.part else None,
            part_name=i.part.part_name if i.part else None,
            warehouse_location=i.warehouse_location,
            shelf_location=i.shelf_location,
            quantity=i.quantity,
            latest_batch_no=i.latest_batch_no,
            latest_production_date=i.latest_production_date,
            updated_at=i.updated_at,
        )
        for i in inventory
    ]


@router.post("/inventory/adjust", response_model=InventoryResponse)
async def adjust_inventory(
    data: InventoryAdjustRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> InventoryResponse:
    """Manually adjust inventory (requires role_level >= 3)."""
    require_role(current_user, min_level=3)

    try:
        inventory = await packaging_service.adjust_inventory(
            db,
            part_id=data.part_id,
            warehouse_location=data.warehouse_location,
            quantity_change=data.quantity_change,
            reason=data.reason,
            operator=current_user,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return InventoryResponse(
        id=inventory.id,
        part_id=inventory.part_id,
        part_no=inventory.part.part_no if inventory.part else None,
        part_name=inventory.part.part_name if inventory.part else None,
        warehouse_location=inventory.warehouse_location,
        shelf_location=inventory.shelf_location,
        quantity=inventory.quantity,
        latest_batch_no=inventory.latest_batch_no,
        latest_production_date=inventory.latest_production_date,
        updated_at=inventory.updated_at,
    )


@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    transaction_type: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[TransactionResponse]:
    """List inventory transactions."""
    transactions = await packaging_service.get_transactions(
        db, part_id=part_id, transaction_type=transaction_type, skip=skip, limit=limit
    )

    return [
        TransactionResponse(
            id=t.id,
            transaction_no=t.transaction_no,
            part_id=t.part_id,
            part_no=t.part.part_no if t.part else None,
            transaction_type=t.transaction_type,
            quantity_before=t.quantity_before,
            quantity_change=t.quantity_change,
            quantity_after=t.quantity_after,
            reference_type=t.reference_type,
            reference_id=t.reference_id,
            warehouse_location=t.warehouse_location,
            operated_by=t.operated_by,
            notes=t.notes,
            created_at=t.created_at,
        )
        for t in transactions
    ]


# Helper function

def _record_to_response(record) -> PackagingRecordResponse:
    """Convert PackagingRecord to response."""
    return PackagingRecordResponse(
        id=record.id,
        record_no=record.record_no,
        part_id=record.part_id,
        part_no=record.part.part_no if record.part else None,
        part_name=record.part.part_name if record.part else None,
        production_batch_no=record.production_batch_no,
        process_flow_no=record.process_flow_no,
        quantity=record.quantity,
        packaging_type=record.packaging_type,
        box_no=record.box_no,
        box_barcode=record.box_barcode,
        gross_weight=record.gross_weight,
        net_weight=record.net_weight,
        status=record.status,
        visual_inspection_result=record.visual_inspection_result,
        visual_inspection_by=record.visual_inspection_by,
        visual_inspection_at=record.visual_inspection_at,
        inspected_qty=record.inspected_qty,
        passed_qty=record.passed_qty,
        rejected_qty=record.rejected_qty,
        inspection_notes=record.inspection_notes,
        warehouse_location=record.warehouse_location,
        shelf_location=record.shelf_location,
        stock_qty=record.stock_qty,
        shipment_id=record.shipment_id,
        shipped_at=record.shipped_at,
        scanned_by=record.scanned_by,
        scanned_at=record.scanned_at,
        created_at=record.created_at,
    )
