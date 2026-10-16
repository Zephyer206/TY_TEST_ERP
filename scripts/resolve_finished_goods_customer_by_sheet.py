import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import async_session_maker

BATCH_ID = 8

# These sheets intentionally combine multiple customers and require row-level review.
EXCLUDED_COMPOUND_SHEETS = {
    "驰泰&同驭",
    "吉成8I万建",
    "华阳I格陆博",
    "海纳I信义8",
    "天合富奥I",
    "泰明顿6聚邦",
    "莆田荣兴1备普",
    "江苏恒力11瑞立",
    "致森8中联",
}


def norm(value):
    return re.sub(r"[\s\u3000]+", "", str(value or "")).casefold()


def parse_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return None


async def main():
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                text("""
                    SELECT id, source_sheet, source_row, raw_data,
                           parsed_customer_part_no, parsed_customer_part_name,
                           resolved_customer_id, resolved_part_id,
                           validation_errors, validation_status
                    FROM excel_import_rows
                    WHERE batch_id=:batch_id
                    ORDER BY source_sheet, source_row
                """),
                {"batch_id": BATCH_ID},
            )
        ).mappings().all()

        sheet_customer_ids = defaultdict(set)
        sheet_mapped_counts = defaultdict(int)
        for row in rows:
            if row["resolved_customer_id"] is not None:
                sheet_customer_ids[row["source_sheet"]].add(row["resolved_customer_id"])
                sheet_mapped_counts[row["source_sheet"]] += 1

        eligible = {
            sheet: next(iter(customer_ids))
            for sheet, customer_ids in sheet_customer_ids.items()
            if len(customer_ids) == 1
            and sheet_mapped_counts[sheet] >= 2
            and sheet not in EXCLUDED_COMPOUND_SHEETS
        }

        parts = (
            await session.execute(
                text("""
                    SELECT id, customer_id, internal_part_no,
                           customer_part_no, customer_part_name
                    FROM parts
                    WHERE COALESCE(is_deleted, FALSE)=FALSE
                """)
            )
        ).mappings().all()
        aliases = (
            await session.execute(
                text("""
                    SELECT customer_id, part_id, customer_part_no,
                           customer_part_name
                    FROM part_customer_aliases
                    WHERE COALESCE(is_active, TRUE)=TRUE
                """)
            )
        ).mappings().all()

        by_customer_value = defaultdict(set)
        for part in parts:
            for value in (
                part["internal_part_no"],
                part["customer_part_no"],
                part["customer_part_name"],
            ):
                if value:
                    by_customer_value[(part["customer_id"], norm(value))].add(part["id"])
        for alias in aliases:
            for value in (alias["customer_part_no"], alias["customer_part_name"]):
                if value:
                    by_customer_value[(alias["customer_id"], norm(value))].add(alias["part_id"])

        counts = defaultdict(int)
        changed = []
        for row in rows:
            if row["source_sheet"] not in eligible:
                continue
            if not row["validation_errors"] or "工作表未匹配客户" not in row["validation_errors"]:
                continue

            customer_id = eligible[row["source_sheet"]]
            part_no = row["parsed_customer_part_no"]
            candidates = (
                by_customer_value.get((customer_id, norm(part_no)), set())
                if part_no
                else set()
            )

            errors = [
                item
                for item in (row["validation_errors"] or "").split(";")
                if item and item != "工作表未匹配客户"
            ]
            if len(candidates) == 1:
                errors = [
                    item
                    for item in errors
                    if item not in {"零件库没有对应的件号", "未匹配现有零件", "零件匹配歧义"}
                ]
                part_id = next(iter(candidates))
                counts["resolved_part"] += 1
            elif len(candidates) > 1:
                errors = [item for item in errors if item != "零件库没有对应的件号"]
                if "零件匹配歧义" not in errors:
                    errors.append("零件匹配歧义")
                part_id = None
                counts["part_ambiguity"] += 1
            else:
                part_id = None
                if part_no and "零件库没有对应的件号" not in errors:
                    errors.append("零件库没有对应的件号")
                counts["part_unmatched"] += 1

            raw = dict(row["raw_data"] or {})
            normalized = dict(raw.get("normalized") or {})
            normalized.update(
                {
                    "customer_id": customer_id,
                    "customer_part_no": part_no,
                    "customer_part_name": row["parsed_customer_part_name"],
                    "decision": "工作表已有唯一客户证据回填",
                }
            )
            raw["normalized"] = normalized
            status = "IMPORTED" if not errors else "REVIEW"
            await session.execute(
                text("""
                    UPDATE excel_import_rows
                    SET raw_data=CAST(:raw_data AS jsonb),
                        resolved_customer_id=:customer_id,
                        resolved_part_id=:part_id,
                        validation_errors=:errors,
                        validation_status=:status
                    WHERE id=:id
                """),
                {
                    "raw_data": json.dumps(raw, ensure_ascii=False),
                    "customer_id": customer_id,
                    "part_id": part_id,
                    "errors": ";".join(errors) if errors else None,
                    "status": status,
                    "id": row["id"],
                },
            )
            counts["rows"] += 1
            counts[f"status_{status.lower()}"] += 1
            changed.append(
                {
                    "id": row["id"],
                    "sheet": row["source_sheet"],
                    "row": row["source_row"],
                    "customer_id": customer_id,
                    "part_id": part_id,
                    "status": status,
                    "errors": errors,
                }
            )

        current = await session.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE validation_status='IMPORTED') AS imported,
                       COUNT(*) FILTER (WHERE validation_status='REVIEW') AS review
                FROM excel_import_rows WHERE batch_id=:batch_id
            """),
            {"batch_id": BATCH_ID},
        )
        totals = current.mappings().one()
        await session.execute(
            text("""
                UPDATE import_batches
                SET valid_rows=:valid_rows, failed_rows=:failed_rows
                WHERE id=:batch_id
            """),
            {
                "valid_rows": totals["imported"],
                "failed_rows": totals["review"],
                "batch_id": BATCH_ID,
            },
        )
        await session.commit()
        print(
            json.dumps(
                {
                    "status": "COMPLETED",
                    "eligible_sheets": eligible,
                    "counts": dict(counts),
                    "sample_changes": changed[:12],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
