"""Safely complete missing T/W/P fields from authoritative Excel staging rows.

The original Excel import is the only source used here.  A part is eligible
only when every imported source row with a complete T/W/P tuple agrees.  This
script never overwrites an existing value, never resolves conflicting source
tuples, and is dry-run by default.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
from app.core.config import settings


def connect():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    return psycopg2.connect(url)


def json_default(value: Any):
    if isinstance(value, (Decimal, datetime)):
        return str(value)
    return str(value)


def load_candidates(cur):
    cur.execute(
        """
        WITH source AS (
            SELECT resolved_part_id AS part_id,
                   parsed_thickness, parsed_width, parsed_pitch,
                   id AS source_row_id, source_sheet, source_row
            FROM excel_import_rows
            WHERE validation_status = 'IMPORTED'
              AND resolved_part_id IS NOT NULL
              AND parsed_thickness IS NOT NULL
              AND parsed_width IS NOT NULL
              AND parsed_pitch IS NOT NULL
        ), grouped AS (
            SELECT part_id,
                   COUNT(DISTINCT (parsed_thickness, parsed_width, parsed_pitch)) AS variants,
                   MIN(parsed_thickness) AS thickness,
                   MIN(parsed_width) AS width,
                   MIN(parsed_pitch) AS pitch,
                   COUNT(*) AS source_count,
                   ARRAY_AGG(source_row_id ORDER BY source_row_id) AS source_row_ids
            FROM source
            GROUP BY part_id
        )
        SELECT p.id, p.thickness AS current_thickness,
               p.width AS current_width, p.pitch AS current_pitch,
               g.variants, g.thickness, g.width, g.pitch,
               g.source_count, g.source_row_ids
        FROM grouped g
        JOIN parts p ON p.id = g.part_id
        WHERE p.is_deleted = FALSE
        ORDER BY p.id
        """
    )
    columns = [description[0] for description in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def build_report(cur, grouped):
    candidates = []
    source_conflicts = []
    current_conflicts = []
    for row in grouped:
        proposed = {
            "thickness": row["thickness"],
            "width": row["width"],
            "pitch": row["pitch"],
        }
        current = {
            "thickness": row["current_thickness"],
            "width": row["current_width"],
            "pitch": row["current_pitch"],
        }
        base = {
            "part_id": row["id"],
            "source_count": row["source_count"],
            "source_row_ids": row["source_row_ids"],
            "proposed": proposed,
            "current": current,
        }
        if row["variants"] != 1:
            source_conflicts.append({**base, "variants": row["variants"]})
            continue
        mismatches = [
            field
            for field in ("thickness", "width", "pitch")
            if current[field] is not None and current[field] != proposed[field]
        ]
        if mismatches:
            current_conflicts.append({**base, "fields": mismatches})
            continue
        updates = {
            field: proposed[field]
            for field in ("thickness", "width", "pitch")
            if current[field] is None
        }
        if updates:
            candidates.append({**base, "updates": updates})

    candidate_ids = [item["part_id"] for item in candidates]
    cur.execute(
        "SELECT * FROM parts WHERE id = ANY(%s) ORDER BY id",
        (candidate_ids or [0],),
    )
    part_columns = [description[0] for description in cur.description]
    parts_backup = [dict(zip(part_columns, row)) for row in cur.fetchall()]
    return {
        "candidates": candidates,
        "source_conflicts": source_conflicts,
        "current_conflicts": current_conflicts,
        "parts_backup": parts_backup,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = connect()
    conn.autocommit = False
    try:
        cur = conn.cursor()
        grouped = load_candidates(cur)
        report = build_report(cur, grouped)
        backup_dir = Path(__file__).parent / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"partial_twp_backup_{stamp}.json"
        backup = {
            "created_at": datetime.utcnow().isoformat(),
            "dry_run": not args.apply,
            "candidate_parts": report["parts_backup"],
            "source_conflicts": report["source_conflicts"],
            "current_conflicts": report["current_conflicts"],
        }
        backup_path.write_text(
            json.dumps(backup, ensure_ascii=False, indent=2, default=json_default),
            encoding="utf-8",
        )

        updated = []
        if args.apply:
            for candidate in report["candidates"]:
                assignments = ", ".join(
                    f"{field}=%s" for field in candidate["updates"]
                )
                values = list(candidate["updates"].values())
                values.extend([datetime.utcnow(), candidate["part_id"]])
                cur.execute(
                    f"UPDATE parts SET {assignments}, updated_at=%s WHERE id=%s",
                    values,
                )
                updated.append(candidate["part_id"])
            conn.commit()
        else:
            conn.rollback()

        output = {
            "dry_run": not args.apply,
            "backup": str(backup_path),
            "safe_candidates": len(report["candidates"]),
            "source_conflicts": len(report["source_conflicts"]),
            "current_conflicts": len(report["current_conflicts"]),
            "updated": len(updated),
            "updated_part_ids": updated,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, default=json_default))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
