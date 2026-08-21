"""Import the FMG installation-kit workbook into the after-sales archive."""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook
from sqlalchemy import delete, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import get_db_context  # noqa: E402
from app.models.after_sales import (  # noqa: E402
    AfterSalesInstallationKit,
    AfterSalesKitChangeLog,
    AfterSalesKitComponent,
)

SHEET_NAME = "汇总表1"
CANONICAL_FIELDS = (
    "source_item_no",
    "description",
    "priority",
    "d_code",
    "tianyue_pn",
    "ibi_spec",
    "internal_kit_spec",
    "drawing_status",
    "sample_status",
    "ppap_status",
    "price",
    "remark",
    "source_row",
    "is_active",
)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.0001"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def prices_differ(fca_price: Any, fmg_price: Any) -> bool:
    fca = to_decimal(fca_price)
    fmg = to_decimal(fmg_price)
    return fca is not None and fmg is not None and fca != fmg


def price_mismatch_remark(fca_price: Any, fmg_price: Any) -> str | None:
    if not prices_differ(fca_price, fmg_price):
        return None
    fca = to_decimal(fca_price)
    fmg = to_decimal(fmg_price)
    return f"FMG Price 与 FCA TIANYUE Plant Price+TTOP 不一致：FMG Price USD {fmg:.4f}（FCA 为 USD {fca:.4f}）"


def json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def merge_remark(price_remark: Any, general_remark: Any, mismatch_remark: str | None = None) -> str | None:
    values = [text for value in (price_remark, general_remark, mismatch_remark) if (text := clean_text(value))]
    return "\n".join(dict.fromkeys(values)) or None


def split_components(spec: str | None) -> list[dict[str, Any]]:
    if not spec:
        return []
    normalized = re.sub(r"(?i)(pcs?)\s+(?=[A-Z]{2,}[A-Z0-9-]*\s*[×xX*])", r"\1+", spec)
    segments = [item.strip(" +") for item in re.split(r"\s*\+\s*", normalized) if item.strip(" +")]
    parsed: list[dict[str, Any]] = []
    for sequence, raw in enumerate(segments, start=1):
        quantity: Decimal | None = None
        part_number: str | None = None
        description: str | None = None
        quantity_match = re.match(
            r"^(?P<label>.+?)\s*[×xX*]\s*(?P<qty>\d+(?:\.\d+)?)"
            r"\s*(?:(?:PCS?)\s*)*(?P<note>[（(].+[）)])?$",
            raw,
            flags=re.IGNORECASE,
        )
        named_item_match = re.match(r"^(?P<qty>\d+)\s*(?:个|张)(?P<label>.+)$", raw)
        if quantity_match:
            part_number = clean_text(quantity_match.group("label"))
            quantity = Decimal(quantity_match.group("qty"))
            description = clean_text(quantity_match.group("note"))
        elif named_item_match:
            description = clean_text(named_item_match.group("label"))
            quantity = Decimal(named_item_match.group("qty"))
        elif "油脂包" in raw:
            description = raw
            quantity = Decimal("1")
        else:
            description = raw
        parsed.append(
            {
                "sequence": sequence,
                "part_number": part_number,
                "description": description,
                "quantity": quantity,
                "raw_text": raw,
            }
        )
    return parsed


