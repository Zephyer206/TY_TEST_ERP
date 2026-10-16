"""Customer inquiry intake and technical review endpoints."""

from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession, require_role
from app.core.file_service import get_inquiry_attachment_path, get_upload_root
from app.models.customer import Customer
from app.models.customer_inquiry import CustomerInquiry, CustomerInquiryAttachment

router = APIRouter(prefix="/customer-inquiries", tags=["Customer Inquiries"])
MAX_FILES = 10
MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_TOTAL_SIZE = 200 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


class InquiryAttachmentResponse(BaseModel):
    id: int
    name: str
    size: int
    status: str = "ready"
    url: str
    content_type: Optional[str] = None


class CustomerInquiryResponse(BaseModel):
    id: int
    inquiry_no: str
    customer_id: int
    customer: str
    project_name: str
    due_date: Optional[date] = None
    status: str
    technical_review: str
    technical_review_note: Optional[str] = None
    technical_data: list[dict] = Field(default_factory=list)
    owner_name: str
    received_at: datetime
    created_at: datetime
    attachments: list[InquiryAttachmentResponse] = Field(default_factory=list)


class TechnicalReviewInput(BaseModel):
    status: str = Field(pattern=r"^(待补充|已完成)$")
    note: Optional[str] = Field(default=None, max_length=4000)
    technical_data: list[dict] = Field(default_factory=list, max_length=100)


def _as_response(
    inquiry: CustomerInquiry,
    customer: Customer,
    attachments: list[CustomerInquiryAttachment],
) -> CustomerInquiryResponse:
    return CustomerInquiryResponse(
        id=inquiry.id,
        inquiry_no=inquiry.inquiry_no,
        customer_id=inquiry.customer_id,
        customer=customer.name,
        project_name=inquiry.project_name,
        due_date=inquiry.due_date,
        status=inquiry.status,
        technical_review=inquiry.technical_review,
        technical_review_note=inquiry.technical_review_note,
        technical_data=inquiry.technical_data or [],
        owner_name=inquiry.owner_name,
        received_at=inquiry.created_at,
        created_at=inquiry.created_at,
        attachments=[
            InquiryAttachmentResponse(
                id=attachment.id,
                name=attachment.original_name,
                size=attachment.file_size,
                status="ready",
                url=f"/uploads/{quote(attachment.relative_path, safe='/')}",
                content_type=attachment.content_type,
            )
            for attachment in attachments
        ],
    )


async def _load_response(db: DbSession, inquiry: CustomerInquiry) -> CustomerInquiryResponse:
    customer = await db.get(Customer, inquiry.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer for inquiry not found")
    attachments = (
        await db.execute(
            select(CustomerInquiryAttachment)
            .where(CustomerInquiryAttachment.inquiry_id == inquiry.id)
            .order_by(CustomerInquiryAttachment.id)
        )
    ).scalars().all()
    return _as_response(inquiry, customer, attachments)


@router.get("", response_model=list[CustomerInquiryResponse])
async def list_customer_inquiries(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None, max_length=100),
    technical_review: Optional[str] = Query(default=None, max_length=40),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[CustomerInquiryResponse]:
    query = select(CustomerInquiry, Customer).join(
        Customer, Customer.id == CustomerInquiry.customer_id
    )
    if technical_review:
        query = query.where(CustomerInquiry.technical_review == technical_review)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                CustomerInquiry.inquiry_no.ilike(term),
                CustomerInquiry.project_name.ilike(term),
                Customer.name.ilike(term),
            )
        )
    rows = (
        await db.execute(
            query.order_by(CustomerInquiry.created_at.desc(), CustomerInquiry.id.desc())
            .offset(skip)
            .limit(limit)
        )
    ).all()
    inquiry_ids = [inquiry.id for inquiry, _customer in rows]
    attachments_by_inquiry: dict[int, list[CustomerInquiryAttachment]] = {
        inquiry_id: [] for inquiry_id in inquiry_ids
    }
    if inquiry_ids:
        attachments = (
            await db.execute(
                select(CustomerInquiryAttachment)
                .where(CustomerInquiryAttachment.inquiry_id.in_(inquiry_ids))
                .order_by(CustomerInquiryAttachment.id)
            )
        ).scalars().all()
        for attachment in attachments:
            attachments_by_inquiry[attachment.inquiry_id].append(attachment)
    return [
        _as_response(inquiry, customer, attachments_by_inquiry[inquiry.id])
        for inquiry, customer in rows
    ]


