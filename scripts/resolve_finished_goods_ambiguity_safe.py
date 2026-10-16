import asyncio
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import async_session_maker

BATCH_ID = 8
OUT = Path(__file__).resolve().parents[1] / "docs" / "finished_goods_ambiguity_auto_resolved_2026-09-24.csv"


def norm(value):
    return re.sub(r"[\s\u3000]+", "", str(value or "")).casefold()


def is_blank_part(part):
    return not any(
        part.get(key)
        for key in ("internal_part_no", "customer_part_no", "customer_part_name", "internal_name")
    )


async def main():
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                text("""
                    SELECT id, source_sheet, source_row, raw_data,
                           resolved_customer_id, parsed_customer_part_no,
                           parsed_customer_part_name, validation_errors
                    FROM excel_import_rows
                    WHERE batch_id=:batch_id
                      AND validation_errors LIKE '%零件匹配歧义%'
                    ORDER BY source_sheet, source_row
                """),
                {"batch_id": BATCH_ID},
            )
        ).mappings().all()

        parts = (
            await session.execute(
                text("""
                    SELECT id, customer_id, internal_part_no,
                           customer_part_no, customer_part_name, internal_name
                    FROM parts
                    WHERE COALESCE(is_deleted, FALSE)=FALSE
                """)
            )
        ).mappings().all()
        aliases = (
            await session.execute(
                text("""
                    SELECT customer_id, part_id, customer_part_no, customer_part_name
                    FROM part_customer_aliases
                    WHERE COALESCE(is_active, TRUE)=TRUE
                """)
            )
        ).mappings().all()

        part_by_id = {part["id"]: dict(part) for part in parts}
        by_key = defaultdict(set)
        for part in parts:
            for value in (
                part["internal_part_no"],
                part["customer_part_no"],
                part["customer_part_name"],
            ):
                if value:
                    by_key[(part["customer_id"], norm(value))].add(part["id"])
        for alias in aliases:
            for value in (alias["customer_part_no"], alias["customer_part_name"]):
                if value:
                    by_key[(alias["customer_id"], norm(value))].add(alias["part_id"])

        changed = []
        for row in rows:
            candidates = [part_by_id[pid] for pid in sorted(by_key.get((row["resolved_customer_id"], norm(row["parsed_customer_part_no"])), set())) if pid in part_by_id]
            source_name = norm(row["parsed_customer_part_name"])
            exact = [
                part
                for part in candidates
                if source_name
                and source_name in {norm(part["customer_part_name"]), norm(part["internal_name"])}
            ]
            blank_candidates = [part for part in candidates if is_blank_part(part)]
            nonblank = [part for part in candidates if not is_blank_part(part)]

            chosen = None
            method = None
            if len(exact) == 1:
                chosen = exact[0]
                method = "歧义候选中源零件名唯一匹配"
            elif len(nonblank) == 1 and len(blank_candidates) == len(candidates) - 1:
                chosen = nonblank[0]
                method = "歧义候选中仅一个完整零件记录"
            if chosen is None:
                continue

            errors = [
                item
                for item in (row["validation_errors"] or "").split(";")
                if item and item != "零件匹配歧义"
            ]
            raw = dict(row["raw_data"] or {})
            normalized = dict(raw.get("normalized") or {})
            normalized.update(
                {
                    "customer_id": row["resolved_customer_id"],
                    "customer_part_no": row["parsed_customer_part_no"],
                    "customer_part_name": row["parsed_customer_part_name"],
                    "decision": method,
                    "resolved_part_id": chosen["id"],
                }
            )
            raw["normalized"] = normalized
            status = "IMPORTED" if not errors else "REVIEW"
            await session.execute(
                text("""
                    UPDATE excel_import_rows
                    SET raw_data=CAST(:raw_data AS jsonb),
                        resolved_part_id=:part_id,
                        validation_errors=:errors,
                        validation_status=:status
                    WHERE id=:id
                """),
                {
                    "raw_data": json.dumps(raw, ensure_ascii=False),
                    "part_id": chosen["id"],
                    "errors": ";".join(errors) if errors else None,
                    "status": status,
                    "id": row["id"],
                },
            )
            changed.append(
                {
                    "导入记录ID": row["id"],
                    "工作表": row["source_sheet"],
                    "源行号": row["source_row"],
                    "客户ID": row["resolved_customer_id"],
                    "客户件号": row["parsed_customer_part_no"],
                    "源零件名": row["parsed_customer_part_name"],
                    "回填part_id": chosen["id"],
                    "判定方式": method,
                    "剩余错误": ";".join(errors),
                }
            )

        totals = (
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
            {"valid_rows": totals["imported"], "failed_rows": totals["review"], "batch_id": BATCH_ID},
        )
        await session.commit()

    with OUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["导入记录ID", "工作表", "源行号", "客户ID", "客户件号", "源零件名", "回填part_id", "判定方式", "剩余错误"])
        writer.writeheader()
        writer.writerows(changed)
    print(json.dumps({"status": "COMPLETED", "changed": len(changed), "totals": dict(totals), "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