def iter_records(workbook_path: Path) -> Iterable[dict[str, Any]]:
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    if SHEET_NAME not in workbook.sheetnames:
        raise ValueError(f"工作表不存在: {SHEET_NAME}")
    sheet = workbook[SHEET_NAME]
    empty_rows = 0
    started = False
    for row_number, row in enumerate(
        sheet.iter_rows(min_row=2, max_col=17, values_only=True), start=2
    ):
        fmg_code = clean_text(row[2])
        if not fmg_code:
            if started:
                empty_rows += 1
                if empty_rows >= 20:
                    break
            continue
        started = True
        empty_rows = 0
        source_data = {
            "item": json_value(row[0]),
            "tianyue_kits": json_value(row[1]),
            "fmg_code": json_value(row[2]),
            "description": json_value(row[3]),
            "priority": json_value(row[4]),
            "d_code": json_value(row[5]),
            "tianyue_pn": json_value(row[6]),
            "ibi": json_value(row[7]),
            "kits": json_value(row[8]),
            "drawing_status": json_value(row[9]),
            "sample_status": json_value(row[10]),
            "ppap": json_value(row[11]),
            "price_remarks": json_value(row[12]),
            "tianyue_plant_price": json_value(row[13]),
            "fmg_price": json_value(row[14]),
            "difference": json_value(row[15]),
            "remarks": json_value(row[16]),
            "price_mismatch": prices_differ(row[13], row[14]),
        }
        mismatch_remark = price_mismatch_remark(row[13], row[14])
        yield {
            "source_item_no": to_int(row[0]),
            "fmg_code": fmg_code,
            "description": clean_text(row[3]),
            "priority": to_int(row[4]),
            "d_code": clean_text(row[5]),
            "tianyue_pn": clean_text(row[6]),
            "ibi_spec": clean_text(row[7]),
            "internal_kit_spec": clean_text(row[8]),
            "drawing_status": clean_text(row[9]),
            "sample_status": clean_text(row[10]),
            "ppap_status": clean_text(row[11]),
            "price": to_decimal(row[13]),
            "remark": merge_remark(row[12], row[16], mismatch_remark),
            "source_data": source_data,
            "source_file_name": workbook_path.name,
            "source_sheet": SHEET_NAME,
            "source_row": row_number,
            "is_active": True,
        }


async def import_workbook(workbook_path: Path) -> dict[str, int]:
    records = list(iter_records(workbook_path))
    codes = [record["fmg_code"] for record in records]
    if len(records) != len(set(codes)):
        raise ValueError("Excel 中存在重复 FMG CODE，导入已中止")

    created = 0
    updated = 0
    unchanged = 0
    component_count = 0
    async with get_db_context() as db:
        result = await db.execute(
            select(AfterSalesInstallationKit).where(AfterSalesInstallationKit.fmg_code.in_(codes))
        )
        existing_by_code = {item.fmg_code: item for item in result.scalars()}
        for record in records:
            kit = existing_by_code.get(record["fmg_code"])
            is_new = kit is None
            if is_new:
                kit = AfterSalesInstallationKit(**record)
                db.add(kit)
                await db.flush()
                changed_fields = list(CANONICAL_FIELDS)
                created += 1
            else:
                changed_fields = [
                    field for field in CANONICAL_FIELDS if getattr(kit, field) != record[field]
                ]
                for field in changed_fields:
                    setattr(kit, field, record[field])
                if changed_fields:
                    kit.source_data = record["source_data"]
                    kit.source_file_name = record["source_file_name"]
                    kit.source_sheet = record["source_sheet"]
                    updated += 1
                else:
                    unchanged += 1

            component_fields_changed = is_new or bool(
                {"ibi_spec", "internal_kit_spec"}.intersection(changed_fields)
            )
            if component_fields_changed:
                if not is_new:
                    await db.execute(
                        delete(AfterSalesKitComponent).where(AfterSalesKitComponent.kit_id == kit.id)
                    )
                for source_kind, spec in (
                    ("ibi", record["ibi_spec"]),
                    ("internal", record["internal_kit_spec"]),
                ):
                    for component in split_components(spec):
                        db.add(AfterSalesKitComponent(kit_id=kit.id, source_kind=source_kind, **component))
                        component_count += 1

            if is_new or changed_fields:
                db.add(
                    AfterSalesKitChangeLog(
                        kit_id=kit.id,
                        action="import_created" if is_new else "import_updated",
                        summary="从 FMG Excel 建档" if is_new else "按 FMG Excel 更新档案",
                        changed_fields=changed_fields,
                        source_file_name=workbook_path.name,
                    )
                )
        await db.flush()
    return {
        "records": len(records),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "components_written": component_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="FMG Excel 文件路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workbook_path = args.workbook.resolve()
    if not workbook_path.is_file():
        raise FileNotFoundError(workbook_path)
    result = asyncio.run(import_workbook(workbook_path))
    print(result)


if __name__ == "__main__":
    main()