@router.get("/{inquiry_id}", response_model=CustomerInquiryResponse)
async def get_customer_inquiry(
    inquiry_id: int, db: DbSession, current_user: CurrentUser
) -> CustomerInquiryResponse:
    inquiry = await db.get(CustomerInquiry, inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=404, detail="Customer inquiry not found")
    return await _load_response(db, inquiry)


@router.post("", response_model=CustomerInquiryResponse, status_code=status.HTTP_201_CREATED)
async def create_customer_inquiry(
    db: DbSession,
    current_user: CurrentUser,
    customer_id: int = Form(...),
    project_name: Optional[str] = Form(default=None, max_length=255),
    due_date: Optional[date] = Form(default=None),
    technical_review_note: Optional[str] = Form(default=None, max_length=4000),
    files: list[UploadFile] = File(...),
) -> CustomerInquiryResponse:
    require_role(current_user, min_level=2)
    if not files or len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Please upload between 1 and {MAX_FILES} files")
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    clean_project_name = (project_name or "").strip() or "待命名项目"
    inquiry = CustomerInquiry(
        inquiry_no=f"RFQ-PENDING-{uuid4().hex[:12].upper()}",
        customer_id=customer.id,
        project_name=clean_project_name,
        due_date=due_date,
        status="报价中",
        technical_review="待评审",
        technical_review_note=(technical_review_note or "").strip() or None,
        owner_name=(current_user.real_name or "").strip() or "待分配",
        created_by=current_user.id,
    )
    db.add(inquiry)
    stored_paths: list[Path] = []
    total_size = 0
    try:
        await db.flush()
        inquiry.inquiry_no = f"RFQ-{datetime.utcnow():%Y%m%d}-{inquiry.id:06d}"
        await db.flush()
        for upload in files:
            original_name = Path(upload.filename or "unnamed").name.strip()[:255] or "unnamed"
            target, relative_path = get_inquiry_attachment_path(inquiry.id, original_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            stored_paths.append(target)
            file_size = 0
            async with aiofiles.open(target, "wb") as output:
                while chunk := await upload.read(CHUNK_SIZE):
                    file_size += len(chunk)
                    total_size += len(chunk)
                    if file_size > MAX_FILE_SIZE or total_size > MAX_TOTAL_SIZE:
                        raise HTTPException(
                            status_code=413, detail="Uploaded files exceed the allowed size"
                        )
                    await output.write(chunk)
            db.add(
                CustomerInquiryAttachment(
                    inquiry_id=inquiry.id,
                    original_name=original_name,
                    stored_name=target.name,
                    relative_path=relative_path,
                    content_type=upload.content_type,
                    file_size=file_size,
                )
            )
        await db.commit()
        await db.refresh(inquiry)
    except Exception:
        await db.rollback()
        for path in stored_paths:
            path.unlink(missing_ok=True)
        inquiry_dir = get_upload_root() / "inquiries" / str(inquiry.id)
        if inquiry_dir.exists():
            try:
                inquiry_dir.rmdir()
            except OSError:
                pass
        raise
    return await _load_response(db, inquiry)


@router.post(
    "/{inquiry_id}/technical-review", response_model=CustomerInquiryResponse
)
async def review_customer_inquiry(
    inquiry_id: int,
    data: TechnicalReviewInput,
    db: DbSession,
    current_user: CurrentUser,
) -> CustomerInquiryResponse:
    require_role(current_user, min_level=2)
    inquiry = await db.get(CustomerInquiry, inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=404, detail="Customer inquiry not found")
    inquiry.technical_review = data.status
    inquiry.technical_data = data.technical_data
    if data.note is not None:
        inquiry.technical_review_note = data.note.strip() or None
    inquiry.updated_at = datetime.utcnow()
    if data.status == "已完成":
        from app.api.quote_groups import ensure_quote_group

        await ensure_quote_group(db, inquiry, current_user.id)
    # Keep the review update and any automatically-created quote group in one
    # transaction. The request-scoped DB dependency rolls the whole unit back
    # if quote-group creation or validation fails.
    await db.commit()
    await db.refresh(inquiry)
    return await _load_response(db, inquiry)
