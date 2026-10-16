import asyncio
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import async_session_maker

BATCH_ID = 8


def norm(value):
    return re.sub(r"[\s\u3000]+", "", unicodedata.normalize("NFKC", str(value or ""))).casefold()


async def main():
    async with async_session_maker() as session:
        already = await session.execute(text("SELECT count(*) FROM inventory_transactions WHERE reference_type='excel_snapshot_incremental' AND reference_id=:batch_id"), {"batch_id": BATCH_ID})
        if already.scalar_one() > 0:
            print(json.dumps({"status": "SKIPPED_EXISTING", "batch_id": BATCH_ID}, ensure_ascii=False))
            return

        parts = (await session.execute(text("SELECT id, customer_id, internal_part_no, customer_part_no, customer_part_name FROM parts"))).mappings().all()
        part_map = defaultdict(set)
        part_customer = {}
        for part in parts:
            part_customer[part["id"]] = part["customer_id"]
            for value in (part["internal_part_no"], part["customer_part_no"], part["customer_part_name"]):
                if value:
                    part_map[norm(value)].add(part["id"])

        rows = (await session.execute(text("""SELECT id, parsed_customer_part_no, parsed_customer_part_name,
                resolved_customer_id, raw_data
            FROM excel_import_rows
            WHERE batch_id=:batch_id AND validation_status='REVIEW'
              AND parsed_customer_part_no IS NOT NULL"""), {"batch_id": BATCH_ID})).mappings().all()
        accepted = []
        for row in rows:
            candidates = part_map.get(norm(row["parsed_customer_part_no"]), set())
            if len(candidates) != 1:
                continue
            part_id = next(iter(candidates))
            customer_id = row["resolved_customer_id"] or part_customer.get(part_id)
            if customer_id is None or (row["resolved_customer_id"] is not None and part_customer.get(part_id) != row["resolved_customer_id"]):
                continue
            raw = row["raw_data"] or {}
            qty = raw.get("closing_qty")
            try:
                qty = int(float(qty or 0))
            except (TypeError, ValueError):
                continue
            if qty < 0:
                continue
            raw["normalized"] = {
                "customer_id": customer_id,
                "customer_part_no": row["parsed_customer_part_no"],
                "customer_part_name": row["parsed_customer_part_name"],
                "decision": "全库唯一件号自动匹配",
            }
            accepted.append((row, raw, part_id, customer_id, qty))

        aggregates = defaultdict(int)
        for row, raw, part_id, customer_id, qty in accepted:
            await session.execute(text("""UPDATE excel_import_rows SET raw_data=CAST(:raw_data AS jsonb),
                validation_status='IMPORTED', validation_errors=NULL,
                resolved_customer_id=:customer_id, resolved_part_id=:part_id
                WHERE id=:id"""), {
                "raw_data": json.dumps(raw, ensure_ascii=False), "customer_id": customer_id,
                "part_id": part_id, "id": row["id"],
            })
            exists = await session.execute(text("""SELECT id FROM part_customer_aliases
                WHERE customer_id=:customer_id AND part_id=:part_id AND customer_part_no=:part_no LIMIT 1"""), {
                "customer_id": customer_id, "part_id": part_id, "part_no": row["parsed_customer_part_no"],
            })
            if exists.first() is None:
                await session.execute(text("""INSERT INTO part_customer_aliases
                    (part_id, customer_id, customer_part_no, customer_part_name, revision, is_active,
                     data_quality_status, data_quality_reason, created_at, updated_at)
                    VALUES (:part_id, :customer_id, :part_no, :part_name, '', TRUE, 'approved',
                            '由全库唯一件号自动匹配导入', :now, :now)"""), {
                    "part_id": part_id, "customer_id": customer_id, "part_no": row["parsed_customer_part_no"],
                    "part_name": row["parsed_customer_part_name"], "now": datetime.utcnow(),
                })
            aggregates[part_id] += qty

        for part_id, quantity in aggregates.items():
            inv = await session.execute(text("SELECT id, stock_qty, location FROM finished_goods_inventory WHERE part_id=:part_id LIMIT 1"), {"part_id": part_id})
            current = inv.first()
            if current:
                before = int(current[1] or 0)
                after = before + quantity
                await session.execute(text("UPDATE finished_goods_inventory SET stock_qty=:after, last_update_at=:now WHERE id=:id"), {"after": after, "now": datetime.utcnow(), "id": current[0]})
            else:
                before = 0
                after = quantity
                await session.execute(text("""INSERT INTO finished_goods_inventory
                    (part_id, stock_qty, reserved_qty, location, last_update_at, created_at)
                    VALUES (:part_id, :after, 0, '导入快照-自动匹配', :now, :now)"""), {"part_id": part_id, "after": after, "now": datetime.utcnow()})
            await session.execute(text("""INSERT INTO inventory_transactions
                (part_id, transaction_type, quantity, stock_before, stock_after,
                 reference_type, reference_id, reason, created_at)
                VALUES (:part_id, 'opening_balance_increment', :quantity, :before, :after,
                        'excel_snapshot_incremental', :batch_id, '全库唯一件号自动匹配后的库存增量', :now)"""), {
                "part_id": part_id, "quantity": quantity, "before": before, "after": after,
                "batch_id": BATCH_ID, "now": datetime.utcnow(),
            })

        await session.execute(text("""
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
        """), {"batch_id": BATCH_ID})

        await session.execute(text("UPDATE import_batches SET valid_rows=valid_rows+:n, failed_rows=failed_rows-:n WHERE id=:batch_id"), {"n": len(accepted), "batch_id": BATCH_ID})
        await session.commit()
        print(json.dumps({"status": "COMPLETED", "accepted_rows": len(accepted), "affected_parts": len(aggregates)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
