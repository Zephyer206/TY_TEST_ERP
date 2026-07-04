"""Part Name Dictionary API - Additional endpoints for three-level structure."""

from fastapi import APIRouter
from sqlalchemy import select, func

from app.api.deps import CurrentUser, DbSession
from app.models.part_name_dict import PartNameDict

router = APIRouter(prefix="/part-names", tags=["Dictionary"])


@router.get("/categories/primary")
async def get_primary_categories(
    db: DbSession,
    current_user: CurrentUser
) -> list[str]:
    """Get all unique primary categories."""
    result = await db.execute(
        select(PartNameDict.primary_category)
        .where(PartNameDict.is_active == True)
        .distinct()
        .order_by(PartNameDict.primary_category)
    )
    return [row[0] for row in result.all()]


@router.get("/categories/secondary")
async def get_secondary_categories(
    db: DbSession,
    current_user: CurrentUser,
    primary_category: str
) -> list[str]:
    """Get secondary categories for a given primary category."""
    result = await db.execute(
        select(PartNameDict.secondary_category)
        .where(
            PartNameDict.is_active == True,
            PartNameDict.primary_category == primary_category,
            PartNameDict.secondary_category.isnot(None)
        )
        .distinct()
        .order_by(PartNameDict.secondary_category)
    )
    return [row[0] for row in result.all()]


@router.get("/tree")
async def get_part_name_tree(
    db: DbSession,
    current_user: CurrentUser
) -> dict:
    """Get complete three-level tree structure."""
    result = await db.execute(
        select(PartNameDict)
        .where(PartNameDict.is_active == True)
        .order_by(
            PartNameDict.primary_category,
            PartNameDict.secondary_category,
            PartNameDict.customer_part_name
        )
    )
    items = result.scalars().all()

    tree = {}
    for item in items:
        primary = item.primary_category
        secondary = item.secondary_category or "直接选择"
        customer = item.customer_part_name or "标准件"

        if primary not in tree:
            tree[primary] = {}
        if secondary not in tree[primary]:
            tree[primary][secondary] = []

        tree[primary][secondary].append({
            "id": item.id,
            "label": customer,
            "remark": item.remark
        })

    return tree
