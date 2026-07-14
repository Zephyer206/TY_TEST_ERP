"""Customers API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, text

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.customer import Customer
from pydantic import BaseModel, Field

router = APIRouter(prefix="/customers", tags=["Customers"])


class CustomerCreate(BaseModel):
    name: str = Field(max_length=200)
    sheet_key: Optional[str] = Field(default=None, max_length=100)


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    sheet_key: Optional[str] = Field(default=None, max_length=100)


class CustomerResponse(BaseModel):
    id: int
    name: str
    customer_code: Optional[str] = None
    sheet_key: Optional[str] = None
    created_at: Optional[datetime] = None
    part_count: Optional[int] = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[CustomerResponse])
async def list_customers(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    is_active: Optional[bool] = Query(default=True, description="Filter by active status"),
    has_parts: Optional[bool] = Query(default=None, description="Filter customers with parts"),
    include_part_count: bool = Query(default=False, description="Include part count in response"),
) -> list[CustomerResponse]:
    """List customers with optional search and filters."""
    from sqlalchemy import func, exists
    from app.models.part_customer_alias import PartCustomerAlias

    q = select(Customer)

    # Filter by active status
    if is_active is not None:
        q = q.where(Customer.is_active == is_active)

    # Filter by has_parts - customers with at least one active part alias
    if has_parts:
        q = q.where(
            exists(
                select(1)
                .select_from(PartCustomerAlias)
                .where(PartCustomerAlias.customer_id == Customer.id)
                .where(PartCustomerAlias.is_active == True)
            )
        )

    # Search by name or customer_code
    if search:
        q = q.where(
            (Customer.name.ilike(f"%{search}%")) |
            (Customer.customer_code.ilike(f"%{search}%"))
        )

    q = q.order_by(Customer.name).offset(skip).limit(limit)
    customers = (await db.execute(q)).scalars().all()

    # Optionally include part count
    result = []
    for c in customers:
        data = CustomerResponse.model_validate(c)
        if include_part_count:
            count_query = select(func.count(func.distinct(PartCustomerAlias.part_id))).where(
                PartCustomerAlias.customer_id == c.id,
                PartCustomerAlias.is_active == True
            )
            count = (await db.execute(count_query)).scalar()
            data.part_count = count
        result.append(data)

    return result


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    db: DbSession,
    current_user: CurrentUser
) -> CustomerResponse:
    """Create a new customer."""
    require_role(current_user, min_level=4)

    # Check for duplicate name
    existing = (await db.execute(
        select(Customer).where(Customer.name == data.name)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="客户名称已存在")

    customer = Customer(
        name=data.name,
        sheet_key=data.sheet_key,
        created_at=datetime.utcnow(),
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> CustomerResponse:
    """Get a customer by ID."""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: DbSession,
    current_user: CurrentUser
) -> CustomerResponse:
    """Update a customer."""
    require_role(current_user, min_level=4)

    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Check for duplicate name if changing name
    if data.name and data.name != customer.name:
        existing = (await db.execute(
            select(Customer).where(Customer.name == data.name)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="客户名称已存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)

    await db.commit()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> None:
    """Delete a customer. Only newly created customers (ID > 89) can be deleted."""
    require_role(current_user, min_level=4)

    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Protect existing customers (ID <= 89)
    if customer_id <= 89:
        raise HTTPException(
            status_code=403,
            detail="无法删除现有客户，只能删除新增的客户"
        )

    await db.delete(customer)
    await db.commit()


@router.get("/{customer_id}/parts")
async def get_customer_parts(
    customer_id: int,
    db: DbSession,
    current_user: CurrentUser
):
    """Get all parts associated with a customer."""
    from app.models.part import Part

    # Get all parts for this customer through quotes
    query = """
        SELECT DISTINCT
            p.id,
            p.part_no,
            p.name,
            p.material_id,
            m.name as material_name
        FROM parts p
        LEFT JOIN materials m ON p.material_id = m.id
        INNER JOIN quotes q ON q.part_id = p.id
        WHERE q.customer_id = :customer_id
        ORDER BY p.part_no
    """

    result = await db.execute(
        select(Part).from_statement(text(query)),
        {"customer_id": customer_id}
    )

    parts = result.scalars().all()

    return [
        {
            "id": part.id,
            "part_no": part.part_no,
            "name": part.name,
            "material_id": part.material_id,
            "material_name": getattr(part, 'material_name', None)
        }
        for part in parts
    ]
