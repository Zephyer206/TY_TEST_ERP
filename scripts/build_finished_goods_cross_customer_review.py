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
OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "finished_goods_cross_customer_review_2026-09-24.csv"


def norm(value):
    return re.sub(r"[\s\u3000]+", "", str(value or "")).casefold()


async def main():
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                text("""
                    SELECT id, source_sheet, source_row, resolved_customer_id,
                           parsed_customer_part_no, parsed_customer_part_name, raw_data
                    FROM excel_import_rows
                    WHERE batch_id=:batch_id
                      AND validation_status='REVIEW'
                      AND validation_errors LIKE '%零件库没有对应的件号%'
                    ORDER BY source_sheet, source_row
                """),
                {"batch_id": BATCH_ID},
            )
        ).mappings().all()
        customers = {
            row["id"]: row["name"]
            for row in (
                await session.execute(text("SELECT id, name FROM customers"))
            ).mappings().all()
        }
        parts = (
            await session.execute(
                text("""
                    SELECT id, customer_id, internal_part_no, customer_part_no,
                           customer_part_name, internal_name, status, is_deleted
                    FROM parts
                """)
            )
        ).mappings().all()
        aliases = (
            await session.execute(
                text("""
                    SELECT customer_id, part_id, customer_part_no, is_active
                    FROM part_customer_aliases
                """)
            )
        ).mappings().all()

    part_by_id = {row["id"]: dict(row) for row in parts}
    by_code = defaultdict(set)
    by_customer_code = defaultdict(set)
    for part in parts:
        if part["is_deleted"]:
            continue
        for value in (part["internal_part_no"], part["customer_part_no"]):
            if value:
                by_code[norm(value)].add(part["id"])
                by_customer_code[(part["customer_id"], norm(value))].add(part["id"])
    for alias in aliases:
        if alias["is_active"] is False or not alias["customer_part_no"]:
            continue
        part = part_by_id.get(alias["part_id"])
        if part and not part["is_deleted"]:
            by_code[norm(alias["customer_part_no"])].add(alias["part_id"])
            by_customer_code[(alias["customer_id"], norm(alias["customer_part_no"]))].add(alias["part_id"])

    output_rows = []
    for row in rows:
        code = norm(row["parsed_customer_part_no"])
        candidates = sorted(by_code.get(code, set())) if code else []
        if not candidates:
            continue
        same_customer = by_customer_code.get((row["resolved_customer_id"], code), set())
        cross_candidates = [part_id for part_id in candidates if part_id not in same_customer]
        if same_customer or not cross_candidates:
            continue

        raw = row["raw_data"] or {}
        source_name = norm(row["parsed_customer_part_name"])
        candidates_text = []
        exact_name_ids = []
        for part_id in cross_candidates:
            part = part_by_id[part_id]
            if source_name and source_name in {
                norm(part["customer_part_name"]),
                norm(part["internal_name"]),
            }:
                exact_name_ids.append(part_id)
            candidates_text.append(
                "|".join(
                    str(value or "")
                    for value in (
                        part["id"],
                        customers.get(part["customer_id"], ""),
                        part["internal_part_no"],
                        part["customer_part_no"],
                        part["customer_part_name"],
                        part["internal_name"],
                        part["status"],
                    )
                )
            )
        qty = raw.get("closing_qty")
        location = raw.get("location")
        output_rows.append(
            {
                "导入记录ID": row["id"],
                "工作表": row["source_sheet"],
                "源行号": row["source_row"],
                "当前客户": customers.get(row["resolved_customer_id"], ""),
                "当前客户ID": row["resolved_customer_id"],
                "件号": row["parsed_customer_part_no"],
                "源零件名": row["parsed_customer_part_name"],
                "结存数量": qty,
                "库位": location,
                "跨客户候选数": len(cross_candidates),
                "零件名精确匹配候选数": len(exact_name_ids),
                "候选内部零件": "; ".join(candidates_text),
                "建议": "核实实际客户归属和零件归属后再决定是否建立客户件号关联",
            }
        )

    columns = [
        "导入记录ID", "工作表", "源行号", "当前客户", "当前客户ID", "件号",
        "源零件名", "结存数量", "库位", "跨客户候选数",
        "零件名精确匹配候选数", "候选内部零件", "建议",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(output_rows)

    print(
        json.dumps(
            {
                "rows": len(output_rows),
                "unique_candidates": sum(row["跨客户候选数"] == 1 for row in output_rows),
                "multiple_candidates": sum(row["跨客户候选数"] > 1 for row in output_rows),
                "exact_name_matches": sum(row["零件名精确匹配候选数"] == 1 for row in output_rows),
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
