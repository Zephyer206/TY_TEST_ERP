"""Authenticated product QR pool, print, one-time binding and capability APIs."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.api.deps import DbSession, security
from app.core.config import settings
from app.core.security import decode_token
from app.models.user import User
from app.schemas import product_box as schemas
from app.services import product_box_service as service, qr_print_service as printing, qr_permission_service as permissions
from app.services.qr_transaction_service import QrError
from app.services import product_order_service as orders, product_production_service as production
from app.services import product_process_service as processes
from app.services import product_split_service as splitting

router = APIRouter(tags=["product-box-qr"])


async def qr_error_handler(request: Request, error: QrError):
    return JSONResponse(status_code=error.status_code, content=error.body())


async def require_qr_user(db: DbSession,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]) -> User:
    if settings.AUTH_DISABLED:
        raise QrError(503, "STATE_CONFLICT", "二维码业务需要启用登录认证")
    invalid = HTTPException(401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(credentials.credentials) if credentials else None
    subject = payload.get("sub") if payload else None
    if (not payload or payload.get("type") != "access" or not isinstance(subject, str)
            or not 1 <= len(subject) <= 10 or not subject.isascii() or not subject.isdigit()
            or subject.startswith("0") or not 0 < int(subject) <= 2_147_483_647):
        raise invalid
    try:
        user = await db.scalar(select(User).where(User.id == int(subject)))
    except SQLAlchemyError:
        raise QrError(503, "STATE_CONFLICT", "二维码服务暂不可用，请稍后重试") from None
    if user is None:
        raise invalid
    return user


QrUser = Annotated[User, Depends(require_qr_user)]


async def run(db, operation, response_model):
    try:
        result = response_model.model_validate(await operation()).model_dump(mode="json")
        await db.commit()
        return result
    except QrError:
        await db.rollback()
        raise
    except DBAPIError as error:
        await db.rollback()
        code = getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)
        if code in {"23505", "23503", "23514", "40001", "40P01", "55P03"}:
            raise QrError(409, "STATE_CONFLICT", "关联数据发生冲突，请重新读取后确认") from None
        raise QrError(503, "STATE_CONFLICT", "二维码服务暂不可用，请稍后重试") from None
    except SQLAlchemyError:
        await db.rollback()
        raise QrError(503, "STATE_CONFLICT", "二维码服务暂不可用，请稍后重试") from None


@router.get("/product-qr-pool", response_model=schemas.PoolPage)
async def list_pool(db: DbSession, user: QrUser, pool_status: Literal["unused", "bound", "void"] | None = None,
                    print_batch_no: Annotated[str | None, Query(max_length=50)] = None,
                    page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=200)] = 50):
    return await run(db, lambda: service.list_pool(db, user, pool_status=pool_status,
        print_batch_no=print_batch_no, page=page, page_size=page_size), schemas.PoolPage)


@router.post("/product-qr-pool/batches", response_model=schemas.GeneratedBatch, status_code=201)
async def generate_batch(body: schemas.GenerateRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: service.generate_batch(db, user, **body.model_dump()), schemas.GeneratedBatch)


@router.post("/product-qr-pool/print-data", response_model=schemas.PrintJob, status_code=201)
async def print_data(body: schemas.PrintDataRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: printing.print_data(db, user, **body.model_dump()), schemas.PrintJob)


@router.post("/product-qr-pool/print-confirmations", response_model=schemas.PrintConfirmation)
async def confirm_print(body: schemas.PrintConfirmationRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: printing.confirm_print(db, user, **body.model_dump()), schemas.PrintConfirmation)


@router.post("/product-qr-pool/{item_id}/reprint", response_model=schemas.PrintJob, status_code=201)
async def reprint(item_id: schemas.NewId, body: schemas.ReprintRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: printing.reprint(db, user, item_id=item_id, **body.model_dump()), schemas.PrintJob)


@router.post("/product-boxes/bind", response_model=schemas.BoxScan, status_code=201)
async def bind_box(body: schemas.BindRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: service.bind_box(db, user, **body.model_dump()), schemas.BoxScan)


@router.post("/product-boxes/scan", response_model=schemas.BoxScan)
async def scan_box(body: schemas.ScanRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: service.scan_box(db, user, **body.model_dump()), schemas.BoxScan)


@router.patch("/product-boxes/{box_id}/metadata", response_model=schemas.ProductBox)
async def edit_metadata(box_id: schemas.NewId, body: schemas.MetadataRequest, db: DbSession, user: QrUser):
    changes = body.model_dump(exclude_unset=True, exclude={"expected_version", "idempotency_key"})
    return await run(db, lambda: service.edit_metadata(db, user, box_id=box_id, changes=changes,
        expected_version=body.expected_version, idempotency_key=body.idempotency_key), schemas.ProductBox)


@router.get("/production/plans/{order_id}/qr-context", response_model=schemas.OrderQrContext)
async def order_qr_context(order_id: Annotated[int, Path(ge=1, le=2_147_483_647)], db: DbSession, user: QrUser):
    return await run(db, lambda: service.order_qr_context(db, user, order_id=order_id), schemas.OrderQrContext)


@router.get("/qr-admin/capabilities", response_model=schemas.CapabilitiesPage)
async def list_capabilities(db: DbSession, user: QrUser,
        user_id: Annotated[int | None, Query(ge=1, le=2_147_483_647)] = None,
        page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=200)] = 50):
    return await run(db, lambda: permissions.list_capabilities(db, user, user_id=user_id,
        page=page, page_size=page_size), schemas.CapabilitiesPage)


@router.put("/production/plans/{order_id}/qr-context", response_model=schemas.OrderQrContext)
async def save_order_context(order_id: Annotated[int, Path(ge=1, le=2_147_483_647)], body: schemas.OrderQrContextRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: orders.save_order_qr_context(db, user, order_id=order_id,
        **body.model_dump(exclude_none=True)), schemas.OrderQrContext)


@router.post("/machines/scan-production", response_model=schemas.MachineScan)
async def scan_production(body: schemas.MachineScanRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: production.scan_machine(db, user, **body.model_dump()), schemas.MachineScan)


@router.post("/machines/production-contexts", response_model=schemas.ProductionSelection, status_code=201)
async def select_production(body: schemas.ProductionSelectRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: production.select_production(db, user, **body.model_dump()), schemas.ProductionSelection)


@router.post("/machines/{machine_id}/production-complete", response_model=schemas.ProductionSelection)
async def complete_production(machine_id: Annotated[int, Path(ge=1, le=2_147_483_647)], body: schemas.ProductionCompleteRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: production.complete_production(db, user, machine_id=machine_id, **body.model_dump()), schemas.ProductionSelection)


@router.post("/product-boxes/{box_id}/quantities", response_model=schemas.ProductionQuantityResult)
async def save_quantity(box_id: schemas.NewId, body: schemas.QuantityRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: production.save_quantity(db, user, box_id=box_id, **body.model_dump()), schemas.ProductionQuantityResult)


@router.post("/product-boxes/{box_id}/quantity-corrections", response_model=schemas.ProductionQuantityResult)
async def correct_quantity(box_id: schemas.NewId, body: schemas.CorrectionRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: production.correct_quantity(db, user, box_id=box_id, **body.model_dump()), schemas.ProductionQuantityResult)


@router.post("/production/output-allocations", response_model=schemas.OutputAllocation)
async def allocate_output(body: schemas.AllocationRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: production.allocate_output(db, user, **body.model_dump()), schemas.OutputAllocation)


@router.post("/product-boxes/{box_id}/advance", response_model=schemas.ProductionQuantityResult)
async def advance_process(box_id: schemas.NewId, body: schemas.AdvanceRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: processes.advance(db, user, box_id=box_id, **body.model_dump()), schemas.ProductionQuantityResult)


@router.get("/product-boxes/{box_id}/trace", response_model=schemas.BoxTrace)
async def trace_box(box_id: schemas.NewId, db: DbSession, user: QrUser,
        page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 50):
    return await run(db, lambda: processes.trace_box(db, user, box_id=box_id, page=page, page_size=page_size), schemas.BoxTrace)


@router.post("/product-boxes/{parent_id}/split", response_model=schemas.SplitResult, status_code=201)
async def split_box(parent_id: schemas.NewId, body: schemas.SplitRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: splitting.split_box(db, user, parent_id=parent_id, **body.model_dump()), schemas.SplitResult)


@router.get("/product-boxes/{box_id}/events", response_model=schemas.EventPage)
async def box_events(box_id: schemas.NewId, db: DbSession, user: QrUser,
        page_size: Annotated[int, Query(ge=1, le=100)] = 50, before_id: schemas.NewId | None = None):
    return await run(db, lambda: processes.events(db, user, box_id=box_id, page_size=page_size, before_id=before_id), schemas.EventPage)


@router.put("/qr-admin/capabilities/{user_id}", response_model=schemas.CapabilitiesResult)
async def save_capabilities(user_id: int, body: schemas.CapabilitiesRequest, db: DbSession, user: QrUser):
    return await run(db, lambda: permissions.replace_capabilities(db, user, user_id,
        body.capabilities, body.expected_version, body.idempotency_key), schemas.CapabilitiesResult)
