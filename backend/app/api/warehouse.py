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
    QRScanLog,
    ScanOperation,
    ScanType,
    Supplier,
)
from app.schemas.warehouse import (
    BatchConsumeRequest,
    BatchScrapRequest,
    BatchSplitRequest,
    BatchTraceResponse,
    BatchTransactionResponse,
    IQCUpdate,
    MaterialBatchChildScanResponse,
    MaterialBatchCreate,
    MaterialBatchDetailResponse,
    MaterialBatchResponse,
    MaterialBatchChildResponse,
    MaterialBatchScanResponse,
    MaterialCreate,
    MaterialResponse,
    QRScanLogCreate,
    QRScanLogResponse,
    SupplierCreate,
    SupplierResponse,
)
from app.services import material_batch_service

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


def _batch_to_response(batch: MaterialBatch) -> MaterialBatchResponse:
    """Convert MaterialBatch to response."""
    return MaterialBatchResponse(
        id=batch.id,
        batch_no=batch.batch_no or batch.qr_uid,
        qr_code=batch.qr_code,
        material_id=batch.material_id or 0,
        supplier_id=batch.supplier_id,
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        gross_weight=batch.gross_weight or 0,
        net_weight=batch.net_weight,
        current_weight=batch.current_weight or 0,
        status=batch.status or BatchStatus.PENDING_IQC,
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
        batch_no=batch.batch_no or batch.qr_uid or "",
        qr_code=batch.qr_code,
        material_id=batch.material_id or 0,
        material_name=batch.material.name if batch.material else (batch.material_name or ""),
        material_grade=batch.material.grade if batch.material else None,
        supplier_id=batch.supplier_id,
        supplier_name=batch.supplier.name if batch.supplier else (batch.supplier_name or ""),
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        gross_weight=batch.gross_weight or 0,
        net_weight=batch.net_weight,
        current_weight=batch.current_weight or 0,
        status=batch.status or BatchStatus.PENDING_IQC,
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
    """Create a new material batch (register incoming material). Requires LV2 (warehouse manager)."""
    require_role(current_user, min_level=2)

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
    """Perform IQC inspection on a material batch. Requires LV2 (quality supervisor)."""
    require_role(current_user, min_level=2)

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


@router.post("/material-batches/{batch_id}/split", response_model=list[MaterialBatchScanResponse])
async def split_material_batch(
    batch_id: int,
    data: BatchSplitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[MaterialBatchScanResponse]:
    """Split a material batch into child batches (each with unique QR code).

    T015: 扫码母卷后执行分条，返回各子卷的 qr_code 供打印标签。
    Requires LV2 (warehouse manager).
    """
    require_role(current_user, min_level=2)

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

    # 记录分条扫码日志
    await material_batch_service.create_scan_log(
        db,
        scan_type=ScanType.MAT,
        entity_id=batch.id,
        entity_no=batch.batch_no,
        operation=ScanOperation.SPLIT,
        operator_id=current_user.id,
        notes=f"Split into {len(children)} child batches",
    )

    return [
        MaterialBatchScanResponse(
            id=c.id,
            batch_no=c.batch_no,
            qr_code=c.qr_code,
            qr_image_base64=generate_material_batch_qr_base64(c.id) if c.qr_code else None,
            material_id=c.material_id,
            material_name=c.material.name if c.material else None,
            material_grade=c.material.grade if c.material else None,
            supplier_name=c.supplier.name if c.supplier else None,
            thickness=c.thickness,
            width=c.width,
            length=c.length,
            gross_weight=c.gross_weight,
            current_weight=c.current_weight,
            status=c.status,
            iqc_result=None,
            iqc_time=None,
            received_at=c.received_at,
            created_at=c.created_at,
            parent_batch_id=batch.id,
            parent_batch_no=batch.batch_no,
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
    """Scrap a material batch. Requires LV3 (boss approval for material write-off)."""
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


# ── QR Scan Endpoints ────────────────────────────────────────────────────────

@router.get("/material-batches/scan/{batch_id}", response_model=MaterialBatchScanResponse)
async def scan_material_batch(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchScanResponse:
    """Scan material batch QR code, record scan log, return full ledger info.

    T012: 扫码原料二维码，记录扫码日志，返回完整台账。
    """
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    await material_batch_service.create_scan_log(
        db,
        scan_type=ScanType.MAT,
        entity_id=batch.id,
        entity_no=batch.batch_no,
        operation=ScanOperation.QUERY,
        operator_id=current_user.id,
    )

    parent_batch_no = None
    if batch.parent_batch_id:
        parent = await material_batch_service.get_batch_by_id(db, batch.parent_batch_id)
        if parent:
            parent_batch_no = parent.batch_no

    return MaterialBatchScanResponse(
        id=batch.id,
        batch_no=batch.batch_no,
        qr_code=batch.qr_code,
        qr_image_base64=generate_material_batch_qr_base64(batch.id) if batch.qr_code else None,
        material_id=batch.material_id,
        material_name=batch.material.name if batch.material else None,
        material_grade=batch.material.grade if batch.material else None,
        supplier_name=batch.supplier.name if batch.supplier else None,
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        gross_weight=batch.gross_weight,
        current_weight=batch.current_weight,
        status=batch.status,
        iqc_result=batch.iqc_result,
        iqc_time=batch.iqc_time,
        received_at=batch.received_at,
        created_at=batch.created_at,
        parent_batch_id=batch.parent_batch_id,
        parent_batch_no=parent_batch_no,
    )


@router.get("/material-batches/scan/child/{child_id}", response_model=MaterialBatchChildScanResponse)
async def scan_child_batch(
    child_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchChildScanResponse:
    """Scan child batch QR code: child info + parent info + sibling list.

    T016: 扫码子卷，返回子卷台账 + 母卷完整信息 + 同胞子卷列表。
    """
    child = await material_batch_service.get_child_batch_by_id(db, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child batch not found")

    await material_batch_service.create_scan_log(
        db,
        scan_type=ScanType.MAT,
        entity_id=child.id,
        entity_no=child.batch_no,
        operation=ScanOperation.QUERY,
        operator_id=current_user.id,
    )

    parent = child.parent_batch
    siblings: list[MaterialBatchScanResponse] = []
    parent_response = None

    if parent:
        parent_response = MaterialBatchScanResponse(
            id=parent.id,
            batch_no=parent.batch_no,
            qr_code=parent.qr_code,
            qr_image_base64=generate_material_batch_qr_base64(parent.id) if parent.qr_code else None,
            material_id=parent.material_id,
            material_name=parent.material.name if parent.material else None,
            material_grade=parent.material.grade if parent.material else None,
            supplier_name=parent.supplier.name if parent.supplier else None,
            thickness=parent.thickness,
            width=parent.width,
            length=parent.length,
            gross_weight=parent.gross_weight,
            current_weight=parent.current_weight,
            status=parent.status,
            iqc_result=parent.iqc_result,
            iqc_time=parent.iqc_time,
            received_at=parent.received_at,
            created_at=parent.created_at,
            parent_batch_id=None,
            parent_batch_no=None,
        )
        sibling_rows = await material_batch_service.get_sibling_batches(
            db, parent_batch_id=parent.id, exclude_id=child.id
        )
        for sib in sibling_rows:
            siblings.append(
                MaterialBatchScanResponse(
                    id=sib.id,
                    batch_no=sib.batch_no,
                    qr_code=sib.qr_code,
                    qr_image_base64=generate_material_batch_qr_base64(sib.id) if sib.qr_code else None,
                    material_id=sib.material_id,
                    material_name=sib.material.name if sib.material else None,
                    material_grade=sib.material.grade if sib.material else None,
                    supplier_name=sib.supplier.name if sib.supplier else None,
                    thickness=sib.thickness,
                    width=sib.width,
                    length=sib.length,
                    gross_weight=sib.gross_weight,
                    current_weight=sib.current_weight,
                    status=sib.status,
                    iqc_result=sib.iqc_result,
                    iqc_time=sib.iqc_time,
                    received_at=sib.received_at,
                    created_at=sib.created_at,
                    parent_batch_id=sib.parent_batch_id,
                    parent_batch_no=None,
                )
            )

    child_response = MaterialBatchScanResponse(
        id=child.id,
        batch_no=child.batch_no,
        qr_code=child.qr_code,
        qr_image_base64=generate_material_batch_qr_base64(child.id) if child.qr_code else None,
        material_id=child.material_id,
        material_name=child.material.name if child.material else None,
        material_grade=child.material.grade if child.material else None,
        supplier_name=child.supplier.name if child.supplier else None,
        thickness=child.thickness,
        width=child.width,
        length=child.length,
        gross_weight=child.gross_weight,
        current_weight=child.current_weight,
        status=child.status,
        iqc_result=child.iqc_result,
        iqc_time=child.iqc_time,
        received_at=child.received_at,
        created_at=child.created_at,
        parent_batch_id=child.parent_batch_id,
        parent_batch_no=parent.batch_no if parent else None,
    )

    return MaterialBatchChildScanResponse(
        child_batch=child_response,
        parent_batch=parent_response,
        sibling_batches=siblings,
    )


@router.get("/material-batches/{batch_id}/children", response_model=list[MaterialBatchScanResponse])
async def list_child_batches(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[MaterialBatchScanResponse]:
    """List all child batches of a parent batch.

    T017: 扫码母卷，返回所有子卷列表（含状态）。
    """
    parent = await material_batch_service.get_parent_batch(db, batch_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Material batch not found")

    await material_batch_service.create_scan_log(
        db,
        scan_type=ScanType.MAT,
        entity_id=parent.id,
        entity_no=parent.batch_no,
        operation=ScanOperation.QUERY,
        operator_id=current_user.id,
    )

    result = await db.execute(
        select(MaterialBatchChild)
        .where(MaterialBatchChild.parent_batch_id == batch_id)
        .order_by(MaterialBatchChild.created_at)
    )
    children = result.scalars().all()

    responses: list[MaterialBatchScanResponse] = []
    for c in children:
        child_batch = await material_batch_service.get_batch_by_id(db, c.id)
        if child_batch:
            responses.append(
                MaterialBatchScanResponse(
                    id=c.id,
                    batch_no=c.child_batch_no,
                    qr_code=c.child_qr_code,
                    qr_image_base64=None,
                    material_id=child_batch.material_id,
                    material_name=child_batch.material.name if child_batch.material else None,
                    material_grade=child_batch.material.grade if child_batch.material else None,
                    supplier_name=child_batch.supplier.name if child_batch.supplier else None,
                    thickness=child_batch.thickness,
                    width=c.width,
                    length=c.length,
                    gross_weight=c.current_weight,
                    current_weight=c.current_weight,
                    status=c.status,
                    iqc_result=None,
                    iqc_time=None,
                    received_at=None,
                    created_at=c.created_at,
                    parent_batch_id=batch_id,
                    parent_batch_no=parent.batch_no,
                )
            )
    return responses


# Supplier endpoints

@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierResponse:
    """Create a new supplier - LV2: warehouse/business staff."""
    require_role(current_user, min_level=2)

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
    require_role(current_user, min_level=2)

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


# ── QR Scan Log ─────────────────────────────────────────────────────────────

@router.post("/scans", response_model=QRScanLogResponse, status_code=status.HTTP_201_CREATED)
async def create_scan_log(
    data: QRScanLogCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> QRScanLogResponse:
    """Record a QR code scan event."""
    log = await material_batch_service.create_scan_log(
        db,
        scan_type=data.scan_type,
        entity_id=data.entity_id,
        entity_no=data.entity_no,
        operation=data.operation,
        operator_id=current_user.id,
        notes=data.notes,
    )
    return QRScanLogResponse(
        id=log.id,
        scan_type=log.scan_type,
        entity_id=log.entity_id,
        entity_no=log.entity_no,
        operator_id=log.operator_id,
        operation=log.operation,
        notes=log.notes,
        scanned_at=log.scanned_at,
    )


@router.get("/scans/{entity_type}/{entity_id}", response_model=list[QRScanLogResponse])
async def get_scan_logs(
    entity_type: str,
    entity_id: int,
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[QRScanLogResponse]:
    """Get scan history for a specific entity."""
    logs = await material_batch_service.get_scan_logs_by_entity(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        skip=skip,
        limit=limit,
    )
    return [
        QRScanLogResponse(
            id=log.id,
            scan_type=log.scan_type,
            entity_id=log.entity_id,
            entity_no=log.entity_no,
            operator_id=log.operator_id,
            operation=log.operation,
            notes=log.notes,
            scanned_at=log.scanned_at,
        )
        for log in logs
    ]


# ── T026: Reprint QR ────────────────────────────────────────────────────────

@router.post("/material-batches/{batch_id}/reprint-qr", response_model=MaterialBatchScanResponse)
async def reprint_material_batch_qr(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchScanResponse:
    """Reprint QR code for a material batch.

    Returns the batch info with qr_content and qr_image_base64.
    Records the reprint operation in qr_scan_logs.
    """
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if not batch.qr_code:
        raise HTTPException(status_code=400, detail="Batch has no QR code")

    from app.services.qr_service import generate_qr_base64
    qr_image_base64 = generate_qr_base64(batch.qr_code)

    # Record reprint scan log
    await material_batch_service.create_scan_log(
        db,
        scan_type="MAT",
        entity_id=batch.id,
        entity_no=batch.batch_no,
        operation="reprint",
        operator_id=current_user.id,
        notes="QR code reprint",
    )
    await db.commit()

    return MaterialBatchScanResponse(
        id=batch.id,
        batch_no=batch.batch_no,
        qr_code=batch.qr_code,
        qr_image_base64=qr_image_base64,
        material_name=batch.material.name if batch.material else None,
        material_grade=batch.material.grade if batch.material else None,
        supplier_name=batch.supplier.name if batch.supplier else None,
        status=batch.status.value if batch.status else None,
        lifecycle_status=batch.lifecycle_status.value if batch.lifecycle_status else None,
        gross_weight=batch.gross_weight,
        current_weight=batch.current_weight,
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        received_at=batch.received_at,
        iqc_result=batch.iqc_result.value if batch.iqc_result else None,
    )
