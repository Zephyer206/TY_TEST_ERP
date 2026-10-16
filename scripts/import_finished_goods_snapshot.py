import asyncio
import hashlib
import json
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import text
from app.database import async_session_maker

FILE = Path(__file__).resolve().parents[1] / "excel" / "成品库报表2026.9.xlsm"
INVENTORY_DATE = "2026-09-24"
NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def norm(value):
    if value is None:
        return ""
    return re.sub(r"[\s\u3000]+", "", unicodedata.normalize("NFKC", str(value))).casefold()


def read_value(cell, shared):
    value = cell.find("a:v", NS)
    kind = cell.attrib.get("t")
    if kind == "s" and value is not None and value.text:
        return shared[int(value.text)]
    if kind == "inlineStr":
        return "".join((node.text or "") for node in cell.findall(".//a:t", NS))
    return value.text if value is not None else None


def parse_number(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def read_workbook():
    with zipfile.ZipFile(FILE) as archive:
        shared = [
            "".join((t.text or "") for t in item.findall(".//a:t", NS))
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("a:si", NS)
        ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        rows = []
        sheet_count = 0
        data_sheet_count = 0
        for sheet in workbook.find("a:sheets", NS):
            sheet_name = sheet.attrib["name"]
            sheet_count += 1
            if sheet_name == "Sheet1":
                continue
            data_sheet_count += 1
            target = targets[sheet.attrib[f"{{{NS['r']}}}id"]]
            target = target if target.startswith("xl/") else "xl/" + target
            root = ET.fromstring(archive.read(target))
            by_row = defaultdict(dict)
            for cell in root.findall(".//a:c", NS):
                ref = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)(\d+)$", ref)
                if not match:
                    continue
                row_no = int(match.group(2))
                value = read_value(cell, shared)
                formula = cell.find("a:f", NS)
                cached = value
                if value not in (None, "") or formula is not None:
                    by_row[row_no][match.group(1)] = {"value": value, "formula": formula.text if formula is not None else None, "cached": cached}
            for row_no, cells in by_row.items():
                if row_no < 4:
                    continue
                b = cells.get("B", {}).get("value")
                c = cells.get("C", {}).get("value")
                if b in (None, "") and c in (None, ""):
                    continue
                raw = {col: cells[col] for col in cells}
                qty = parse_number(cells.get("G", {}).get("value"))
                incoming = parse_number(cells.get("E", {}).get("value"))
                outgoing = parse_number(cells.get("F", {}).get("value"))
                opening = parse_number(cells.get("D", {}).get("value"))
                errors = []
                if qty is None:
                    errors.append("结存不是数字")
                if qty is not None and qty < 0:
                    errors.append("负库存")
                # Conservative field inference: only accept a code-like value as a part number.
                def looks_code(v):
                    return bool(v and re.search(r"[A-Za-z0-9]", str(v)) and not re.search(r"[\u4e00-\u9fff]", str(v)))
                if looks_code(b) and not looks_code(c):
                    part_no, part_name = str(b).strip(), c
                elif looks_code(c) and not looks_code(b):
                    part_no, part_name = str(c).strip(), b
                else:
                    part_no, part_name = None, None
                    errors.append("B/C件号件名无法唯一判断")
                rows.append({
                    "source_sheet": sheet_name,
                    "source_row": row_no,
                    "raw_data": raw,
                    "parsed_customer_part_no": part_no,
                    "parsed_customer_part_name": str(part_name).strip() if part_name not in (None, "") else None,
                    "opening_qty": opening,
                    "incoming_qty": incoming,
                    "outgoing_qty": outgoing,
                    "closing_qty": qty,
                    "location": cells.get("A", {}).get("value"),
                    "errors": errors,
                })
        return rows, sheet_count, data_sheet_count


async def main():
    content = FILE.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()
    rows, sheet_count, data_sheet_count = read_workbook()
    async with async_session_maker() as session:
        existing = await session.execute(
            text("SELECT id, status FROM import_batches WHERE file_hash = :file_hash AND file_name = :file_name ORDER BY id DESC LIMIT 1"),
            {"file_hash": file_hash, "file_name": FILE.name},
        )
        prior = existing.first()
        if prior:
            print(json.dumps({"status": "SKIPPED_EXISTING", "batch_id": prior[0], "batch_status": prior[1]}, ensure_ascii=False))
            return

        customers = (await session.execute(text("SELECT id, name, short_name, sheet_key FROM customers"))).mappings().all()
        aliases = (await session.execute(text("SELECT customer_id, part_id, customer_part_no, customer_part_name FROM part_customer_aliases"))).mappings().all()
        parts = (await session.execute(text("SELECT id, customer_id, internal_part_no, customer_part_no, customer_part_name FROM parts"))).mappings().all()
        customer_map = {}
        for customer in customers:
            for key in (customer["name"], customer["short_name"], customer["sheet_key"]):
                if key:
                    customer_map[norm(key)] = customer["id"]
            match = re.search(r"[（(]([^（）()]*)[）)]\s*$", customer["name"])
            if match:
                customer_map[norm(customer["name"][:match.start()])] = customer["id"]
        part_map = defaultdict(set)
        for row in aliases:
            for value in (row["customer_part_no"], row["customer_part_name"]):
                if value:
                    part_map[(row["customer_id"], norm(value))].add(row["part_id"])
        for row in parts:
            for value in (row["internal_part_no"], row["customer_part_no"], row["customer_part_name"]):
                if value:
                    part_map[(row["customer_id"], norm(value))].add(row["id"])

        for row in rows:
            customer_id = customer_map.get(norm(row["source_sheet"]))
            candidates = set()
            if customer_id and row["parsed_customer_part_no"]:
                candidates = part_map.get((customer_id, norm(row["parsed_customer_part_no"])), set())
            row["resolved_customer_id"] = customer_id
            row["resolved_part_id"] = next(iter(candidates)) if len(candidates) == 1 else None
            if not customer_id:
                row["errors"].append("工作表未匹配客户")
            if len(candidates) > 1:
                row["errors"].append("零件匹配歧义")
            elif len(candidates) == 0 and row["parsed_customer_part_no"]:
                row["errors"].append("零件库没有对应的件号")
            row["validation_status"] = "IMPORTED" if not row["errors"] else "REVIEW"

        valid = sum(row["validation_status"] == "IMPORTED" for row in rows)
        failed = len(rows) - valid
        batch_result = await session.execute(
            text("""INSERT INTO import_batches
                (file_name, file_hash, file_size, total_sheets, data_sheets, total_rows, valid_rows, failed_rows, status, imported_by, started_at, completed_at, created_at)
                VALUES (:file_name, :file_hash, :file_size, :total_sheets, :data_sheets, :total_rows, :valid_rows, :failed_rows, 'COMPLETED', 'system:finished_goods_snapshot:2026-09-24', :started_at, :completed_at, :created_at)
                RETURNING id"""),
            {"file_name": FILE.name, "file_hash": file_hash, "file_size": len(content), "total_sheets": sheet_count, "data_sheets": data_sheet_count, "total_rows": len(rows), "valid_rows": valid, "failed_rows": failed, "started_at": datetime.utcnow(), "completed_at": datetime.utcnow(), "created_at": datetime.utcnow()},
        )
        batch_id = batch_result.scalar_one()
        for row in rows:
            raw = dict(row["raw_data"])
            raw.update({"inventory_date": INVENTORY_DATE, "opening_qty": row["opening_qty"], "incoming_qty": row["incoming_qty"], "outgoing_qty": row["outgoing_qty"], "closing_qty": row["closing_qty"], "location": row["location"]})
            await session.execute(text("""INSERT INTO excel_import_rows
                (batch_id, source_sheet, source_row, raw_data, parsed_customer_name, parsed_customer_part_no, parsed_customer_part_name, validation_status, validation_errors, resolved_customer_id, resolved_part_id, created_at)
                VALUES (:batch_id, :source_sheet, :source_row, CAST(:raw_data AS jsonb), :customer_name, :part_no, :part_name, :status, :errors, :customer_id, :part_id, :created_at)"""),
                {"batch_id": batch_id, "source_sheet": row["source_sheet"], "source_row": row["source_row"], "raw_data": json.dumps(raw, ensure_ascii=False), "customer_name": row["source_sheet"], "part_no": row["parsed_customer_part_no"], "part_name": row["parsed_customer_part_name"], "status": row["validation_status"], "errors": ";".join(row["errors"]) if row["errors"] else None, "customer_id": row["resolved_customer_id"], "part_id": row["resolved_part_id"], "created_at": datetime.utcnow()},
            )
        await session.commit()
        print(json.dumps({"status": "COMPLETED", "batch_id": batch_id, "inventory_date": INVENTORY_DATE, "candidate_rows": len(rows), "imported_rows": valid, "review_rows": failed, "sheets": sheet_count}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())


