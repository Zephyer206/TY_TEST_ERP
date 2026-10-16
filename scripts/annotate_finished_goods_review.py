import csv
import os
import re
import shutil
from collections import defaultdict
from copy import copy
from pathlib import Path

import psycopg2
from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "excel" / "成品库报表2026.9.xlsm"
QUEUE = ROOT / "docs" / "finished_goods_review_queue_2026-09-24.csv"
OUTPUT = ROOT / "excel" / "成品库报表2026.9_审核标注_20260924.xlsm"
AMBIGUITY_CSV = ROOT / "docs" / "finished_goods_ambiguity_queue_2026-09-24.csv"
CUSTOMER_CSV = ROOT / "docs" / "finished_goods_customer_review_queue_2026-09-24.csv"
CROSS_CUSTOMER_CSV = ROOT / "docs" / "finished_goods_cross_customer_review_2026-09-24.csv"

CUSTOMER_MARKER = "工作表未匹配客户"
AMBIGUITY_MARKER = "零件匹配歧义"
UNMATCHED_MARKERS = ("零件库没有对应的件号", "未匹配现有零件")
CUSTOMER_TOOLTIP = "工作表未匹配正式客户，暂不能确认零件归属"
AMBIGUITY_TOOLTIP = "系统存在多个对应内部零件，请人工选择"
UNMATCHED_TOOLTIP = "零件库没有对应的件号"
CROSS_CUSTOMER_TOOLTIP = "系统在其他客户下找到同件号候选，当前客户归属无法自动确认；请仓库人员现场核对实物标签、包装和客户区域后再处理"


def norm(value):
    return re.sub(r"[\s\u3000]+", "", str(value or "")).casefold()


def db_url():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].replace("postgresql+asyncpg://", "postgresql://", 1)
    raise RuntimeError("DATABASE_URL not found")


def part_column(row):
    part_no = (row.get("规范化件号") or "").strip()
    raw_b = (row.get("原始B") or "").strip()
    raw_c = (row.get("原始C") or "").strip()
    if part_no and raw_b == part_no:
        return "B"
    if part_no and raw_c == part_no:
        return "C"
    return "B" if raw_b else "C"


def load_db_data():
    conn = psycopg2.connect(db_url())
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM customers")
    customers = dict(cur.fetchall())
    cur.execute("SELECT id, customer_id, internal_part_no, customer_part_no, customer_part_name, internal_name, status, is_deleted FROM parts")
    parts = {row[0]: row for row in cur.fetchall()}
    cur.execute("SELECT customer_id, part_id, customer_part_no, customer_part_name FROM part_customer_aliases")
    aliases = cur.fetchall()
    cur.close()
    conn.close()
    by_key = defaultdict(set)
    for customer_id, part_id, part_no, part_name in aliases:
        for value in (part_no, part_name):
            if value:
                by_key[(customer_id, norm(value))].add(part_id)
    for part_id, customer_id, internal_no, part_no, part_name, internal_name, status, is_deleted in parts.values():
        for value in (internal_no, part_no, part_name):
            if value:
                by_key[(customer_id, norm(value))].add(part_id)
    by_customer_part = defaultdict(set)
    for part_id, customer_id, internal_no, part_no, part_name, internal_name, status, is_deleted in parts.values():
        for value in (internal_no, part_no):
            if value:
                by_customer_part[norm(value)].add(customer_id)
    for customer_id, part_id, part_no, part_name in aliases:
        if part_no:
            by_customer_part[norm(part_no)].add(customer_id)
    return customers, parts, by_key, by_customer_part


def build_review_reports():
    customers, parts, by_key, by_customer_part = load_db_data()
    conn = psycopg2.connect(db_url())
    cur = conn.cursor()
    cur.execute("""SELECT id, source_sheet, source_row, resolved_customer_id,
                          parsed_customer_part_no, parsed_customer_part_name,
                          raw_data, validation_errors
                   FROM excel_import_rows
                   WHERE batch_id=8 AND validation_errors IS NOT NULL
                   ORDER BY source_sheet, source_row""")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    with AMBIGUITY_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["导入记录ID", "工作表", "源行号", "客户ID", "客户件号", "零件名", "结存数量", "库位", "候选内部零件数", "候选内部零件"])
        for row_id, sheet, source_row, customer_id, part_no, part_name, raw, errors in rows:
            if AMBIGUITY_MARKER not in (errors or ""):
                continue
            raw = raw or {}
            candidates = sorted(by_key.get((customer_id, norm(part_no)), set()))
            detail = []
            for part_id in candidates:
                part = parts[part_id]
                detail.append("|".join(str(v or "") for v in (part[0], part[2], part[3], part[4], part[5])))
            writer.writerow([row_id, sheet, source_row, customer_id, part_no, part_name, raw.get("closing_qty"), raw.get("location"), len(candidates), "; ".join(detail)])

    with CUSTOMER_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["导入记录ID", "工作表", "源行号", "客户件号", "零件名", "结存数量", "库位", "候选客户数", "候选客户"])
        for row_id, sheet, source_row, customer_id, part_no, part_name, raw, errors in rows:
            if CUSTOMER_MARKER not in (errors or ""):
                continue
            raw = raw or {}
            candidate_ids = sorted(by_customer_part.get(norm(part_no), set())) if part_no else []
            candidate_names = [f"{cid}:{customers.get(cid, '')}" for cid in candidate_ids]
            writer.writerow([row_id, sheet, source_row, part_no, part_name, raw.get("closing_qty"), raw.get("location"), len(candidate_ids), "; ".join(candidate_names)])

    return sum(1 for row in rows if CUSTOMER_MARKER in (row[7] or "")), sum(1 for row in rows if AMBIGUITY_MARKER in (row[7] or ""))


