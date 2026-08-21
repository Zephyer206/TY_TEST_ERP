"""Clear source-covered legacy T/W/P fields from the parts table.

The script is dry-run by default.  ``--apply`` first writes a JSON backup of
the exact rows selected by the read-only audit, then clears only the legacy
``spec_twph``, ``thickness``, ``width``, and ``pitch`` columns.  ``height`` and
``spec_info`` are intentionally preserved because they do not have a confirmed
destination in ``part_tooling_specs``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine, get_db_context  # noqa: E402
from app.models.part import Part  # noqa: E402
from audit_legacy_part_specs import build_report  # noqa: E402


SAFE_STATUSES = {"covered_by_sourced_tooling_spec", "exact_excel_candidate"}


def serialise(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def eligible_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in report["all_items"]
        if not item["is_test_record"] and item["twp_status"] in SAFE_STATUSES
    ]


async def apply_cleanup(
    items: list[dict[str, Any]],
    backup_path: Path,
) -> dict[str, Any]:
    part_ids = [item["part_id"] for item in items]
    if not part_ids:
        return {"updated": 0, "backup": None, "verification_failures": []}

    async with get_db_context() as db:
        rows = (
            await db.execute(select(Part).where(Part.id.in_(part_ids)))
        ).scalars().all()
        rows_by_id = {row.id: row for row in rows}
        missing_ids = sorted(set(part_ids) - set(rows_by_id))
        if missing_ids:
            raise RuntimeError(f"Audit selected missing part ids: {missing_ids[:10]}")

        backup = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": "clear source-covered legacy part T/W/P fields",
            "columns_cleared": ["spec_twph", "thickness", "width", "pitch"],
            "columns_preserved": ["spec_info", "height"],
            "rows": [
                {
                    "part_id": row.id,
                    "part_number": row.part_number,
                    "internal_name": row.internal_name,
                    "spec_info": row.spec_info,
                    "spec_twph": serialise(row.spec_twph),
                    "thickness": serialise(row.thickness),
                    "width": serialise(row.width),
                    "pitch": serialise(row.pitch),
                    "height": serialise(row.height),
                    "audit_status": next(
                        item["twp_status"]
                        for item in items
                        if item["part_id"] == row.id
                    ),
                }
                for row in sorted(rows, key=lambda value: value.id)
            ],
        }
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(
            json.dumps(backup, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        result = await db.execute(
            update(Part)
            .where(Part.id.in_(part_ids))
            .values(spec_twph=None, thickness=None, width=None, pitch=None)
        )
        updated = result.rowcount or 0

    async with get_db_context() as db:
        remaining = (
            await db.execute(
                select(Part.id).where(
                    Part.id.in_(part_ids),
                    (Part.spec_twph.is_not(None))
                    | Part.thickness.is_not(None)
                    | Part.width.is_not(None)
                    | Part.pitch.is_not(None),
                )
            )
        ).scalars().all()

    return {
        "updated": updated,
        "backup": str(backup_path),
        "verification_failures": sorted(remaining),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--backup",
        type=Path,
        default=None,
        help="Optional backup path; defaults to backend/scripts/backups.",
    )
    args = parser.parse_args()

    try:
        report = await build_report()
        items = eligible_items(report)
        summary = {
            "mode": "apply" if args.apply else "dry_run",
            "eligible": len(items),
            "statuses": {
                status: sum(item["twp_status"] == status for item in items)
                for status in sorted(SAFE_STATUSES)
            },
        }
        if args.apply:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = args.backup or (
                BACKEND_DIR / "scripts" / "backups"
                / f"legacy_part_specs_before_clear_{timestamp}.json"
            )
            summary.update(await apply_cleanup(items, backup_path))
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if not summary.get("verification_failures") else 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
