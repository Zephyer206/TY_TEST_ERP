import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import async_session_maker

BATCH_ID = 8
SHEET_TO_CUSTOMER = {"重庆辉门": 14}


async def main():
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                text("""
                    SELECT id, source_sheet, raw_data,
                           parsed_customer_part_no, parsed_customer_part_name,
                           validation_errors
                    FROM excel_import_rows
                    WHERE batch_id=:batch_id
                      AND validation_status='REVIEW'
                      AND validation_errors LIKE '%工作表未匹配客户%'
                """),
                {"batch_id": BATCH_ID},
            )
        ).mappings().all()

        changed = 0
        for row in rows:
            customer_id = SHEET_TO_CUSTOMER.get(row["source_sheet"])
            if customer_id is None:
                continue
            errors = [
                item
                for item in (row["validation_errors"] or "").split(";")
                if item and item != "工作表未匹配客户"
            ]
            raw = dict(row["raw_data"] or {})
            normalized = dict(raw.get("normalized") or {})
            normalized.update(
                {
                    "customer_id": customer_id,
                    "customer_part_no": row["parsed_customer_part_no"],
                    "customer_part_name": row["parsed_customer_part_name"],
                    "decision": "显式工作表别名映射",
                }
            )
            raw["normalized"] = normalized
            await session.execute(
                text("""
                    UPDATE excel_import_rows
                    SET raw_data=CAST(:raw_data AS jsonb),
                        resolved_customer_id=:customer_id,
                        validation_errors=:errors
                    WHERE id=:id
                """),
                {
                    "raw_data": json.dumps(raw, ensure_ascii=False),
                    "customer_id": customer_id,
                    "errors": ";".join(errors) if errors else None,
                    "id": row["id"],
                },
            )
            changed += 1

        current = (
            await session.execute(
                text("""
                    SELECT COUNT(*) FILTER (WHERE validation_status='IMPORTED') AS imported,
                           COUNT(*) FILTER (WHERE validation_status='REVIEW') AS review
                    FROM excel_import_rows WHERE batch_id=:batch_id
                """),
                {"batch_id": BATCH_ID},
            )
        ).mappings().one()
        await session.execute(
            text("""
                UPDATE import_batches
                SET valid_rows=:valid_rows, failed_rows=:failed_rows
                WHERE id=:batch_id
            """),
            {"valid_rows": current["imported"], "failed_rows": current["review"], "batch_id": BATCH_ID},
        )
        await session.commit()
        print(json.dumps({"status": "COMPLETED", "changed": changed, "totals": dict(current)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
