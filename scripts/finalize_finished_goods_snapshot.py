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


async def main():
    async with async_session_maker() as session:
        already = await session.execute(text("""SELECT count(*) FROM inventory_transactions
            WHERE reference_type='excel_snapshot' AND reference_id=:batch_id"""), {"batch_id": BATCH_ID})
        if already.scalar_one() > 0:
            print(json.dumps({"status": "SKIPPED_EXISTING", "batch_id": BATCH_ID}, ensure_ascii=False))
            return

        rows = (await session.execute(text("""SELECT resolved_customer_id, resolved_part_id,
                parsed_customer_part_no, parsed_customer_part_name, raw_data
            FROM excel_import_rows
            WHERE batch_id=:batch_id AND validation_status='IMPORTED'
              AND resolved_customer_id IS NOT NULL AND resolved_part_id IS NOT NULL
              AND parsed_customer_part_no IS NOT NULL"""), {"batch_id": BATCH_ID})).mappings().all()

        aliases_added = 0
        aggregates = defaultdict(lambda: {"qty": 0, "locations": set(), "customer_ids": set()})
        for row in rows:
            existing = await session.execute(text("""SELECT id FROM part_customer_aliases
                WHERE customer_id=:customer_id AND part_id=:part_id AND customer_part_no=:part_no
                LIMIT 1"""), {"customer_id": row["resolved_customer_id"], "part_id": row["resolved_part_id"], "part_no": row["parsed_customer_part_no"]})
            if existing.first() is None:
                await session.execute(text("""INSERT INTO part_customer_aliases
                    (part_id, customer_id, customer_part_no, customer_part_name, customer_name,
                     revision, is_active, data_quality_status, data_quality_reason, created_at, updated_at)
                    VALUES (:part_id, :customer_id, :part_no, :part_name, NULL, '', TRUE, 'approved',
                            '由成品库存快照唯一匹配导入', :created_at, :updated_at)"""), {
                    "part_id": row["resolved_part_id"], "customer_id": row["resolved_customer_id"],
                    "part_no": row["parsed_customer_part_no"], "part_name": row["parsed_customer_part_name"],
                    "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
                })
                aliases_added += 1
            raw = row["raw_data"] or {}
            qty = raw.get("closing_qty")
            try:
                qty = int(float(qty or 0))
            except (TypeError, ValueError):
                qty = 0
            location = raw.get("location")
            item = aggregates[row["resolved_part_id"]]
            item["qty"] += qty
            item["customer_ids"].add(row["resolved_customer_id"])
            if location:
                item["locations"].add(str(location).strip())

        inventory_rows = 0
        transaction_rows = 0
        for part_id, item in aggregates.items():
            location = next(iter(item["locations"])) if len(item["locations"]) == 1 else ("导入快照-多库位" if item["locations"] else "导入快照-待定库位")
            result = await session.execute(text("""INSERT INTO finished_goods_inventory
                (part_id, stock_qty, reserved_qty, location, last_update_by, last_update_at, created_at)
                VALUES (:part_id, :stock_qty, 0, :location, NULL, :now, :now)
                RETURNING id"""), {"part_id": part_id, "stock_qty": item["qty"], "location": location, "now": datetime.utcnow()})
            inventory_id = result.scalar_one()
            inventory_rows += 1
            await session.execute(text("""INSERT INTO inventory_transactions
                (part_id, transaction_type, quantity, stock_before, stock_after,
                 reference_type, reference_id, reason, operator_id, created_at)
                VALUES (:part_id, 'opening_balance', :quantity, 0, :quantity,
                        'excel_snapshot', :batch_id, :reason, NULL, :created_at)"""), {
                "part_id": part_id, "quantity": item["qty"], "batch_id": BATCH_ID,
                "reason": f"成品库存快照期初导入，库存日期 {INVENTORY_DATE}；同零件按快照结存汇总",
                "created_at": datetime.utcnow(),
            })
            transaction_rows += 1

        await session.commit()
        print(json.dumps({"status": "COMPLETED", "batch_id": BATCH_ID, "aliases_added": aliases_added, "inventory_rows": inventory_rows, "transaction_rows": transaction_rows, "source_rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
