"""Read-only audit for legacy part-level specification fields."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine, get_db_context  # noqa: E402


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalize_spec(value: Any) -> str | None:
    if not has_text(value):
        return None
    result = str(value).strip().replace(" ", "").replace("×", "*").replace("x", "*")
    while "**" in result:
        result = result.replace("**", "*")
    return result.casefold()


def is_test_record(part_number: str | None, internal_name: str | None) -> bool:
    number = (part_number or "").upper()
    if number.startswith(("TEST-", "CODEX-TEST-")):
        return True
    return not number and (internal_name or "") in {
        "Test Part",
        "Test Part Original",
        "Test Part Updated",
        "Updated Name",
        "Should Not Save",
        "Modified by Another User",
    }


def dimensions_key(row: dict[str, Any], prefix: str = "") -> tuple[Decimal | None, ...]:
    return (
        row[f"{prefix}thickness"],
        row[f"{prefix}width"],
        row[f"{prefix}pitch"],
    )


def has_dimensions(values: tuple[Decimal | None, ...]) -> bool:
    return any(value is not None for value in values)


def compatible_source_dimensions(
    legacy: tuple[Decimal | None, ...],
    source: tuple[Decimal | None, ...],
) -> bool:
    """Return whether a source row can verify the legacy non-null fields.

    A source row is evidence only when every legacy value is present in the
    source and equal.  Legacy NULLs may be completed by the source, but a
    source NULL cannot verify a legacy value.
    """

    return all(
        legacy_value is None
        or (source_value is not None and source_value == legacy_value)
        for legacy_value, source_value in zip(legacy, source)
    )


def completed_dimensions(
    legacy: tuple[Decimal | None, ...],
    source: tuple[Decimal | None, ...],
) -> tuple[Decimal | None, ...]:
    return tuple(
        source_value if legacy_value is None else legacy_value
        for legacy_value, source_value in zip(legacy, source)
    )


def source_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "tooling_number": row.get("tooling_number"),
        "source_sheet": row.get("source_sheet"),
        "source_row": row.get("source_row"),
    }


async def build_report() -> dict[str, Any]:
    async with get_db_context() as db:
        parts = (
            await db.execute(
                text(
                    """
                    SELECT id, part_number, internal_name, spec_info, spec_twph,
                           thickness, width, pitch, height
                    FROM parts
                    WHERE is_deleted = FALSE
                      AND (
                          NULLIF(BTRIM(spec_info), '') IS NOT NULL
                          OR NULLIF(BTRIM(spec_twph), '') IS NOT NULL
                          OR thickness IS NOT NULL
                          OR width IS NOT NULL
                          OR pitch IS NOT NULL
                          OR height IS NOT NULL
                      )
                    ORDER BY part_number NULLS LAST, id
                    """
                )
            )
        ).mappings().all()
        tooling_specs = (
            await db.execute(
                text(
                    """
                    SELECT pts.part_id, pts.spec_twph, pts.thickness, pts.width, pts.pitch,
                           pts.source_sheet, pts.source_row,
                           COALESCE(t.tooling_number, t.tooling_no) AS tooling_number
                    FROM part_tooling_specs pts
                    LEFT JOIN tooling t ON t.id = pts.tooling_id
                    """
                )
            )
        ).mappings().all()
        excel_rows = (
            await db.execute(
                text(
                    """
                    SELECT e.resolved_part_id AS part_id, e.resolved_tooling_id AS tooling_id,
                           e.source_sheet, e.source_row,
                           e.parsed_thickness, e.parsed_width, e.parsed_pitch,
                           COALESCE(t.tooling_number, t.tooling_no) AS tooling_number
                    FROM excel_import_rows e
                    LEFT JOIN tooling t ON t.id = e.resolved_tooling_id
                    WHERE e.validation_status = 'IMPORTED'
                      AND e.resolved_part_id IS NOT NULL
                    ORDER BY e.source_sheet, e.source_row, e.id
                    """
                )
            )
        ).mappings().all()
        tooling_links = (
            await db.execute(
                text(
                    """
                    SELECT tp.part_id, COALESCE(t.tooling_number, t.tooling_no) AS tooling_number,
                           tp.is_primary
                    FROM tooling_parts tp
                    LEFT JOIN tooling t ON t.id = tp.tooling_id
                    ORDER BY tp.part_id, tp.is_primary DESC, tooling_number
                    """
                )
            )
        ).mappings().all()

    specs_by_part: dict[int, list[dict[str, Any]]] = defaultdict(list)
    excel_by_part: dict[int, list[dict[str, Any]]] = defaultdict(list)
    links_by_part: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tooling_specs:
        specs_by_part[row["part_id"]].append(dict(row))
    for row in excel_rows:
        excel_by_part[row["part_id"]].append(dict(row))
    for row in tooling_links:
        links_by_part[row["part_id"]].append(dict(row))

    items: list[dict[str, Any]] = []
    twp_summary: Counter[str] = Counter()
    spec_info_summary: Counter[str] = Counter()
    for part in parts:
        part_id = part["id"]
        part_number = part["part_number"] or ""
        test_record = is_test_record(part_number, part["internal_name"])
        legacy_dims = dimensions_key(part)
        specs = specs_by_part.get(part_id, [])
        sources = excel_by_part.get(part_id, [])
        matched_sourced = [
            row
            for row in specs
            if has_dimensions(legacy_dims)
            and dimensions_key(row) == legacy_dims
            and row["source_sheet"] is not None
            and row["source_row"] is not None
        ]
        matched_unsourced = [
            row
            for row in specs
            if has_dimensions(legacy_dims)
            and dimensions_key(row) == legacy_dims
            and (row["source_sheet"] is None or row["source_row"] is None)
        ]
        exact_excel = [
            row
            for row in sources
            if row["tooling_id"] is not None
            and has_dimensions(legacy_dims)
            and dimensions_key(row, "parsed_") == legacy_dims
        ]
        compatible_excel = [
            row
            for row in sources
            if row["tooling_id"] is not None
            and has_dimensions(dimensions_key(row, "parsed_"))
            and compatible_source_dimensions(legacy_dims, dimensions_key(row, "parsed_"))
        ]
        completion_by_dimensions: dict[
            tuple[Decimal | None, ...], list[dict[str, Any]]
        ] = defaultdict(list)
        for row in compatible_excel:
            completion_by_dimensions[
                completed_dimensions(legacy_dims, dimensions_key(row, "parsed_"))
            ].append(row)
        completion_keys = list(completion_by_dimensions)
        unique_complete_completion = (
            len(completion_keys) == 1 and all(value is not None for value in completion_keys[0])
        )

        if not has_dimensions(legacy_dims):
            twp_status = "text_only_or_height_only"
        elif matched_sourced:
            legacy_text = normalize_spec(part["spec_twph"])
            sourced_texts = {normalize_spec(row["spec_twph"]) for row in matched_sourced}
            twp_status = (
                "sourced_dimensions_but_text_differs"
                if legacy_text and legacy_text not in sourced_texts
                else "covered_by_sourced_tooling_spec"
            )
        elif matched_unsourced:
            twp_status = "covered_but_provenance_missing"
        elif exact_excel:
            twp_status = "exact_excel_candidate"
        elif unique_complete_completion:
            twp_status = "exact_excel_candidate"
        elif len(completion_keys) > 1:
            twp_status = "ambiguous_excel_completion"
        elif compatible_excel:
            twp_status = "partial_excel_evidence"
        elif specs:
            twp_status = "tooling_spec_conflict"
        elif sources:
            twp_status = "excel_rows_exist_but_no_exact_match"
        elif links_by_part.get(part_id):
            twp_status = "tooling_link_without_excel_evidence"
        else:
            twp_status = "no_tooling_or_excel_evidence"

        spec_info_status = (
            "empty"
            if not has_text(part["spec_info"])
            else "excel_rows_available_needs_field_mapping"
            if sources
            else "no_excel_row"
        )
        twp_summary[twp_status] += 1
        spec_info_summary[spec_info_status] += 1
        items.append(
            {
                "part_id": part_id,
                "part_number": part_number or None,
                "internal_name": part["internal_name"],
                "is_test_record": test_record,
                "legacy": {
                    "spec_info": part["spec_info"],
                    "spec_twph": part["spec_twph"],
                    "thickness": str(part["thickness"]) if part["thickness"] is not None else None,
                    "width": str(part["width"]) if part["width"] is not None else None,
                    "pitch": str(part["pitch"]) if part["pitch"] is not None else None,
                    "height": str(part["height"]) if part["height"] is not None else None,
                },
                "twp_status": twp_status,
                "matching_sourced_specs": [source_ref(row) for row in matched_sourced],
                "exact_excel_candidates": [source_ref(row) for row in exact_excel],
                "compatible_excel_evidence": [source_ref(row) for row in compatible_excel],
                "resolved_twp": (
                    {
                        "thickness": str(completion_keys[0][0])
                        if completion_keys[0][0] is not None
                        else None,
                        "width": str(completion_keys[0][1])
                        if completion_keys[0][1] is not None
                        else None,
                        "pitch": str(completion_keys[0][2])
                        if completion_keys[0][2] is not None
                        else None,
                    }
                    if unique_complete_completion
                    else None
                ),
                "tooling_links": [
                    {"tooling_number": row["tooling_number"], "is_primary": row["is_primary"]}
                    for row in links_by_part.get(part_id, [])
                ],
                "spec_info_status": spec_info_status,
                "review_evidence": (
                    {
                        "tooling_specs": [
                            {
                                **source_ref(row),
                                "spec_twph": row["spec_twph"],
                                "thickness": str(row["thickness"]) if row["thickness"] is not None else None,
                                "width": str(row["width"]) if row["width"] is not None else None,
                                "pitch": str(row["pitch"]) if row["pitch"] is not None else None,
                            }
                            for row in specs
                        ],
                        "excel_rows": [
                            {
                                **source_ref(row),
                                "thickness": str(row["parsed_thickness"]) if row["parsed_thickness"] is not None else None,
                                "width": str(row["parsed_width"]) if row["parsed_width"] is not None else None,
                                "pitch": str(row["parsed_pitch"]) if row["parsed_pitch"] is not None else None,
                            }
                            for row in sources
                        ],
                    }
                    if twp_status not in {"covered_by_sourced_tooling_spec", "exact_excel_candidate"}
                    else None
                ),
            }
        )

    review = [
        item
        for item in items
        if item["twp_status"] not in {"covered_by_sourced_tooling_spec", "exact_excel_candidate"}
        or item["spec_info_status"] not in {"empty", "excel_rows_available_needs_field_mapping"}
    ]
    return {
        "scope": {
            "active_parts_with_legacy_spec_values": len(items),
            "test_records_in_scope": sum(item["is_test_record"] for item in items),
        },
        "twp_summary": dict(sorted(twp_summary.items())),
        "spec_info_summary": dict(sorted(spec_info_summary.items())),
        "exact_excel_migration_candidates": [
            item for item in items if item["twp_status"] == "exact_excel_candidate"
        ],
        "review_required": review,
        "all_items": items,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=BACKEND_DIR.parent / "reports" / "legacy_part_spec_audit.json",
    )
    args = parser.parse_args()
    try:
        report = await build_report()
    finally:
        await engine.dispose()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(args.report),
                "scope": report["scope"],
                "twp_summary": report["twp_summary"],
                "spec_info_summary": report["spec_info_summary"],
                "exact_excel_migration_candidates": len(
                    report["exact_excel_migration_candidates"]
                ),
                "review_required": len(report["review_required"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
