"""Repair source-backed T/W/P values for explicitly prefixed Excel specs.

Dry-run is the default and writes a rollback report containing every old value
that would be changed.  ``--apply --report <dry-run-report>`` applies exactly
that report with optimistic before-value checks.  The script never changes
customer, tooling, legacy part fields, validation status, or ``is_primary``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import xlrd
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
import sys

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import async_session_maker  # noqa: E402
from app.models.excel_import import ExcelImportRow  # noqa: E402
from app.models.part_tooling_spec import PartToolingSpec  # noqa: E402
from scripts.import_excel_authoritative import (  # noqa: E402
    _SPEC_PREFIX_RE,
    detect_headers,
    parse_combined_spec,
)


REPORT_VERSION = 1
DEFAULT_EXCEL_PATH = BACKEND_DIR.parent / "excel" / "五金模具及产品清单表.xls"


def decimal_text(value: Decimal | float | int | str | None) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)).normalize(), "f")


def tuple_text(values: tuple[Any, Any, Any]) -> list[str | None]:
    return [decimal_text(value) for value in values]


def parsed_tuple(row: ExcelImportRow) -> tuple[Any, Any, Any]:
    return row.parsed_thickness, row.parsed_width, row.parsed_pitch


def format_spec_values(values: tuple[Any, Any, Any]) -> str | None:
    """Format T/W/P with the same partial-spec convention as the importer."""
    thickness, width, pitch = (decimal_text(value) for value in values)
    if thickness is None and width is None and pitch is None:
        return None
    parts: list[str] = []
    if thickness is not None:
        parts.append(thickness)
    if width is not None:
        parts.append(width)
    elif pitch is not None:
        parts.append("-")
    if pitch is not None:
        parts.append(pitch)
    return "*".join(parts)


def load_sheet_spec_map(excel_path: Path) -> tuple[dict[str, dict[str, int]], list[str]]:
    """Read-only map of source sheet name to its authoritative spec column."""
    if not excel_path.exists():
        raise FileNotFoundError(f"authoritative Excel not found: {excel_path}")

    workbook = xlrd.open_workbook(str(excel_path), formatting_info=True)
    sheet_map: dict[str, dict[str, int]] = {}
    sheets_without_spec: list[str] = []
    for sheet_index in range(workbook.nsheets):
        sheet = workbook.sheet_by_index(sheet_index)
        header_row, column_map = detect_headers(sheet)
        spec_col = column_map.get("spec")
        if header_row is None or spec_col is None:
            sheets_without_spec.append(sheet.name)
            continue
        sheet_map[sheet.name] = {
            "header_row": header_row,
            "spec_col": spec_col,
        }
    return sheet_map, sheets_without_spec


def prefixed_spec_value(
    raw_data: Any,
    source_sheet: str,
    source_row: int,
    sheet_map: dict[str, dict[str, int]],
) -> tuple[dict[str, Any] | None, str | None]:
    """Read only raw_data[spec_col] for the matching authoritative sheet."""
    mapping = sheet_map.get(source_sheet)
    if mapping is None:
        return None, "source_sheet_or_spec_column_not_mapped"
    if not isinstance(raw_data, list):
        return None, "raw_data_not_row_array"
    spec_col = mapping["spec_col"]
    if spec_col >= len(raw_data):
        return None, "raw_data_missing_spec_column"

    raw_value = raw_data[spec_col]
    if not isinstance(raw_value, str):
        return None, None
    value = raw_value.strip()
    if not _SPEC_PREFIX_RE.match(value):
        return None, None
    parsed = parse_combined_spec(value)
    if not any(item is not None for item in parsed):
        return None, "prefixed_spec_did_not_parse"
    return {
        "raw_index": spec_col,
        "raw_spec": value,
        "parsed": tuple_text(parsed),
        "header_row": mapping["header_row"],
        "source_row": source_row,
    }, None


def same_values(current: tuple[Any, Any, Any], expected: list[str | None]) -> bool:
    return tuple_text(current) == expected


def load_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("report_version") != REPORT_VERSION or report.get("mode") != "dry_run":
        raise ValueError("report is not a compatible dry-run repair report")
    return report


async def build_report(excel_path: Path) -> dict[str, Any]:
    sheet_map, sheets_without_spec = load_sheet_spec_map(excel_path)
    invalid_prefixed_rows: list[dict[str, Any]] = []
    unmapped_rows = 0
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(ExcelImportRow)
                .where(ExcelImportRow.validation_status == "IMPORTED")
                .order_by(ExcelImportRow.id)
            )
        ).scalars().all()

        source_rows: list[dict[str, Any]] = []
        for row in rows:
            match, read_error = prefixed_spec_value(
                row.raw_data,
                row.source_sheet,
                row.source_row,
                sheet_map,
            )
            if read_error == "source_sheet_or_spec_column_not_mapped":
                unmapped_rows += 1
                continue
            if read_error == "prefixed_spec_did_not_parse":
                invalid_prefixed_rows.append(
                    {
                        "excel_import_row_id": row.id,
                        "source_sheet": row.source_sheet,
                        "source_row": row.source_row,
                    }
                )
                continue
            if match is None:
                continue

            matches = [match]
            # Keep the canonical representation as a list, matching
            # ``tuple_text`` and the JSON report format.  Comparing a tuple
            # with the equivalent list would otherwise make every already
            # repaired row look like a fresh candidate on every dry-run.
            new_values = list(match["parsed"])
            pts_rows = (
                await session.execute(
                    select(PartToolingSpec)
                    .where(
                        PartToolingSpec.source_sheet == row.source_sheet,
                        PartToolingSpec.source_row == row.source_row,
                    )
                    .order_by(PartToolingSpec.id)
                )
            ).scalars().all()

            current_values = parsed_tuple(row)
            pts_changes: list[dict[str, Any]] = []
            for spec in pts_rows:
                old_values = tuple_text((spec.thickness, spec.width, spec.pitch))
                old_spec = spec.spec_twph
                new_spec = format_spec_values(tuple(Decimal(v) if v is not None else None for v in new_values))
                if old_values != new_values or old_spec != new_spec:
                    pts_changes.append(
                        {
                            "id": spec.id,
                            "part_id": spec.part_id,
                            "tooling_id": spec.tooling_id,
                            "old_values": old_values,
                            "old_spec_twph": old_spec,
                            "new_values": new_values,
                            "new_spec_twph": new_spec,
                            "is_primary": bool(spec.is_primary),
                            "action": "update",
                        }
                    )

            insert_change: dict[str, Any] | None = None
            if not pts_rows and row.resolved_part_id is not None and row.resolved_tooling_id is not None:
                insert_change = {
                    "part_id": row.resolved_part_id,
                    "tooling_id": row.resolved_tooling_id,
                    "old_values": None,
                    "old_spec_twph": None,
                    "new_values": new_values,
                    "new_spec_twph": format_spec_values(
                        tuple(Decimal(v) if v is not None else None for v in new_values)
                    ),
                    "is_primary": False,
                    "action": "insert",
                }

            row_changed = not same_values(current_values, new_values)
            if row_changed or pts_changes or insert_change:
                source_rows.append(
                    {
                        "excel_import_row_id": row.id,
                        "source_sheet": row.source_sheet,
                        "source_row": row.source_row,
                        "resolved_part_id": row.resolved_part_id,
                        "resolved_tooling_id": row.resolved_tooling_id,
                        "matches": matches,
                        "old_row_values": tuple_text(current_values),
                        "new_row_values": new_values,
                        "row_action": "update" if row_changed else "none",
                        "validation_status": row.validation_status,
                        "pts_changes": pts_changes,
                        "pts_insert": insert_change,
                    }
                )

        blocked = [item for item in source_rows if item.get("blocked_reason")]
        candidates = [item for item in source_rows if not item.get("blocked_reason")]
        return {
            "report_version": REPORT_VERSION,
            "mode": "dry_run",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "authoritative_excel": str(excel_path),
            "mapped_spec_sheets": len(sheet_map),
            "sheets_without_spec_column": sheets_without_spec,
            "scope": {
                "validation_status": "IMPORTED",
                "prefix_rule": _SPEC_PREFIX_RE.pattern,
                "updated_excel_fields": [
                    "parsed_thickness",
                    "parsed_width",
                    "parsed_pitch",
                ],
                "updated_part_tooling_fields": [
                    "thickness",
                    "width",
                    "pitch",
                    "spec_twph",
                ],
                "untouched_fields": [
                    "customer_fields",
                    "tooling_fields",
                    "parts legacy fields",
                    "validation_status",
                    "is_primary",
                ],
            },
            "scanned_imported_rows": len(rows),
            "rows_on_unmapped_sheets": unmapped_rows,
            "invalid_prefixed_rows": invalid_prefixed_rows,
            "matched_prefixed_rows": len(source_rows),
            "blocked_rows": len(blocked),
            "candidate_rows": len(candidates),
            "excel_rows_to_update": sum(item.get("row_action") == "update" for item in candidates),
            "part_tooling_specs_to_update": sum(len(item["pts_changes"]) for item in candidates),
            "part_tooling_specs_to_insert": sum(item["pts_insert"] is not None for item in candidates),
            "candidates": candidates,
            "blocked": blocked,
        }


async def apply_report(report: dict[str, Any]) -> dict[str, int]:
    candidates = report.get("candidates", [])
    updated_rows = 0
    updated_specs = 0
    inserted_specs = 0

    async with async_session_maker() as session:
        for item in candidates:
            row = await session.get(ExcelImportRow, item["excel_import_row_id"])
            if row is None:
                raise RuntimeError(f"excel_import_row missing: {item['excel_import_row_id']}")
            if row.source_sheet != item["source_sheet"] or row.source_row != item["source_row"]:
                raise RuntimeError(f"source identity changed for excel_import_row {row.id}")
            if not same_values(parsed_tuple(row), item["old_row_values"]):
                raise RuntimeError(f"before-value mismatch for excel_import_row {row.id}")

            if item.get("row_action") == "update":
                new_values = item["new_row_values"]
                row.parsed_thickness = Decimal(new_values[0]) if new_values[0] is not None else None
                row.parsed_width = Decimal(new_values[1]) if new_values[1] is not None else None
                row.parsed_pitch = Decimal(new_values[2]) if new_values[2] is not None else None
                updated_rows += 1

            for change in item.get("pts_changes", []):
                spec = await session.get(PartToolingSpec, change["id"])
                if spec is None:
                    raise RuntimeError(f"part_tooling_spec missing: {change['id']}")
                if spec.source_sheet != item["source_sheet"] or spec.source_row != item["source_row"]:
                    raise RuntimeError(f"source identity changed for part_tooling_spec {spec.id}")
                if tuple_text((spec.thickness, spec.width, spec.pitch)) != change["old_values"]:
                    raise RuntimeError(f"before-value mismatch for part_tooling_spec {spec.id}")
                if spec.spec_twph != change["old_spec_twph"]:
                    raise RuntimeError(f"before-value mismatch for spec_twph {spec.id}")
                new_values = change["new_values"]
                spec.thickness = Decimal(new_values[0]) if new_values[0] is not None else None
                spec.width = Decimal(new_values[1]) if new_values[1] is not None else None
                spec.pitch = Decimal(new_values[2]) if new_values[2] is not None else None
                spec.spec_twph = change["new_spec_twph"]
                updated_specs += 1

            insert = item.get("pts_insert")
            if insert is not None:
                existing = (
                    await session.execute(
                        select(PartToolingSpec.id).where(
                            PartToolingSpec.source_sheet == item["source_sheet"],
                            PartToolingSpec.source_row == item["source_row"],
                        )
                    )
                ).scalars().first()
                if existing is not None:
                    raise RuntimeError(
                        f"part_tooling_spec appeared before insert for {item['source_sheet']}[{item['source_row']}]"
                    )
                new_values = insert["new_values"]
                session.add(
                    PartToolingSpec(
                        part_id=insert["part_id"],
                        tooling_id=insert["tooling_id"],
                        spec_twph=insert["new_spec_twph"],
                        thickness=Decimal(new_values[0]) if new_values[0] is not None else None,
                        width=Decimal(new_values[1]) if new_values[1] is not None else None,
                        pitch=Decimal(new_values[2]) if new_values[2] is not None else None,
                        source_sheet=item["source_sheet"],
                        source_row=item["source_row"],
                    )
                )
                inserted_specs += 1

        await session.commit()

    return {
        "excel_rows_updated": updated_rows,
        "part_tooling_specs_updated": updated_specs,
        "part_tooling_specs_inserted": inserted_specs,
        "primary_changed": 0,
    }


async def verify_sample(part_id: int, source_sheet: str, source_row: int) -> dict[str, Any]:
    async with async_session_maker() as session:
        row = (
            await session.execute(
                select(ExcelImportRow).where(
                    ExcelImportRow.source_sheet == source_sheet,
                    ExcelImportRow.source_row == source_row,
                    ExcelImportRow.resolved_part_id == part_id,
                )
            )
        ).scalars().all()
        specs = (
            await session.execute(
                select(PartToolingSpec)
                .where(
                    PartToolingSpec.source_sheet == source_sheet,
                    PartToolingSpec.source_row == source_row,
                )
                .order_by(PartToolingSpec.id)
            )
        ).scalars().all()
        return {
            "part_id": part_id,
            "source_sheet": source_sheet,
            "source_row": source_row,
            "excel_rows": [
                {
                    "id": item.id,
                    "parsed_thickness": decimal_text(item.parsed_thickness),
                    "parsed_width": decimal_text(item.parsed_width),
                    "parsed_pitch": decimal_text(item.parsed_pitch),
                    "validation_status": item.validation_status,
                }
                for item in row
            ],
            "part_tooling_specs": [
                {
                    "id": item.id,
                    "part_id": item.part_id,
                    "tooling_id": item.tooling_id,
                    "thickness": decimal_text(item.thickness),
                    "width": decimal_text(item.width),
                    "pitch": decimal_text(item.pitch),
                    "spec_twph": item.spec_twph,
                    "is_primary": bool(item.is_primary),
                }
                for item in specs
            ],
        }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, help="dry-run report to apply")
    parser.add_argument("--excel", type=Path, default=DEFAULT_EXCEL_PATH)
    parser.add_argument("--verify-part-id", type=int)
    parser.add_argument("--verify-source-sheet")
    parser.add_argument("--verify-source-row", type=int)
    args = parser.parse_args()

    if args.verify_part_id is not None:
        if not args.verify_source_sheet or args.verify_source_row is None:
            parser.error("--verify requires --verify-source-sheet and --verify-source-row")
        print(json.dumps(await verify_sample(args.verify_part_id, args.verify_source_sheet, args.verify_source_row), ensure_ascii=False))
        return 0

    if args.apply:
        if not args.report:
            parser.error("--apply requires the dry-run --report path")
        report = load_report(args.report)
        result = await apply_report(report)
        print(json.dumps({"mode": "apply", **result}, ensure_ascii=False))
        return 0

    report = await build_report(args.excel)
    report_path = args.report or (
        BACKEND_DIR.parent
        / "reports"
        / f"chinese_prefixed_twp_repair_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {key: value for key, value in report.items() if key not in {"candidates", "blocked"}}
    print(json.dumps({"mode": "dry_run", **summary, "report": str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
