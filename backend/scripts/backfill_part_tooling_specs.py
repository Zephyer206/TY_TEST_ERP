"""Backfill source-backed TWP options without overwriting legacy part fields.

The dry-run mode is the default.  ``--apply`` inserts one option per imported
source row and automatically marks a part's sole option as primary.  Parts with
multiple distinct options remain unselected until a user chooses the primary
specification in the ERP UI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
import sys

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import async_session_maker  # noqa: E402
from app.models.excel_import import ExcelImportRow  # noqa: E402
from app.models.part_tooling_spec import PartToolingSpec  # noqa: E402


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS part_tooling_specs (
    id SERIAL PRIMARY KEY,
    part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    tooling_id INTEGER NOT NULL REFERENCES tooling(id) ON DELETE CASCADE,
    spec_twph VARCHAR(100),
    thickness NUMERIC(10, 3),
    width NUMERIC(10, 3),
    pitch NUMERIC(10, 3),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    source_sheet VARCHAR(200),
    source_row INTEGER,
    source_note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
)
"""


def format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


def format_spec(row: ExcelImportRow) -> str | None:
    values = (row.parsed_thickness, row.parsed_width, row.parsed_pitch)
    if any(value is None for value in values):
        return None
    return "*".join(format_decimal(value) or "" for value in values)


async def build_report() -> dict[str, Any]:
    async with async_session_maker() as session:
        source_rows = (
            await session.execute(
                select(ExcelImportRow)
                .where(
                    ExcelImportRow.validation_status == "IMPORTED",
                    ExcelImportRow.resolved_part_id.is_not(None),
                    ExcelImportRow.resolved_tooling_id.is_not(None),
                    ExcelImportRow.parsed_thickness.is_not(None),
                    ExcelImportRow.parsed_width.is_not(None),
                    ExcelImportRow.parsed_pitch.is_not(None),
                )
                .order_by(ExcelImportRow.id)
            )
        ).scalars().all()

        try:
            existing_rows = (await session.execute(select(PartToolingSpec))).scalars().all()
        except Exception:
            existing_rows = []

    existing_keys = {
        (
            spec.part_id,
            spec.tooling_id,
            spec.source_sheet,
            spec.source_row,
            str(spec.thickness),
            str(spec.width),
            str(spec.pitch),
        )
        for spec in existing_rows
    }
    candidates: list[dict[str, Any]] = []
    distinct_by_part: dict[int, set[tuple[str, str, str]]] = defaultdict(set)
    for row in source_rows:
        key = (
            row.resolved_part_id,
            row.resolved_tooling_id,
            row.source_sheet,
            row.source_row,
            str(row.parsed_thickness),
            str(row.parsed_width),
            str(row.parsed_pitch),
        )
        option_key = (
            str(row.parsed_thickness),
            str(row.parsed_width),
            str(row.parsed_pitch),
        )
        distinct_by_part[row.resolved_part_id].add(option_key)
        if key in existing_keys:
            continue
        candidates.append(
            {
                "part_id": row.resolved_part_id,
                "tooling_id": row.resolved_tooling_id,
                "spec_twph": format_spec(row),
                "thickness": str(row.parsed_thickness),
                "width": str(row.parsed_width),
                "pitch": str(row.parsed_pitch),
                "source_sheet": row.source_sheet,
                "source_row": row.source_row,
            }
        )

    conflict_parts = sum(1 for values in distinct_by_part.values() if len(values) > 1)
    sole_option_parts = sum(1 for values in distinct_by_part.values() if len(values) == 1)
    return {
        "source_rows": len(source_rows),
        "existing_options": len(existing_rows),
        "candidate_options": len(candidates),
        "parts_with_options": len(distinct_by_part),
        "sole_option_parts": sole_option_parts,
        "conflict_parts": conflict_parts,
        "candidates": candidates,
    }


async def apply_report(report: dict[str, Any]) -> dict[str, int]:
    async with async_session_maker() as session:
        await session.execute(text(CREATE_TABLE_SQL))
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_part_tooling_specs_part_id "
                "ON part_tooling_specs (part_id)"
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_part_tooling_specs_tooling_id "
                "ON part_tooling_specs (tooling_id)"
            )
        )
        await session.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_part_tooling_specs_primary "
                "ON part_tooling_specs (part_id) WHERE is_primary"
            )
        )

        inserted = 0
        for item in report["candidates"]:
            thickness = Decimal(item["thickness"])
            width = Decimal(item["width"])
            pitch = Decimal(item["pitch"])
            exists = await session.scalar(
                select(PartToolingSpec.id).where(
                    PartToolingSpec.part_id == item["part_id"],
                    PartToolingSpec.tooling_id == item["tooling_id"],
                    PartToolingSpec.source_sheet == item["source_sheet"],
                    PartToolingSpec.source_row == item["source_row"],
                    PartToolingSpec.thickness == thickness,
                    PartToolingSpec.width == width,
                    PartToolingSpec.pitch == pitch,
                )
            )
            if exists:
                continue
            session.add(
                PartToolingSpec(
                    part_id=item["part_id"],
                    tooling_id=item["tooling_id"],
                    spec_twph=item["spec_twph"],
                    thickness=thickness,
                    width=width,
                    pitch=pitch,
                    source_sheet=item["source_sheet"],
                    source_row=item["source_row"],
                )
            )
            inserted += 1

        await session.flush()
        grouped = defaultdict(list)
        for spec in (await session.execute(select(PartToolingSpec))).scalars().all():
            grouped[spec.part_id].append(spec)

        primary_assigned = 0
        for specs in grouped.values():
            if any(spec.is_primary for spec in specs):
                continue
            distinct = {
                (str(spec.thickness), str(spec.width), str(spec.pitch))
                for spec in specs
            }
            if len(distinct) == 1 and len(specs) >= 1:
                specs[0].is_primary = True
                primary_assigned += 1

        await session.commit()
        return {"inserted": inserted, "primary_assigned": primary_assigned}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=BACKEND_DIR.parent / "reports" / "part_tooling_specs_dry_run.json",
    )
    args = parser.parse_args()

    report = await build_report()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.apply:
        result = await apply_report(report)
        print(json.dumps({"mode": "apply", **result, **{k: v for k, v in report.items() if k != "candidates"}}, ensure_ascii=False))
    else:
        print(json.dumps({"mode": "dry_run", **{k: v for k, v in report.items() if k != "candidates"}, "report": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
