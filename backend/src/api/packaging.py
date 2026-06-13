"""Packaging management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.part import Part
from app.models.packaging import (
    Inventory,
    InventoryTransaction,
    PackagingRecord,
    PackagingStatus,
)
from app.schemas.packaging import (
    InventoryAdjustmentRequest,
    InventoryDetailResponse,
    InventoryResponse,
    InventoryTransactionResponse,
    PackagingInspectionRequest,
    PackagingRecordResponse,
    PackagingScanRequest,
)
from app.services import packaging_service

router = APIRouter(prefix="/packaging", tags=["Packaging"])


def _record_to_response(record: PackagingRecord) -> PackagingRecordResponse:
    """Convert PackagingRecord to response."""
    return PackagingRecordResponse(
        id=record.id,
        package_no=record.package_no,
        part_id=record.part_id,
        session_id=record.session_id,
        package_qty=record.package_qty,
        box_no=record.box_no,
        status=record.status,
        inspected_by=record.inspected_by,
        inspected_at=record.inspected_at,
        inspection_notes=record.inspection_notes,
        operator_id=record.operator_id,
        notes=record.notes,
        scanned_at=record.scanned_at,
        created_at=record.created_at,
    )


def _inventory_to_response(inventory: Inventory) -> InventoryResponse:
    """Convert Inventory to response."""
    return InventoryResponse(
        id=inventory.id,
        part_id=inventory.part_id,
        stock_qty=inventory.stock_qty,
        reserved_qty=inventory.reserved_qty,
        location=inventory.location,
        last_update_by=inventory.last_update_by,
        last_update_at=inventory.last_update_at,
        created_at=inventory.created_at,
    )


def _inventory_detail_to_response(inventory: Inventory) -> InventoryDetailResponse:
    """Convert Inventory to detail response."""
    return InventoryDetailResponse(
        id=inventory.id,
        part_id=inventory.part_id,
        part_no=inventory.part.part_number if inventory.part else None,
        part_name=inventory.part.internal_name if inventory.part else None,
        stock_qty=inventory.stock_qty,
        reserved_qty=inventory.reserved_qty,
        location=inventory.location,
        last_update_by=inventory.last_update_by,
        last_update_at=inventory.last_update_at,
        created_at=inventory.created_at,
    )


# Packaging endpoints

@router.post("/scan", response_model=PackagingRecordResponse, status_code=status.HTTP_201_CREATED)
async def scan_packaging(
    data: PackagingScanRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PackagingRecordResponse:
    """Scan packaging and create a packaging record.

    Used by packaging personnel to scan finished goods.
    """
    require_role(current_user, min_level=1)

    # Verify part exists
    result = await db.execute(select(Part).where(Part.id == data.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    record = await packaging_service.create_packaging_record(
        db,
        part_id=data.part_id,
        package_qty=data.package_qty,
        box_no=data.box_no,
        session_id=data.session_id,
        operator_id=current_user.id,
        notes=data.notes,
    )
    return _record_to_response(record)


@router.post("/inspect/{record_id}", response_model=PackagingRecordResponse)
async def inspect_packaging(
    record_id: int,
    data: PackagingInspectionRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PackagingRecordResponse:
    """Perform full inspection (全检) on packaging and update inventory if passed.

    Used by inspection personnel to verify packaged goods before stock-in.
    """
    require_role(current_user, min_level=3)

    record = await packaging_service.get_packaging_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Packaging record not found")

    try:
        record = await packaging_service.inspect_packaging(
            db, record, data.passed, current_user.id, data.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _record_to_response(record)


@router.get("/records", response_model=list[PackagingRecordResponse])
async def list_packaging_records(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    status_filter: Optional[PackagingStatus] = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PackagingRecordResponse]:
    """List packaging records."""
    records = await packaging_service.get_packaging_records(
        db, part_id=part_id, status=status_filter, skip=skip, limit=limit
    )
    return [_record_to_response(r) for r in records]


@router.get("/records/{record_id}", response_model=PackagingRecordResponse)
async def get_packaging_record(
    record_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PackagingRecordResponse:
    """Get a packaging record by ID."""
    record = await packaging_service.get_packaging_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Packaging record not found")
    return _record_to_response(record)


@router.get("/records/by-no/{package_no}", response_model=PackagingRecordResponse)
async def get_packaging_record_by_no(
    package_no: str,
    db: DbSession,
    current_user: CurrentUser,
) -> PackagingRecordResponse:
    """Get a packaging record by package number."""
    record = await packaging_service.get_packaging_record_by_no(db, package_no)
    if not record:
        raise HTTPException(status_code=404, detail="Packaging record not found")
    return _record_to_response(record)


# Inventory endpoints

@router.get("/inventory", response_model=list[InventoryDetailResponse])
async def list_inventory(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[InventoryDetailResponse]:
    """List finished goods inventory."""
    inventories = await packaging_service.get_inventories(
        db, part_id=part_id, skip=skip, limit=limit
    )
    return [_inventory_detail_to_response(i) for i in inventories]


@router.get("/inventory/{part_id}", response_model=InventoryDetailResponse)
async def get_inventory(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> InventoryDetailResponse:
    """Get inventory for a specific part."""
    inventory = await packaging_service.get_inventory(db, part_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return _inventory_detail_to_response(inventory)


@router.post("/inventory/{part_id}/adjust", response_model=InventoryResponse)
async def adjust_inventory(
    part_id: int,
    data: InventoryAdjustmentRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> InventoryResponse:
    """Manually adjust inventory quantity.

    Used by authorized personnel to correct inventory discrepancies.
    """
    require_role(current_user, min_level=3)

    # Verify part exists
    result = await db.execute(select(Part).where(Part.id == part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    try:
        inventory = await packaging_service.adjust_inventory(
            db, part_id, data.quantity, data.reason, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _inventory_to_response(inventory)


@router.get("/inventory/{part_id}/transactions", response_model=list[InventoryTransactionResponse])
async def list_inventory_transactions(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[InventoryTransactionResponse]:
    """Get inventory transaction history for a part."""
    transactions = await packaging_service.get_inventory_transactions(
        db, part_id, skip=skip, limit=limit
    )
    return [
        InventoryTransactionResponse(
            id=t.id,
            part_id=t.part_id,
            transaction_type=t.transaction_type,
            quantity=t.quantity,
            stock_before=t.stock_before,
            stock_after=t.stock_after,
            reference_type=t.reference_type,
            reference_id=t.reference_id,
            reason=t.reason,
            operator_id=t.operator_id,
            created_at=t.created_at,
        )
        for t in transactions
    ]
