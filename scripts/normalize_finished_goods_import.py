import asyncio
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import async_session_maker

BATCH_ID = 8


def norm(value):
    return re.sub(r"[\s\u3000]+", "", str(value or "")).casefold()


def field_score(value):
    """Score how strongly a cell resembles a part number vs a part name."""
    if value in (None, ""):
        return -999
    value = str(value).strip()
    score = 0
    if re.search(r"[\u4e00-\u9fff]", value):
        score -= 3
    if re.search(r"\d", value):
        score += 3
    if re.search(r"[A-Za-z]", value):
        score += 1
    if re.search(r"[-_./]", value):
        score += 1
    if re.fullmatch(r"[A-Za-z][A-Za-z _()/.-]*", value):
        score -= 3
    if re.fullmatch(r"\d+", value):
        score += 1
    if len(value) <= 3 and not re.search(r"\d", value):
        score -= 2
    return score


def infer_orientation(b, c, b_ids, c_ids, sheet_default):
    """Return B or C as the part-number column, or None if still unclear."""
    if len(b_ids) == 1 and not c_ids:
        return "B", "主数据匹配B列"
    if len(c_ids) == 1 and not b_ids:
        return "C", "主数据匹配C列"
    if len(b_ids) == 1 and len(c_ids) == 1 and b_ids == c_ids:
        return "B", "主数据匹配B/C同一零件"

    b_score = field_score(b)
    c_score = field_score(c)
    if b_score - c_score >= 2:
        return "B", "内容特征判断B列"
    if c_score - b_score >= 2:
        return "C", "内容特征判断C列"
    if sheet_default:
        return sheet_default, f"工作表主流方向判断{sheet_default}列"
    return None, "无法唯一判断"


async def main():
    async with async_session_maker() as session:
        customers = (await session.execute(text("SELECT id, name, short_name, sheet_key FROM customers"))).mappings().all()
        aliases = (await session.execute(text("SELECT customer_id, part_id, customer_part_no, customer_part_name FROM part_customer_aliases"))).mappings().all()
        parts = (await session.execute(text("SELECT id, customer_id, internal_part_no, customer_part_no, customer_part_name FROM parts"))).mappings().all()

        customer_map = {}
        for customer in customers:
            for key in (customer["name"], customer["short_name"], customer["sheet_key"]):
                if key:
                    customer_map[norm(key)] = customer["id"]
            base = re.sub(r"[（(][^（）()]*[）)]\s*$", "", customer["name"])
            customer_map[norm(base)] = customer["id"]

        values_by_customer = defaultdict(lambda: defaultdict(set))
        for row in aliases:
            for value in (row["customer_part_no"], row["customer_part_name"]):
                if value:
                    values_by_customer[row["customer_id"]][norm(value)].add(row["part_id"])
        for row in parts:
            for value in (row["internal_part_no"], row["customer_part_no"], row["customer_part_name"]):
                if value:
                    values_by_customer[row["customer_id"]][norm(value)].add(row["id"])

        result = await session.execute(text("SELECT id, source_sheet, raw_data FROM excel_import_rows WHERE batch_id=:batch_id ORDER BY id"), {"batch_id": BATCH_ID})
        rows = result.mappings().all()

        # Learn each sheet's dominant part-number direction from rows with a clear signal.
        sheet_counts = defaultdict(Counter)
        for row in rows:
            raw = row["raw_data"] or {}
            b = (raw.get("B") or {}).get("value")
            c = (raw.get("C") or {}).get("value")
            b_score = field_score(b)
            c_score = field_score(c)
            if b_score - c_score >= 2:
                sheet_counts[row["source_sheet"]]["B"] += 1
            elif c_score - b_score >= 2:
                sheet_counts[row["source_sheet"]]["C"] += 1

        sheet_defaults = {}
        for sheet, counts in sheet_counts.items():
            b_count = counts["B"]
            c_count = counts["C"]
            if b_count >= 5 and b_count >= max(3 * c_count, c_count + 5):
                sheet_defaults[sheet] = "B"
            elif c_count >= 5 and c_count >= max(3 * b_count, b_count + 5):
                sheet_defaults[sheet] = "C"

        stats = Counter()
        for row in rows:
            raw = row["raw_data"] or {}
            customer_id = customer_map.get(norm(row["source_sheet"]))
            if customer_id is None:
                matches = {
                    customer["id"]
                    for customer in customers
                    if norm(customer["name"]) in norm(row["source_sheet"])
                    or norm(row["source_sheet"]) in norm(customer["name"])
                }
                customer_id = next(iter(matches)) if len(matches) == 1 else None
            candidate_ids = values_by_customer[customer_id] if customer_id else {}
            b = (raw.get("B") or {}).get("value")
            c = (raw.get("C") or {}).get("value")
            b = str(b).strip() if b not in (None, "") else None
            c = str(c).strip() if c not in (None, "") else None
            b_ids = candidate_ids.get(norm(b), set()) if b else set()
            c_ids = candidate_ids.get(norm(c), set()) if c else set()
            orientation, method = infer_orientation(b, c, b_ids, c_ids, sheet_defaults.get(row["source_sheet"]))
            if orientation == "B":
                part_no, part_name = b, c
            elif orientation == "C":
                part_no, part_name = c, b
            else:
                part_no, part_name = None, None

            candidates = candidate_ids.get(norm(part_no), set()) if part_no else set()
            errors = []
            if not customer_id:
                errors.append("工作表未匹配客户")
            if not part_no:
                errors.append("B/C件号件名无法唯一判断")
            if len(candidates) > 1:
                errors.append("零件匹配歧义")
            elif len(candidates) == 0 and part_no:
                errors.append("零件库没有对应的件号")
            status = "IMPORTED" if not errors else "REVIEW"
            raw["normalized"] = {
                "customer_id": customer_id,
                "customer_part_no": part_no,
                "customer_part_name": part_name,
                "decision": method,
            }
            await session.execute(text("""UPDATE excel_import_rows
                SET raw_data=CAST(:raw_data AS jsonb), parsed_customer_name=:customer_name,
                    parsed_customer_part_no=:part_no, parsed_customer_part_name=:part_name,
                    validation_status=:status, validation_errors=:errors,
                    resolved_customer_id=:customer_id, resolved_part_id=:part_id
                WHERE id=:id"""), {
                "raw_data": json.dumps(raw, ensure_ascii=False),
                "customer_name": row["source_sheet"],
                "part_no": part_no,
                "part_name": part_name,
                "status": status,
                "errors": ";".join(errors) if errors else None,
                "customer_id": customer_id,
                "part_id": next(iter(candidates)) if len(candidates) == 1 else None,
                "id": row["id"],
            })
            stats[status] += 1
            stats[method] += 1
            if "B/C件号件名无法唯一判断" in errors:
                stats["B/C仍无法判断"] += 1
            elif "零件匹配歧义" in errors:
                stats["零件匹配歧义"] += 1
            elif "零件库没有对应的件号" in errors:
                stats["零件库无对应件号"] += 1
            else:
                stats["唯一匹配入账候选"] += 1

        await session.execute(text("""UPDATE import_batches SET valid_rows=:valid_rows, failed_rows=:failed_rows WHERE id=:batch_id"""), {
            "valid_rows": stats["IMPORTED"],
            "failed_rows": stats["REVIEW"],
            "batch_id": BATCH_ID,
        })
        await session.commit()
        print(dict(stats))


if __name__ == "__main__":
    asyncio.run(main())
