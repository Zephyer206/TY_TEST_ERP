import asyncio
import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import async_session_maker

BATCH_ID = 8
OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "finished_goods_format_review_2026-09-24.csv"


def exact_norm(value):
    return re.sub(r"[\s\u3000]+", "", unicodedata.normalize("NFKC", str(value or ""))).casefold()


def punctuation_norm(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in value if character.isalnum())


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
                           customer_part_name, internal_name, is_deleted
                    FROM parts
                    WHERE COALESCE(is_deleted, FALSE)=FALSE
                """)
            )
        ).mappings().all()
        aliases = (
            await session.execute(
                text("""
                    SELECT customer_id, part_id, customer_part_no, is_active
                    FROM part_customer_aliases
                    WHERE COALESCE(is_active, TRUE)=TRUE
                """)
            )
        ).mappings().all()

    part_by_id = {part["id"]: dict(part) for part in parts}
    by_customer_key = defaultdict(set)
    by_customer_exact = defaultdict(set)
    codes_by_part_customer = defaultdict(set)
    for part in parts:
        for value in (part["internal_part_no"], part["customer_part_no"]):
            if value:
                key = (part["customer_id"], punctuation_norm(value))
                by_customer_key[key].add(part["id"])
                by_customer_exact[(part["customer_id"], exact_norm(value))].add(part["id"])
                codes_by_part_customer[(part["customer_id"], part["id"])].add(value)
    for alias in aliases:
        if not alias["customer_part_no"] or alias["part_id"] not in part_by_id:
            continue
        key = (alias["customer_id"], punctuation_norm(alias["customer_part_no"]))
        by_customer_key[key].add(alias["part_id"])
        by_customer_exact[(alias["customer_id"], exact_norm(alias["customer_part_no"]))].add(alias["part_id"])
        codes_by_part_customer[(alias["customer_id"], alias["part_id"])].add(alias["customer_part_no"])

    output_rows = []
    for row in rows:
        customer_id = row["resolved_customer_id"]
        source_code = row["parsed_customer_part_no"]
        if customer_id is None or not source_code:
            continue
        key = (customer_id, punctuation_norm(source_code))
        candidates = by_customer_key.get(key, set())
        if len(candidates) != 1:
            continue
        part_id = next(iter(candidates))
        if part_id in by_customer_exact.get((customer_id, exact_norm(source_code)), set()):
            continue
        candidate_codes = sorted(codes_by_part_customer[(customer_id, part_id)])
        candidate_code = next(
            (value for value in candidate_codes if punctuation_norm(value) == punctuation_norm(source_code)),
            None,
        )
        if not candidate_code or exact_norm(candidate_code) == exact_norm(source_code):
            continue
        part = part_by_id[part_id]
        raw = row["raw_data"] or {}
        output_rows.append(
            {
                "导入记录ID": row["id"],
                "工作表": row["source_sheet"],
                "源行号": row["source_row"],
                "客户": customers.get(customer_id, ""),
                "客户件号原值": source_code,
                "主数据件号候选": candidate_code,
                "源零件名": row["parsed_customer_part_name"],
                "候选part_id": part_id,
                "主数据零件名": part["customer_part_name"],
                "内部零件名": part["internal_name"],
                "结存数量": raw.get("closing_qty"),
                "库位": raw.get("location"),
                "建议": "确认分隔符差异是否仅为格式后再建立客户件号别名",
            }
        )

    columns = [
        "导入记录ID", "工作表", "源行号", "客户", "客户件号原值",
        "主数据件号候选", "源零件名", "候选part_id", "主数据零件名",
        "内部零件名", "结存数量", "库位", "建议",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(output_rows)
    print({"rows": len(output_rows), "output": str(OUTPUT)})


if __name__ == "__main__":
    asyncio.run(main())
