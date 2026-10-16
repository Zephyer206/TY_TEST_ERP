import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import async_session_maker

BATCH_ID = 8
INVENTORY_DATE = "2026-09-24"
REFERENCE_TYPE = "excel_snapshot_incremental"


async def main():
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT id, resolved_customer_id, resolved_part_id,
                           parsed_customer_part_no, parsed_customer_part_name, raw_data
                    FROM excel_import_rows
                    WHERE batch_id=:batch_id
                      AND validation_status='IMPORTED'
                      AND resolved_customer_id IS NOT NULL
                      AND resolved_part_id IS NOT NULL
                      AND parsed_customer_part_no IS NOT NULL
                    ORDER BY id
                    """
                ),
                {"batch_id": BATCH_ID},
            )
        ).mappings().all()

        grouped = defaultdict(lambda: {"rows": [], "qty": 0, "locations": set()})
        skipped_negative = []
        for row in rows:
            raw = row["raw_data"] or {}
            try:
                qty = int(float(raw.get("closing_qty") or 0))
            except (TypeError, ValueError):
                continue
            item = grouped[row["resolved_part_id"]]
            item["rows"].append(row)
            item["qty"] += qty
            location = str(raw.get("location") or "").strip()
            if location:
                item["locations"].add(location)

        existing_parts = {
            row[0]
            for row in (
                await session.execute(
                    text(
                        """
                        SELECT DISTINCT part_id
                        FROM inventory_transactions
                        WHERE reference_id=:batch_id
                        """
                    ),
                    {"batch_id": BATCH_ID},
                )
            ).all()
        }

        accepted = {
            part_id: item
            for part_id, item in grouped.items()
            if part_id not in existing_parts and item["qty"] >= 0
        }
        skipped_negative = [part_id for part_id, item in grouped.items() if part_id not in existing_parts and item["qty"] < 0]

        aliases_added = 0
        inventory_rows = 0
        transaction_rows = 0
        source_rows = 0
        now = datetime.utcnow()
        for part_id, item in accepted.items():
            for row in item["rows"]:
                alias = await session.execute(
                    text(
                        """
                        SELECT id FROM part_customer_aliases
                        WHERE customer_id=:customer_id AND part_id=:part_id
                          AND customer_part_no=:part_no
                        LIMIT 1
                        """
                    ),
                    {
                        "customer_id": row["resolved_customer_id"],
                        "part_id": part_id,
                        "part_no": row["parsed_customer_part_no"],
                    },
                )
                if alias.first() is None:
                    await session.execute(
                        text(
                            """
                            INSERT INTO part_customer_aliases
                              (part_id, customer_id, customer_part_no, customer_part_name,
                               revision, is_active, data_quality_status, data_quality_reason,
                               created_at, updated_at)
                            VALUES (:part_id, :customer_id, :part_no, :part_name, '', TRUE,
                                    'approved', '成品库存快照安全补导', :now, :now)
                            """
                        ),
                        {
                            "part_id": part_id,
                            "customer_id": row["resolved_customer_id"],
                            "part_no": row["parsed_customer_part_no"],
                            "part_name": row["parsed_customer_part_name"],
                            "now": now,
                        },
                    )
                    aliases_added += 1
                source_rows += 1

            result = await session.execute(
                text(
                    """
                    INSERT INTO finished_goods_inventory
                      (part_id, stock_qty, reserved_qty, location,
                       last_update_by, last_update_at, created_at)
                    VALUES (:part_id, :qty, 0, NULL, NULL, :now, :now)
                    RETURNING id
                    """
                ),
                {"part_id": part_id, "qty": item["qty"], "now": now},
            )
            result.scalar_one()
            inventory_rows += 1
            await session.execute(
                text(
                    """
                    INSERT INTO inventory_transactions
                      (part_id, transaction_type, quantity, stock_before, stock_after,
                       reference_type, reference_id, reason, operator_id, created_at)
                    VALUES (:part_id, 'opening_balance_increment', :qty, 0, :qty,
                            :reference_type, :batch_id, :reason, NULL, :now)
                    """
                ),
                {
                    "part_id": part_id,
                    "qty": item["qty"],
                    "reference_type": REFERENCE_TYPE,
                    "batch_id": BATCH_ID,
                    "reason": f"成品库存快照安全补导，库存日期 {INVENTORY_DATE}；库位待仓库确认",
                    "now": now,
                },
            )
            transaction_rows += 1

        await session.execute(
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
                """
            ),
            {"batch_id": BATCH_ID},
        )

        await session.commit()
        print(
            json.dumps(
                {
                    "status": "COMPLETED",
                    "batch_id": BATCH_ID,
                    "source_rows": source_rows,
                    "accepted_parts": len(accepted),
                    "inventory_rows": inventory_rows,
                    "transaction_rows": transaction_rows,
                    "aliases_added": aliases_added,
                    "skipped_existing_parts": len(existing_parts),
                    "skipped_negative_parts": skipped_negative,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
