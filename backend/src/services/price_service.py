"""Business logic for price account management and annual price reduction calculation."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.price import (
    AnnualPriceRecord,
    PriceAccount,
    PriceAdjustment,
    PriceAdjustmentType,
)
from src.models.user import User


def calculate_current_price(
    base_price: Decimal,
    reduction_pct: float,
    elapsed_years: int,
) -> Decimal:
    """Calculate current price based on annual reduction.

    Formula: price = base_price × (1 - reduction_pct)^elapsed_years
    """
    if base_price is None or base_price <= 0:
        return Decimal("0")
    if reduction_pct <= 0 or elapsed_years <= 0:
        return base_price

    factor = Decimal(str(1 - reduction_pct)) ** elapsed_years
    return round(base_price * factor, 4)


async def create_price_account(
    db: AsyncSession,
    part_id: int,
    customer_id: int,
    material: Optional[str] = None,
    net_weight_kg: Optional[float] = None,
    gross_weight_kg: Optional[float] = None,
    material_unit_price: Optional[Decimal] = None,
    scrap_price: Optional[Decimal] = None,
    reduction_pct: float = 0.0,
    notes: Optional[str] = None,
) -> PriceAccount:
    """Create a new price account for part + customer."""
    account = PriceAccount(
        part_id=part_id,
        customer_id=customer_id,
        material=material,
        net_weight_kg=net_weight_kg,
        gross_weight_kg=gross_weight_kg,
        material_unit_price=material_unit_price,
        scrap_price=scrap_price,
        reduction_pct=reduction_pct,
        notes=notes,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def get_price_account_by_id(
    db: AsyncSession,
    account_id: int,
) -> Optional[PriceAccount]:
    """Get price account by ID."""
    result = await db.execute(
        select(PriceAccount)
        .options(
            selectinload(PriceAccount.annual_records),
            selectinload(PriceAccount.adjustments),
        )
        .where(PriceAccount.id == account_id, PriceAccount.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_price_account_by_part_customer(
    db: AsyncSession,
    part_id: int,
    customer_id: int,
) -> Optional[PriceAccount]:
    """Get price account by part and customer."""
    result = await db.execute(
        select(PriceAccount)
        .options(
            selectinload(PriceAccount.annual_records),
            selectinload(PriceAccount.adjustments),
        )
        .where(
            PriceAccount.part_id == part_id,
            PriceAccount.customer_id == customer_id,
            PriceAccount.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_price_accounts_by_part(
    db: AsyncSession,
    part_id: int,
) -> Sequence[PriceAccount]:
    """Get all price accounts for a part."""
    result = await db.execute(
        select(PriceAccount)
        .options(selectinload(PriceAccount.annual_records))
        .where(PriceAccount.part_id == part_id, PriceAccount.is_deleted == False)
    )
    return result.scalars().all()


async def update_price_account(
    db: AsyncSession,
    account: PriceAccount,
    **fields,
) -> PriceAccount:
    """Update price account fields."""
    for key, value in fields.items():
        if hasattr(account, key):
            setattr(account, key, value)
    await db.commit()
    await db.refresh(account)
    return account


async def add_annual_price_record(
    db: AsyncSession,
    account_id: int,
    year: int,
    unit_price: Decimal,
    annual_qty: Optional[int] = None,
    notes: Optional[str] = None,
    created_by: Optional[User] = None,
) -> AnnualPriceRecord:
    """Add an annual price record to a price account."""
    record = AnnualPriceRecord(
        price_account_id=account_id,
        year=year,
        unit_price=unit_price,
        annual_qty=annual_qty,
        notes=notes,
        created_by=created_by.id if created_by else None,
    )
    db.add(record)

    account = await get_price_account_by_id(db, account_id)
    if account:
        account.current_price = unit_price
        account.price_year = year

    await db.commit()
    await db.refresh(record)
    return record


async def get_annual_records(
    db: AsyncSession,
    account_id: int,
) -> Sequence[AnnualPriceRecord]:
    """Get all annual records for a price account."""
    result = await db.execute(
        select(AnnualPriceRecord)
        .where(
            AnnualPriceRecord.price_account_id == account_id,
            AnnualPriceRecord.is_deleted == False,
        )
        .order_by(AnnualPriceRecord.year.desc())
    )
    return result.scalars().all()


def compute_current_price_from_records(
    account: PriceAccount,
    current_year: Optional[int] = None,
) -> tuple[Optional[Decimal], Optional[int]]:
    """Compute current price from annual records or annual reduction formula.

    Returns (current_price, price_year).
    """
    if current_year is None:
        current_year = datetime.utcnow().year

    if account.annual_records:
        latest_record = max(
            [r for r in account.annual_records if r.year <= current_year],
            key=lambda r: r.year,
            default=None,
        )
        if latest_record:
            return latest_record.unit_price, latest_record.year

    if account.base_price and account.reduction_pct > 0:
        base_year = account.price_year or (current_year - 1)
        elapsed = current_year - base_year
        if elapsed > 0:
            price = calculate_current_price(
                account.base_price,
                account.reduction_pct,
                elapsed,
            )
            return price, current_year

    return account.current_price, account.price_year


async def record_price_adjustment(
    db: AsyncSession,
    account_id: int,
    old_price: Decimal,
    new_price: Decimal,
    adjustment_type: PriceAdjustmentType,
    reason: Optional[str],
    created_by: User,
) -> PriceAdjustment:
    """Record a manual price adjustment."""
    adjustment = PriceAdjustment(
        price_account_id=account_id,
        old_price=old_price,
        new_price=new_price,
        adjustment_type=adjustment_type,
        reason=reason,
        created_by=created_by.id,
    )
    db.add(adjustment)

    account = await get_price_account_by_id(db, account_id)
    if account:
        account.current_price = new_price

    await db.commit()
    await db.refresh(adjustment)
    return adjustment
