import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import async_session_maker

BATCH_ID = 8


async def main():
    async with async_session_maker() as session:
        before = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) AS parts,
                           COUNT(*) FILTER (WHERE p.stock_pcs <> i.stock_qty) AS mismatched,
                           COALESCE(SUM(p.stock_pcs), 0) AS part_stock,
                           COALESCE(SUM(i.stock_qty), 0) AS inventory_stock
                    FROM parts p
                    JOIN (
                        SELECT part_id, SUM(stock_qty) AS stock_qty
                        FROM finished_goods_inventory
                        WHERE part_id IN (
                            SELECT DISTINCT part_id
                            FROM inventory_transactions
                            WHERE reference_id=:batch_id
                        )
                        GROUP BY part_id
                    ) i ON i.part_id=p.id
                    """
                ),
                {"batch_id": BATCH_ID},
            )
        ).mappings().one()

        result = await session.execute(
            text(
                """
                UPDATE parts p
                SET stock_pcs=i.stock_qty,
                    updated_at=NOW()
                FROM (
                    SELECT part_id, SUM(stock_qty)::integer AS stock_qty
                    FROM finished_goods_inventory
                    WHERE part_id IN (
                        SELECT DISTINCT part_id
                        FROM inventory_transactions
                        WHERE reference_id=:batch_id
                    )
                    GROUP BY part_id
                ) i
                WHERE p.id=i.part_id
                RETURNING p.id
                """
            ),
            {"batch_id": BATCH_ID},
        )
        updated = len(result.all())
        await session.commit()

        after = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) AS parts,
                           COUNT(*) FILTER (WHERE p.stock_pcs <> i.stock_qty) AS mismatched,
                           COALESCE(SUM(p.stock_pcs), 0) AS part_stock,
                           COALESCE(SUM(i.stock_qty), 0) AS inventory_stock
                    FROM parts p
                    JOIN (
                        SELECT part_id, SUM(stock_qty) AS stock_qty
                        FROM finished_goods_inventory
                        WHERE part_id IN (
                            SELECT DISTINCT part_id
                            FROM inventory_transactions
                            WHERE reference_id=:batch_id
                        )
                        GROUP BY part_id
                    ) i ON i.part_id=p.id
                    """
                ),
                {"batch_id": BATCH_ID},
            )
        ).mappings().one()

        def clean(value):
            return {key: (float(val) if hasattr(val, "as_tuple") else val) for key, val in value.items()}

        print(json.dumps({"batch_id": BATCH_ID, "updated_parts": updated, "before": clean(before), "after": clean(after)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
