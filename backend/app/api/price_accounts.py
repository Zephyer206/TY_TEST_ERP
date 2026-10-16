"""Price account API endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.price import PriceAccount
from app.models.user import User
from app.schemas.price import (
    AnnualPriceRecordCreate,
    AnnualPriceRecordResponse,
    CurrentPriceResponse,
    PriceAccountCreate,
    PriceAccountListResponse,
    PriceAccountResponse,
    PriceAccountUpdate,
    PriceAccountAdjustmentCreate,
    PriceAccountAdjustmentResponse,
)
from app.services import price_service

router = APIRouter(prefix="/price-accounts", tags=["Price Accounts"])


def _account_to_response(account: PriceAccount) -> PriceAccountResponse:
    """Convert PriceAccount to response."""
    return PriceAccountResponse(
        id=account.id,
        part_id=account.part_id,
        customer_id=account.customer_id,
        material=account.material,
        net_weight_kg=account.net_weight_kg,
        gross_weight_kg=account.gross_weight_kg,
        material_unit_price=account.material_unit_price,
        scrap_price=account.scrap_price,
        reduction_pct=account.reduction_pct,
        notes=account.notes,
        base_price=account.base_price,
        current_price=account.current_price,
        price_year=account.price_year,
        is_active=account.is_active,
        annual_records=[
            AnnualPriceRecordResponse(
                id=r.id,
                price_account_id=r.price_id,
                year=r.year,
                unit_price=r.unit_price,
                annual_qty=r.annual_sales,
                notes=None,
                created_by=r.operator_id,
                creator_name=None,
                created_at=r.updated_at,
            )
            for r in (account.annual_records or [])
        ],
        # Adjustment history belongs to the approval workflow and is exposed
        # by /price-adjustments.  The legacy account response no longer reads
        # a non-existent ``price_accounts.adjustments`` relationship.
        adjustments=[],
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@router.post("", response_model=PriceAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_price_account(
    data: PriceAccountCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PriceAccountResponse:
    """Create a new price account - LV2: business staff."""
    require_role(current_user, min_level=2)

    existing = await price_service.get_price_account_by_part_customer(
        db, data.part_id, data.customer_id
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Price account already exists for this part and customer",
        )

    account = await price_service.create_price_account(
        db,
        part_id=data.part_id,
        customer_id=data.customer_id,
        material=data.material,
        net_weight_kg=data.net_weight_kg,
        gross_weight_kg=data.gross_weight_kg,
        material_unit_price=data.material_unit_price,
        scrap_price=data.scrap_price,
        reduction_pct=data.reduction_pct,
        notes=data.notes,
    )
    return _account_to_response(account)


@router.get("/{account_id}", response_model=PriceAccountResponse)
async def get_price_account(
    account_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PriceAccountResponse:
    """Get price account by ID."""
    account = await price_service.get_price_account_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Price account not found")
    return _account_to_response(account)


@router.get("/part/{part_id}", response_model=list[PriceAccountListResponse])
async def get_price_accounts_by_part(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[PriceAccountListResponse]:
    """Get all price accounts for a part."""
    accounts = await price_service.get_price_accounts_by_part(db, part_id)
    return [
        PriceAccountListResponse(
            id=a.id,
            part_id=a.part_id,
            # The canonical Part model no longer exposes the retired
            # ``part_no`` column; customer aliases are queried separately.
            part_no=None,
            part_name=a.part.internal_name if a.part else None,
            customer_id=a.customer_id,
            customer_name=a.customer.name if a.customer else None,
            current_price=a.current_price,
            price_year=a.price_year,
            reduction_pct=a.reduction_pct,
            is_active=a.is_active,
            created_at=a.created_at,
        )
        for a in accounts
    ]


@router.patch("/{account_id}", response_model=PriceAccountResponse)
async def update_price_account(
    account_id: int,
    data: PriceAccountUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> PriceAccountResponse:
    """Update price account fields - LV2: business staff."""
    require_role(current_user, min_level=2)

    account = await price_service.get_price_account_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Price account not found")

    account = await price_service.update_price_account(
        db, account, **data.model_dump(exclude_unset=True)
    )
    return _account_to_response(account)


@router.post("/{account_id}/annual-price", response_model=AnnualPriceRecordResponse, status_code=status.HTTP_201_CREATED)
async def add_annual_price(
    account_id: int,
    data: AnnualPriceRecordCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AnnualPriceRecordResponse:
    """Add annual price record - LV2: business staff."""
    require_role(current_user, min_level=2)

    account = await price_service.get_price_account_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Price account not found")

    record = await price_service.add_annual_price_record(
        db,
        account_id=account_id,
        year=data.year,
        unit_price=data.unit_price,
        annual_qty=data.annual_qty,
        notes=data.notes,
        created_by=current_user,
    )

    return AnnualPriceRecordResponse(
        id=record.id,
        price_account_id=record.price_account_id,
        year=record.year,
        unit_price=record.unit_price,
        annual_qty=record.annual_qty,
        notes=record.notes,
        created_by=record.created_by,
        creator_name=current_user.full_name,
        created_at=record.created_at,
    )


@router.get("/{account_id}/current-price", response_model=CurrentPriceResponse)
async def get_current_price(
    account_id: int,
    db: DbSession,
    current_user: CurrentUser,
    year: Optional[int] = Query(default=None),
) -> CurrentPriceResponse:
    """Get computed current price (from record or formula)."""
    account = await price_service.get_price_account_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Price account not found")

    current_year = year or datetime.utcnow().year
    price, price_year = price_service.compute_current_price_from_records(
        account, current_year
    )

    if price is None:
        raise HTTPException(status_code=400, detail="No price available")

    is_computed = True
    formula = None

    if account.annual_records:
        latest_record = max(
            [r for r in account.annual_records if r.year <= current_year],
            key=lambda r: r.year,
            default=None,
        )
        if latest_record and latest_record.year == price_year:
            is_computed = False
            formula = f"From annual record {price_year}"

    if is_computed and account.base_price:
        formula = (
            f"base_price × (1 - {account.reduction_pct})^"
            f"({current_year} - {account.price_year or current_year})"
        )

    return CurrentPriceResponse(
        price=price,
        year=price_year or current_year,
        is_computed=is_computed,
        formula=formula,
    )


@router.post("/{account_id}/adjustments", response_model=PriceAccountAdjustmentResponse, status_code=status.HTTP_201_CREATED)
async def create_price_adjustment(
    account_id: int,
    data: PriceAccountAdjustmentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PriceAccountAdjustmentResponse:
    """Record a manual price adjustment - LV2: business staff."""
    require_role(current_user, min_level=2)

    account = await price_service.get_price_account_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Price account not found")

    old_price = account.current_price or Decimal("0")
    adjustment = await price_service.record_price_adjustment(
        db,
        account_id=account_id,
        old_price=old_price,
        new_price=data.new_price,
        adjustment_type=data.adjustment_type,
        reason=data.reason,
        created_by=current_user,
    )

    return PriceAccountAdjustmentResponse(
        id=adjustment.id,
        price_account_id=adjustment.price_account_id,
        old_price=adjustment.old_price,
        new_price=adjustment.new_price,
        adjustment_type=adjustment.adjustment_type,
        reason=adjustment.reason,
        created_by=adjustment.created_by,
        creator_name=current_user.full_name,
        created_at=adjustment.created_at,
    )
