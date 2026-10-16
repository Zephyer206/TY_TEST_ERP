"""Business logic for price account management and annual price reduction calculation."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.price import (
    # AnnualPriceRecord,  # 已废弃，使用新的价格历史表
    PriceAccount,
    PriceAdjustment,
    PriceAdjustmentType,
    PriceYear,
)
from app.models.user import User


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
        material_name=material,
        net_weight=net_weight_kg,
        gross_weight=gross_weight_kg,
        material_unit_price=material_unit_price,
        scrap_price=scrap_price,
        remark=notes,
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
        .options(selectinload(PriceAccount.annual_records))
        .where(PriceAccount.id == account_id)
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
        .options(selectinload(PriceAccount.annual_records))
        .where(
            PriceAccount.part_id == part_id,
            PriceAccount.customer_id == customer_id,
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
        .where(PriceAccount.part_id == part_id)
    )
    return result.scalars().all()


async def update_price_account(
    db: AsyncSession,
    account: PriceAccount,
    **fields,
) -> PriceAccount:
    """Update price account fields."""
    field_aliases = {
        "material": "material_name",
        "net_weight_kg": "net_weight",
        "gross_weight_kg": "gross_weight",
        "notes": "remark",
    }
    for key, value in fields.items():
        target = field_aliases.get(key, key)
        if hasattr(account, target) and target not in {"reduction_pct", "is_active"}:
            setattr(account, target, value)
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
):
    """Add a year-price record to the canonical ``price_years`` table."""
    record = PriceYear(
        price_id=account_id,
        year=year,
        unit_price=unit_price,
        annual_sales=annual_qty,
        operator_id=created_by.id if created_by else None,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_annual_records(
    db: AsyncSession,
    account_id: int,
):
    """Get all annual records for a price account."""
    result = await db.execute(
        select(PriceYear).where(PriceYear.price_id == account_id).order_by(PriceYear.year)
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

    return account.base_price, account.price_year


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
    account = await get_price_account_by_id(db, account_id)
    if account is None:
        raise ValueError(f"Price account {account_id} not found")

    adjustment = PriceAdjustment(
        customer_id=account.customer_id,
        part_id=account.part_id,
        adjustment_type=adjustment_type.value
        if isinstance(adjustment_type, PriceAdjustmentType)
        else str(adjustment_type),
        old_price=old_price,
        new_price=new_price,
        reason=reason,
        status="approved",
        requested_by=created_by.id,
        reviewed_by=created_by.id,
        reviewed_at=datetime.utcnow(),
    )
    adjustment.price_account_id = account_id
    db.add(adjustment)

    # ``prices`` has no mutable current-price column.  Store the approved
    # value as the current year's canonical annual record instead.
    current_year = datetime.utcnow().year
    existing = await db.execute(
        select(PriceYear).where(
            PriceYear.price_id == account_id, PriceYear.year == current_year
        )
    )
    annual = existing.scalar_one_or_none()
    if annual is None:
        annual = PriceYear(
            price_id=account_id,
            year=current_year,
            unit_price=new_price,
            operator_id=created_by.id,
        )
        db.add(annual)
    else:
        annual.unit_price = new_price
        annual.operator_id = created_by.id

    await db.commit()
    await db.refresh(adjustment)
    return adjustment