def annotate_workbook():
    if OUTPUT.exists():
        os.chmod(OUTPUT, 0o666)
    shutil.copy2(SOURCE, OUTPUT)
    os.chmod(OUTPUT, 0o666)
    workbook = load_workbook(OUTPUT, keep_vba=True)
    orange_fill = PatternFill(fill_type="solid", fgColor="FCE4D6")
    yellow_fill = PatternFill(fill_type="solid", fgColor="FFF2CC")
    red_fill = PatternFill(fill_type="solid", fgColor="FFC7CE")
    blue_fill = PatternFill(fill_type="solid", fgColor="DDEBF7")
    counts = {"customer": 0, "ambiguity": 0, "unmatched": 0, "cross_customer": 0}
    with QUEUE.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            errors = row.get("系统错误") or ""
            if not (row.get("规范化件号") or "").strip():
                continue
            sheet_name = row.get("工作表") or ""
            if sheet_name not in workbook.sheetnames:
                continue
            cell = workbook[sheet_name][f"{part_column(row)}{int(row['源行号'])}"]
            font = copy(cell.font)
            if CUSTOMER_MARKER in errors:
                cell.fill = copy(orange_fill)
                font.color = "C65911"
                cell.font = font
                cell.comment = Comment(CUSTOMER_TOOLTIP, "ZephyrERP")
                counts["customer"] += 1
            elif AMBIGUITY_MARKER in errors:
                cell.fill = copy(yellow_fill)
                font.color = "9C6500"
                cell.font = font
                cell.comment = Comment(AMBIGUITY_TOOLTIP, "ZephyrERP")
                counts["ambiguity"] += 1
            elif any(marker in errors for marker in UNMATCHED_MARKERS):
                cell.fill = copy(red_fill)
                font.color = "9C0006"
                cell.font = font
                cell.comment = Comment(UNMATCHED_TOOLTIP, "ZephyrERP")
                counts["unmatched"] += 1
    with CROSS_CUSTOMER_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            sheet_name = row.get("工作表") or ""
            if sheet_name not in workbook.sheetnames:
                continue
            if not (row.get("当前客户ID") or "").strip():
                # Customer identity must be resolved before a cross-customer hint is useful.
                continue
            part_no = (row.get("件号") or "").strip()
            if not part_no:
                continue
            sheet = workbook[sheet_name]
            source_row = int(row["源行号"])
            if str(sheet[f"B{source_row}"].value or "").strip() == part_no:
                cell = sheet[f"B{source_row}"]
            elif str(sheet[f"C{source_row}"].value or "").strip() == part_no:
                cell = sheet[f"C{source_row}"]
            else:
                continue
            font = copy(cell.font)
            cell.fill = copy(blue_fill)
            font.color = "1F4E78"
            font.bold = True
            cell.font = font
            candidate_text = (row.get("候选内部零件") or "").replace("; ", "；")
            cell.comment = Comment(
                f"{CROSS_CUSTOMER_TOOLTIP}。候选：{candidate_text}",
                "ZephyrERP",
            )
            counts["cross_customer"] += 1
    workbook.save(OUTPUT)
    return counts


def main():
    customer_rows, ambiguity_rows = build_review_reports()
    counts = annotate_workbook()
    print({
        "customer_review_rows": customer_rows,
        "ambiguity_rows": ambiguity_rows,
        "customer_report": str(CUSTOMER_CSV),
        "ambiguity_report": str(AMBIGUITY_CSV),
        "annotated_workbook": str(OUTPUT),
        "marked": counts,
    })


if __name__ == "__main__":
    main()
