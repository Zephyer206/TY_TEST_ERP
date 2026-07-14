#!/usr/bin/env python3
"""Remediate the 1038 legacy parts that reference invalid customer rows.

Default mode is a database-read-only dry run. Apply mode requires an explicit
confirmation token, creates filesystem backups, revalidates every invariant,
and performs all writes in one transaction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
AUDIT_DIR = SCRIPT_DIR / "backups" / "customer_cleanup" / "legacy_ref_audit"
CLASSIFICATION_FILE = AUDIT_DIR / "classification_20260714_183810.json"
EXPECTED_CLASSIFICATION_SHA256 = "b868645f9d8be306a5583287e659d1b5d8fbb6688d25434bdf5cbeb6cac0ae69"
EXPECTED_COUNTS = {
    "unique_canonical_mapping": 930,
    "clear_deprecated_only": 20,
    "duplicate_legacy_part": 12,
    "new_customer_required": 37,
    "invalid_template_part": 39,
}
APPLY_CONFIRMATION = "APPLY_LEGACY_CUSTOMER_REFS_20260714"
BACKUP_ROOT = AUDIT_DIR / "remediation_backups"
CRITICAL_DUPLICATE_FIELDS = (
    "part_number",
    "internal_name",
    "mold_number",
    "customer_product_no",
    "material_name",
    "thickness",
    "width",
    "pitch",
    "spec_twph",
)


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date, Decimal)):
        return str(value)
    raise TypeError(f"Unsupported JSON type: {type(value)!r}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_classifications() -> list[dict[str, Any]]:
    actual_hash = sha256(CLASSIFICATION_FILE)
    if actual_hash != EXPECTED_CLASSIFICATION_SHA256:
        raise RuntimeError(
            f"Classification SHA256 mismatch: expected {EXPECTED_CLASSIFICATION_SHA256}, "
            f"got {actual_hash}"
        )
    data = json.loads(CLASSIFICATION_FILE.read_text(encoding="utf-8"))
    rows = data.get("classifications")
    if not isinstance(rows, list) or len(rows) != 1038:
        raise RuntimeError("Classification must contain exactly 1038 rows")
    ids = [row.get("part_id") for row in rows]
    if len(set(ids)) != 1038:
        raise RuntimeError("Classification part IDs are not unique")
    counts = Counter(row.get("category") for row in rows)
    if dict(counts) != EXPECTED_COUNTS:
        raise RuntimeError(f"Unexpected category counts: {dict(counts)}")
    if counts.get("ambiguous", 0):
        raise RuntimeError("Ambiguous classifications remain")
    return rows


def connect(read_only: bool):
    sys.path.insert(0, str(BACKEND_DIR))
    from app.config import settings  # noqa: PLC0415

    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    options = "-c default_transaction_read_only=on" if read_only else None
    return psycopg2.connect(url, options=options)


def fetch_all(cur: RealDictCursor, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def first_excel_row(classification: dict[str, Any]) -> dict[str, Any]:
    rows = classification.get("evidence", {}).get("excel_row_evidence", [])
    return rows[0] if rows else {}


def target_customer_spec(classification: dict[str, Any]) -> tuple[int | None, str]:
    category = classification["category"]
    if category == "new_customer_required":
        names = classification.get("evidence", {}).get("unmapped_customers", [])
        if len(names) != 1:
            raise RuntimeError(
                f"Part {classification['part_id']} must prove exactly one new customer: {names}"
            )
        return None, names[0]
    customer_id = classification.get("canonical_customer_id")
    customer_name = classification.get("canonical_customer_name")
    if category != "invalid_template_part" and (not customer_id or not customer_name):
        raise RuntimeError(
            f"Part {classification['part_id']} has no canonical customer for {category}"
        )
    return customer_id, customer_name or ""


def discover_live_part_reference_columns(cur: RealDictCursor) -> list[dict[str, str]]:
    cur.execute(
        """
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema=c.table_schema AND t.table_name=c.table_name
        WHERE c.table_schema='public'
          AND t.table_type='BASE TABLE'
          AND c.column_name IN ('part_id','internal_part_id','current_part_id')
          AND c.table_name <> 'parts'
          AND c.table_name !~ '(backup|snapshot|snap_)'
        ORDER BY c.table_name, c.column_name
        """
    )
    return [dict(row) for row in cur.fetchall()]


def nonzero_part_references(
    cur: RealDictCursor,
    columns: list[dict[str, str]],
    part_ids: list[int],
) -> list[dict[str, Any]]:
    if not part_ids:
        return []
    findings: list[dict[str, Any]] = []
    for item in columns:
        table = item["table_name"].replace('"', '""')
        column = item["column_name"].replace('"', '""')
        cur.execute(
            f'SELECT "{column}" AS part_id, COUNT(*) AS count '
            f'FROM "{table}" WHERE "{column}"=ANY(%s) '
            f'GROUP BY "{column}" ORDER BY "{column}"',
            (part_ids,),
        )
        rows = [dict(row) for row in cur.fetchall()]
        if rows:
            findings.append(
                {"table_name": item["table_name"], "column_name": item["column_name"], "rows": rows}
            )
    return findings


def build_plan(cur: RealDictCursor, classifications: list[dict[str, Any]]) -> dict[str, Any]:
    source_ids = sorted(row["part_id"] for row in classifications)
    duplicate_rows = [row for row in classifications if row["category"] == "duplicate_legacy_part"]
    duplicate_target_ids = sorted(row["duplicate_part_id"] for row in duplicate_rows)
    all_part_ids = sorted(set(source_ids + duplicate_target_ids))

    parts = fetch_all(cur, "SELECT * FROM parts WHERE id=ANY(%s) ORDER BY id", (all_part_ids,))
    parts_by_id = {row["id"]: row for row in parts}
    if not set(source_ids).issubset(parts_by_id):
        raise RuntimeError(f"Missing source parts: {sorted(set(source_ids) - parts_by_id.keys())}")
    if not set(duplicate_target_ids).issubset(parts_by_id):
        raise RuntimeError(
            f"Missing duplicate targets: {sorted(set(duplicate_target_ids) - parts_by_id.keys())}"
        )

    for classification in classifications:
        part = parts_by_id[classification["part_id"]]
        if part["is_deleted"] or part["customer_id"] != classification["invalid_customer_id"]:
            raise RuntimeError(
                f"Part {part['id']} changed since audit: customer_id={part['customer_id']}, "
                f"is_deleted={part['is_deleted']}"
            )

    canonical_ids = sorted(
        {
            row["canonical_customer_id"]
            for row in classifications
            if row.get("canonical_customer_id") is not None
        }
    )
    customers = fetch_all(
        cur,
        "SELECT * FROM customers WHERE id=ANY(%s) OR name=ANY(%s) ORDER BY id",
        (
            canonical_ids,
            sorted(
                {
                    target_customer_spec(row)[1]
                    for row in classifications
                    if row["category"] == "new_customer_required"
                }
            ),
        ),
    )
    customers_by_id = {row["id"]: row for row in customers}
    customers_by_name: dict[str, list[dict[str, Any]]] = {}
    for row in customers:
        customers_by_name.setdefault(row["name"], []).append(row)

    for classification in classifications:
        if classification.get("canonical_customer_id") is None:
            continue
        expected_id, expected_name = target_customer_spec(classification)
        customer = customers_by_id.get(expected_id)
        if not customer or customer["name"] != expected_name or not customer["is_active"]:
            raise RuntimeError(
                f"Canonical customer changed for part {classification['part_id']}: "
                f"expected {expected_id}/{expected_name}"
            )

    new_customer_names = sorted(
        {
            target_customer_spec(row)[1]
            for row in classifications
            if row["category"] == "new_customer_required"
        }
    )
    if new_customer_names != ["H4287", "日立安斯泰莫底盘系统（武汉）有限公司"]:
        raise RuntimeError(f"Unexpected new customer set: {new_customer_names}")
    for name in new_customer_names:
        exact = customers_by_name.get(name, [])
        if len(exact) > 1:
            raise RuntimeError(f"Multiple exact customers already exist for {name}")

    duplicate_comparisons: list[dict[str, Any]] = []
    for classification in duplicate_rows:
        source = parts_by_id[classification["part_id"]]
        target = parts_by_id[classification["duplicate_part_id"]]
        mismatches = {
            field: {"source": source.get(field), "target": target.get(field)}
            for field in CRITICAL_DUPLICATE_FIELDS
            if source.get(field) != target.get(field)
        }
        if mismatches:
            raise RuntimeError(
                f"Duplicate pair {source['id']}->{target['id']} differs: {mismatches}"
            )
        if target["customer_id"] != classification["canonical_customer_id"] or target["is_deleted"]:
            raise RuntimeError(
                f"Duplicate target {target['id']} is not the expected live canonical part"
            )
        duplicate_comparisons.append(
            {"source_part_id": source["id"], "target_part_id": target["id"], "mismatches": {}}
        )

    clear_rows = [row for row in classifications if row["category"] == "clear_deprecated_only"]
    clear_ids = [row["part_id"] for row in clear_rows]
    clear_aliases = fetch_all(
        cur,
        "SELECT * FROM part_customer_aliases WHERE part_id=ANY(%s) AND is_active=TRUE ORDER BY id",
        (clear_ids,),
    )
    clear_alias_keys = {(row["part_id"], row["customer_id"]) for row in clear_aliases}
    missing_clear_aliases = [
        row["part_id"]
        for row in clear_rows
        if (row["part_id"], row["canonical_customer_id"]) not in clear_alias_keys
    ]
    if missing_clear_aliases:
        raise RuntimeError(f"clear_deprecated_only aliases disappeared: {missing_clear_aliases}")

    alias_actions: list[dict[str, Any]] = []
    for classification in classifications:
        category = classification["category"]
        if category not in {"unique_canonical_mapping", "new_customer_required", "duplicate_legacy_part"}:
            continue
        target_id, target_name = target_customer_spec(classification)
        alias_part_id = (
            classification["duplicate_part_id"]
            if category == "duplicate_legacy_part"
            else classification["part_id"]
        )
        source_part = parts_by_id[classification["part_id"]]
        excel = first_excel_row(classification)
        alias_actions.append(
            {
                "source_part_id": classification["part_id"],
                "part_id": alias_part_id,
                "target_customer_id": target_id,
                "target_customer_name": target_name,
                # The authoritative Excel has eight legitimate blank customer-part
                # numbers. The current schema requires a string, so preserve the
                # source blank as an empty string instead of inventing an identifier.
                "customer_part_no": (
                    excel.get("customer_part_no")
                    or source_part.get("customer_product_no")
                    or source_part.get("part_number")
                    or ""
                ),
                "customer_part_name": source_part.get("customer_product_name"),
                "revision": "A",
                "vehicle_model": source_part.get("vehicle_model"),
                "remark": (
                    f"Legacy customer cleanup; Excel {excel.get('sheet')} row {excel.get('row')}"
                ),
            }
        )

    expected_alias_actions = EXPECTED_COUNTS["unique_canonical_mapping"] + EXPECTED_COUNTS[
        "new_customer_required"
    ] + EXPECTED_COUNTS["duplicate_legacy_part"]
    if len(alias_actions) != expected_alias_actions:
        raise RuntimeError(f"Expected {expected_alias_actions} alias actions, got {len(alias_actions)}")

    keep_ids = sorted(
        row["part_id"]
        for row in classifications
        if row["category"]
        in {"unique_canonical_mapping", "new_customer_required", "clear_deprecated_only"}
    )
    duplicate_delete_ids = sorted(row["part_id"] for row in duplicate_rows)
    template_delete_ids = sorted(
        row["part_id"] for row in classifications if row["category"] == "invalid_template_part"
    )
    delete_ids = sorted(duplicate_delete_ids + template_delete_ids)
    if len(keep_ids) != 987 or len(delete_ids) != 51:
        raise RuntimeError(f"Unexpected keep/delete counts: {len(keep_ids)}/{len(delete_ids)}")

    reference_columns = discover_live_part_reference_columns(cur)
    delete_references = nonzero_part_references(cur, reference_columns, delete_ids)
    if delete_references:
        raise RuntimeError(f"Delete candidates still have live references: {delete_references}")

    existing_aliases = fetch_all(
        cur,
        "SELECT * FROM part_customer_aliases WHERE part_id=ANY(%s) ORDER BY id",
        (sorted({action["part_id"] for action in alias_actions}),),
    )

    return {
        "classification_file": str(CLASSIFICATION_FILE),
        "classification_sha256": EXPECTED_CLASSIFICATION_SHA256,
        "category_counts": EXPECTED_COUNTS,
        "source_ids": source_ids,
        "keep_ids": keep_ids,
        "duplicate_delete_ids": duplicate_delete_ids,
        "template_delete_ids": template_delete_ids,
        "delete_ids": delete_ids,
        "duplicate_target_ids": duplicate_target_ids,
        "duplicate_comparisons": duplicate_comparisons,
        "new_customer_names": new_customer_names,
        "alias_actions": alias_actions,
        "clear_aliases": clear_aliases,
        "reference_columns_checked": reference_columns,
        "delete_references": delete_references,
        "parts_snapshot": parts,
        "customers_snapshot": customers,
        "existing_aliases_snapshot": existing_aliases,
    }


def write_artifact(prefix: str, payload: dict[str, Any]) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = AUDIT_DIR / f"{prefix}_{timestamp}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )
    return path


def backup_before_apply(cur: RealDictCursor, plan: dict[str, Any]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    affected_ids = sorted(set(plan["source_ids"] + plan["duplicate_target_ids"]))
    payload = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "classification_sha256": EXPECTED_CLASSIFICATION_SHA256,
        },
        "parts": fetch_all(cur, "SELECT * FROM parts WHERE id=ANY(%s) ORDER BY id", (affected_ids,)),
        "part_customer_aliases": fetch_all(
            cur,
            "SELECT * FROM part_customer_aliases WHERE part_id=ANY(%s) ORDER BY id",
            (affected_ids,),
        ),
        "customers": fetch_all(
            cur,
            "SELECT * FROM customers WHERE id=ANY(%s) OR name=ANY(%s) ORDER BY id",
            (
                sorted(
                    {
                        action["target_customer_id"]
                        for action in plan["alias_actions"]
                        if action["target_customer_id"] is not None
                    }
                ),
                plan["new_customer_names"],
            ),
        ),
        "plan": plan,
    }
    path = backup_dir / "backup.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )
    return path


def apply_plan(cur: RealDictCursor, plan: dict[str, Any]) -> dict[str, Any]:
    cur.execute("SELECT id FROM parts WHERE id=ANY(%s) FOR UPDATE", (plan["source_ids"],))
    cur.execute(
        "SELECT id FROM part_customer_aliases WHERE part_id=ANY(%s) FOR UPDATE",
        (sorted(set(plan["source_ids"] + plan["duplicate_target_ids"])),),
    )

    customer_ids_by_name: dict[str, int] = {}
    created_customers: list[dict[str, Any]] = []
    for name in plan["new_customer_names"]:
        cur.execute("SELECT id FROM customers WHERE name=%s ORDER BY id FOR UPDATE", (name,))
        rows = cur.fetchall()
        if len(rows) > 1:
            raise RuntimeError(f"Multiple exact customers exist for {name}")
        if rows:
            customer_ids_by_name[name] = rows[0]["id"]
        else:
            cur.execute(
                "INSERT INTO customers (name, is_active) VALUES (%s, TRUE) RETURNING id, name",
                (name,),
            )
            created = dict(cur.fetchone())
            created_customers.append(created)
            customer_ids_by_name[name] = created["id"]

    inserted_aliases = 0
    skipped_existing_aliases = 0
    for action in plan["alias_actions"]:
        customer_id = action["target_customer_id"]
        if customer_id is None:
            customer_id = customer_ids_by_name[action["target_customer_name"]]
        cur.execute(
            """
            SELECT id FROM part_customer_aliases
            WHERE part_id=%s AND customer_id=%s AND revision=%s AND is_active=TRUE
              AND customer_part_no IS NOT DISTINCT FROM %s
            ORDER BY id
            """,
            (
                action["part_id"],
                customer_id,
                action["revision"],
                action["customer_part_no"],
            ),
        )
        existing = cur.fetchall()
        if existing:
            skipped_existing_aliases += 1
            continue
        cur.execute(
            """
            INSERT INTO part_customer_aliases
              (part_id, customer_name, customer_part_no, customer_part_name,
               customer_id, revision, vehicle_model, remark, is_active)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
            """,
            (
                action["part_id"],
                action["target_customer_name"],
                action["customer_part_no"],
                action["customer_part_name"],
                customer_id,
                action["revision"],
                action["vehicle_model"],
                action["remark"],
            ),
        )
        inserted_aliases += 1

    cur.execute(
        "UPDATE parts SET customer_id=NULL, updated_at=NOW() WHERE id=ANY(%s) AND customer_id IS NOT NULL",
        (plan["keep_ids"],),
    )
    cleared_parts = cur.rowcount

    cur.execute("DELETE FROM parts WHERE id=ANY(%s)", (plan["delete_ids"],))
    deleted_parts = cur.rowcount
    if deleted_parts != 51:
        raise RuntimeError(f"Expected to delete 51 parts, deleted {deleted_parts}")

    return {
        "created_customers": created_customers,
        "inserted_aliases": inserted_aliases,
        "skipped_existing_aliases": skipped_existing_aliases,
        "cleared_parts_customer_id": cleared_parts,
        "deleted_parts": deleted_parts,
    }


def verify_after_apply(cur: RealDictCursor, plan: dict[str, Any]) -> dict[str, Any]:
    cur.execute(
        "SELECT COUNT(*) AS count FROM parts WHERE id=ANY(%s) AND customer_id IS NULL AND is_deleted=FALSE",
        (plan["keep_ids"],),
    )
    kept_clean = int(cur.fetchone()["count"])
    cur.execute("SELECT COUNT(*) AS count FROM parts WHERE id=ANY(%s)", (plan["delete_ids"],))
    delete_remaining = int(cur.fetchone()["count"])
    if kept_clean != 987 or delete_remaining != 0:
        raise RuntimeError(
            f"Post-apply part verification failed: kept_clean={kept_clean}, "
            f"delete_remaining={delete_remaining}"
        )

    missing_aliases: list[dict[str, Any]] = []
    for action in plan["alias_actions"]:
        customer_id = action["target_customer_id"]
        if customer_id is None:
            cur.execute("SELECT id FROM customers WHERE name=%s", (action["target_customer_name"],))
            rows = cur.fetchall()
            if len(rows) != 1:
                missing_aliases.append(action)
                continue
            customer_id = rows[0]["id"]
        cur.execute(
            """
            SELECT COUNT(*) AS count FROM part_customer_aliases
            WHERE part_id=%s AND customer_id=%s AND revision=%s AND is_active=TRUE
              AND customer_part_no IS NOT DISTINCT FROM %s
            """,
            (
                action["part_id"],
                customer_id,
                action["revision"],
                action["customer_part_no"],
            ),
        )
        if int(cur.fetchone()["count"]) < 1:
            missing_aliases.append(action)
    if missing_aliases:
        raise RuntimeError(f"Post-apply aliases missing: {missing_aliases[:5]}")

    return {
        "kept_parts_with_null_customer_id": kept_clean,
        "deleted_parts_remaining": delete_remaining,
        "missing_aliases": len(missing_aliases),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        raise SystemExit(f"Apply requires --confirm {APPLY_CONFIRMATION}")

    classifications = load_classifications()
    conn = connect(read_only=not args.apply)
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if args.apply:
                cur.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            else:
                cur.execute("SELECT current_setting('transaction_read_only') AS value")
                if cur.fetchone()["value"] != "on":
                    raise RuntimeError("Dry run connection is not read-only")
            plan = build_plan(cur, classifications)
            summary = {
                "mode": "apply" if args.apply else "dry_run",
                "category_counts": plan["category_counts"],
                "new_customers": plan["new_customer_names"],
                "alias_actions": len(plan["alias_actions"]),
                "clear_customer_id_parts": len(plan["keep_ids"]),
                "duplicate_parts_to_delete": len(plan["duplicate_delete_ids"]),
                "template_parts_to_delete": len(plan["template_delete_ids"]),
                "delete_references": plan["delete_references"],
                "database_modified": False,
            }
            if not args.apply:
                report_path = write_artifact("legacy_ref_remediation_dry_run", {"summary": summary, "plan": plan})
                conn.rollback()
                print(json.dumps(summary, ensure_ascii=False, indent=2))
                print(report_path)
                return

            backup_path = backup_before_apply(cur, plan)
            stats = apply_plan(cur, plan)
            verification = verify_after_apply(cur, plan)
            conn.commit()
            result = {
                "summary": {**summary, "database_modified": True},
                "stats": stats,
                "verification": verification,
                "backup_path": str(backup_path),
            }
            result_path = write_artifact("legacy_ref_remediation_apply", result)
            print(json.dumps(result, ensure_ascii=False, indent=2, default=json_default))
            print(result_path)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
