"""Repair Shanghai Wanxiang aliases, duplicate price-bootstrap parts, and TWP gaps.

This is intentionally an explicit, auditable repair rather than a generic cleanup:
the only customer relationship source is the original Excel staging data already
recorded in ``excel_import_rows``.  The script is dry-run by default and writes a
JSON backup before applying changes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
from app.core.config import settings


CUSTOMER_ID = 28
PRICE_FIELDS = (
    "material_name", "net_weight", "gross_weight", "material_unit_price",
    "scrap_price", "surface_treatment_cost", "cost_override", "material_cost",
    "surface_treatment", "remark",
)


def canonical_part_number(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:
            return None
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    text = str(value).strip()
    match = re.fullmatch(r"([+-]?\d+)\.0+", text)
    return match.group(1) if match else (text or None)


def connect():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    return psycopg2.connect(url)


def rows_as_dicts(cur, query, params=()):
    cur.execute(query, params)
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def get_duplicate_groups(cur):
    aliases = rows_as_dicts(cur, """
        SELECT a.id, a.part_id, a.customer_part_no, a.customer_part_name,
               p.drawing_url, p.material_name, p.is_deleted
        FROM part_customer_aliases a
        JOIN parts p ON p.id = a.part_id
        WHERE a.customer_id = %s AND a.is_active = TRUE
          AND a.customer_part_no ~ '^[0-9]+$'
          AND a.customer_part_no !~ '\\.0$'
        ORDER BY a.id
    """, (CUSTOMER_ID,))
    dotted = rows_as_dicts(cur, """
        SELECT id, part_id, customer_part_no, customer_part_name
        FROM part_customer_aliases
        WHERE customer_id = %s AND is_active = TRUE
    """, (CUSTOMER_ID,))
    by_number = defaultdict(set)
    for row in dotted:
        canonical = canonical_part_number(row["customer_part_no"])
        if canonical is not None:
            by_number[canonical].add(row["part_id"])

    groups = []
    for alias in aliases:
        target_ids = sorted(by_number.get(canonical_part_number(alias["customer_part_no"]), set()) - {alias["part_id"]})
        if target_ids:
            groups.append({"alias": alias, "target_ids": target_ids})
    return groups


def collect_backup(cur, duplicate_groups):
    old_part_ids = sorted({g["alias"]["part_id"] for g in duplicate_groups})
    target_part_ids = sorted({part_id for g in duplicate_groups for part_id in g["target_ids"]})
    all_part_ids = sorted(set(old_part_ids + target_part_ids))
    backup = {
        "created_at": datetime.utcnow().isoformat(),
        "customer_id": CUSTOMER_ID,
        "duplicate_groups": duplicate_groups,
        "parts": rows_as_dicts(cur, "SELECT * FROM parts WHERE id = ANY(%s)", (all_part_ids,)),
        "aliases": rows_as_dicts(cur, "SELECT * FROM part_customer_aliases WHERE part_id = ANY(%s) OR (customer_id=%s AND customer_part_no ~ '\\.0$')", (all_part_ids, CUSTOMER_ID)),
        "staging_rows": rows_as_dicts(cur, "SELECT * FROM excel_import_rows WHERE resolved_customer_id=%s AND parsed_customer_part_no ~ '\\.0$'", (CUSTOMER_ID,)),
        "all_dot_zero_aliases": rows_as_dicts(cur, "SELECT * FROM part_customer_aliases WHERE customer_part_no ~ '\\.0$'"),
        "all_dot_zero_staging": rows_as_dicts(cur, "SELECT id, parsed_customer_part_no FROM excel_import_rows WHERE parsed_customer_part_no ~ '\\.0$'"),
        "prices": rows_as_dicts(cur, "SELECT * FROM prices WHERE part_id = ANY(%s)", (all_part_ids,)),
        "price_years": rows_as_dicts(cur, """
            SELECT py.* FROM price_years py JOIN prices p ON p.id=py.price_id
            WHERE p.part_id = ANY(%s)
        """, (all_part_ids,)),
    }
    return backup


def transfer_price_accounts(cur, old_part_id, target_ids, conflicts):
    old_prices = rows_as_dicts(cur, "SELECT * FROM prices WHERE part_id=%s AND customer_id=%s", (old_part_id, CUSTOMER_ID))
    for old_price in old_prices:
        old_years = rows_as_dicts(cur, "SELECT * FROM price_years WHERE price_id=%s", (old_price["id"],))
        for target_id in target_ids:
            target_prices = rows_as_dicts(cur, "SELECT * FROM prices WHERE part_id=%s AND customer_id=%s ORDER BY id LIMIT 1", (target_id, CUSTOMER_ID))
            if target_prices:
                target_price = target_prices[0]
                target_price_id = target_price["id"]
                updates = {}
                for field in PRICE_FIELDS:
                    old_value = old_price[field]
                    target_value = target_price[field]
                    if target_value is None and old_value is not None:
                        updates[field] = old_value
                    elif old_value is not None and target_value is not None and old_value != target_value:
                        conflicts.append({"type": "price_field_conflict", "old_part_id": old_part_id, "target_part_id": target_id, "field": field})
                if updates:
                    assignments = ", ".join(f"{field}=%s" for field in updates)
                    values = list(updates.values()) + [datetime.utcnow(), target_price_id]
                    cur.execute(f"UPDATE prices SET {assignments}, updated_at=%s WHERE id=%s", values)
            else:
                columns = ["part_id", "customer_id", *PRICE_FIELDS, "created_at", "updated_at"]
                values = [target_id, CUSTOMER_ID]
                for field in PRICE_FIELDS:
                    value = old_price[field]
                    if field == "surface_treatment" and value is not None:
                        value = psycopg2.extras.Json(value)
                    values.append(value)
                values.extend([datetime.utcnow(), datetime.utcnow()])
                placeholders = ", ".join(["%s"] * len(columns))
                cur.execute(f"INSERT INTO prices ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id", values)
                target_price_id = cur.fetchone()[0]

            for old_year in old_years:
                existing_year = rows_as_dicts(cur, "SELECT * FROM price_years WHERE price_id=%s AND year=%s", (target_price_id, old_year["year"]))
                if existing_year:
                    if existing_year[0]["unit_price"] != old_year["unit_price"]:
                        conflicts.append({"type": "price_year_conflict", "old_part_id": old_part_id, "target_part_id": target_id, "year": old_year["year"]})
                    continue
                cur.execute("""
                    INSERT INTO price_years(price_id,year,unit_price,annual_sales,operator_id,updated_at)
                    VALUES(%s,%s,%s,%s,%s,%s)
                """, (target_price_id, old_year["year"], old_year["unit_price"], old_year["annual_sales"], old_year["operator_id"], datetime.utcnow()))


def backfill_consistent_twp(cur, report):
    rows = rows_as_dicts(cur, """
        SELECT resolved_part_id, parsed_thickness, parsed_width, parsed_pitch, source_sheet, source_row
        FROM excel_import_rows
        WHERE resolved_customer_id=%s
          AND parsed_thickness IS NOT NULL
          AND parsed_width IS NOT NULL
          AND parsed_pitch IS NOT NULL
        ORDER BY resolved_part_id, source_row
    """, (CUSTOMER_ID,))
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["resolved_part_id"]].append(row)

    for part_id, sources in grouped.items():
        values = {(str(r["parsed_thickness"]), str(r["parsed_width"]), str(r["parsed_pitch"])) for r in sources}
        if len(values) != 1:
            report["twp_conflicts"].append({"part_id": part_id, "source_rows": [r["source_row"] for r in sources], "values": sorted(values)})
            continue
        source = sources[0]
        current = rows_as_dicts(cur, "SELECT id, thickness, width, pitch FROM parts WHERE id=%s", (part_id,))
        if not current:
            continue
        part = current[0]
        proposed = {"thickness": source["parsed_thickness"], "width": source["parsed_width"], "pitch": source["parsed_pitch"]}
        conflicts = []
        for field, value in proposed.items():
            if part[field] is not None and part[field] != value:
                conflicts.append(field)
        if conflicts:
            report["twp_conflicts"].append({"part_id": part_id, "source_rows": [r["source_row"] for r in sources], "fields": conflicts})
            continue
        updates = {field: value for field, value in proposed.items() if part[field] is None}
        if updates:
            assignments = ", ".join(f"{field}=%s" for field in updates)
            cur.execute(f"UPDATE parts SET {assignments}, updated_at=%s WHERE id=%s", [*updates.values(), datetime.utcnow(), part_id])
            report["twp_backfilled"].append({"part_id": part_id, "source_rows": [r["source_row"] for r in sources], "values": proposed, "filled_fields": sorted(updates)})


def apply_repair(apply: bool):
    conn = connect()
    conn.autocommit = False
    try:
        cur = conn.cursor()
        groups = get_duplicate_groups(cur)
        backup = collect_backup(cur, groups)
        backup_dir = Path(__file__).parent / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"wanxiang_repair_backup_{stamp}.json"
        backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")

        report = {
            "dry_run": not apply,
            "backup": str(backup_path),
            "duplicate_groups": len(groups),
            "deactivated_aliases": [],
            "soft_deleted_parts": [],
            "twp_backfilled": [],
            "twp_conflicts": [],
            "price_conflicts": [],
        }

        if apply:
            for group in groups:
                alias = group["alias"]
                target_ids = group["target_ids"]
                old_part_id = alias["part_id"]
                old_part = rows_as_dicts(cur, "SELECT drawing_url, material_name FROM parts WHERE id=%s", (old_part_id,))[0]
                for target_id in target_ids:
                    target = rows_as_dicts(cur, "SELECT drawing_url, material_name FROM parts WHERE id=%s", (target_id,))[0]
                    updates = {}
                    if target["drawing_url"] is None and old_part["drawing_url"] is not None:
                        updates["drawing_url"] = old_part["drawing_url"]
                    if target["material_name"] is None and old_part["material_name"] is not None:
                        updates["material_name"] = old_part["material_name"]
                    if updates:
                        assignments = ", ".join(f"{field}=%s" for field in updates)
                        cur.execute(f"UPDATE parts SET {assignments}, updated_at=%s WHERE id=%s", [*updates.values(), datetime.utcnow(), target_id])
                    transfer_price_accounts(cur, old_part_id, [target_id], report["price_conflicts"])
                cur.execute("UPDATE part_customer_aliases SET is_active=FALSE, updated_at=%s WHERE id=%s", (datetime.utcnow(), alias["id"]))
                cur.execute("UPDATE parts SET is_deleted=TRUE, updated_at=%s WHERE id=%s", (datetime.utcnow(), old_part_id))
                report["deactivated_aliases"].append(alias["id"])
                report["soft_deleted_parts"].append(old_part_id)

            backfill_consistent_twp(cur, report)

            cur.execute("""
                UPDATE part_customer_aliases
                SET customer_part_no=regexp_replace(customer_part_no, '\\.0+$', ''), updated_at=NOW()
                WHERE customer_part_no ~ '^[+-]?\\d+\\.0+$'
            """)
            report["normalized_aliases"] = cur.rowcount
            cur.execute("""
                UPDATE excel_import_rows
                SET parsed_customer_part_no=regexp_replace(parsed_customer_part_no, '\\.0+$', '')
                WHERE parsed_customer_part_no ~ '^[+-]?\\d+\\.0+$'
            """)
            report["normalized_staging_rows"] = cur.rowcount
            conn.commit()
        else:
            conn.rollback()

        print(json.dumps(report, ensure_ascii=False, indent=2, default=json_default))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    apply_repair(args.apply)
