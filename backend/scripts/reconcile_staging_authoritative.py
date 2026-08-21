#!/usr/bin/env python3
"""Phase 3A2c: Relationship diagnostics and action candidates for staging data.

This script performs read-only relationship diagnostics and generates deduped action candidates.
It validates aliases, tooling links, and generates insert candidates for missing relationships.

Usage:
    python reconcile_staging_authoritative.py                    # dry-run, read-only
    python reconcile_staging_authoritative.py --help             # show help, no DB connection
    python reconcile_staging_authoritative.py --apply            # abort with "not implemented"
    python reconcile_staging_authoritative.py --report-dir ./out # custom report directory
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
EXCEL_PATH = PROJECT_ROOT / "excel" / "五金模具及产品清单表.xls"
EXPECTED_SHA256 = "f9ba5dc0602d7828e10e194646e5733c7782d700b06aea10f007aa6d7b818e74"

# Customer alias mapping (唯一别名)
CUSTOMER_ALIASES = {
    "温州力邦企业": "温州力邦企业有限公司",
}

# Required customer ID validation
REQUIRED_CUSTOMERS = {
    16: "温州力邦企业有限公司",
    7272: "日立安斯泰莫底盘系统（苏州）有限公司",
    7328: "H4287",
    7329: "日立安斯泰莫底盘系统（武汉）有限公司",
}

# Template/header values to exclude
TEMPLATE_VALUES = {
    "客户", "客户名称", "客户件号", "模具编号", "内部名称", "产品名称",
    "产品编号", "模具号", "本厂产品名称", "本厂产品编号",
    "原图产品编号", "原图产品名称",
}

# Tables to query for counts
CANONICAL_TABLES = [
    "customers",
    "parts",
    "part_customer_aliases",
    "tooling",
    "tooling_parts",
    "tooling_customer_links",
]

STAGING_TABLES = [
    "excel_import_rows",
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Customer and part resolution dry-run for staging data (Phase 3A2b)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to database (currently aborts with 'not implemented')",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=BACKEND_DIR / "scripts" / "backups" / "reconciliation_reports",
        help="Directory to write JSON reports (default: backend/scripts/backups/reconciliation_reports)",
    )
    parser.add_argument(
        "--plan-file",
        type=Path,
        help="Optional plan file for staged operations (reserved for future use)",
    )
    return parser.parse_args()


def is_template_value(value: Any) -> bool:
    """Check if a value is a template/header placeholder."""
    if value is None:
        return False
    text = str(value).strip()
    return text in TEMPLATE_VALUES or text in {"_", "__", "___", "...", "…", "#", "##", "###"}


def norm(value: Any) -> str:
    """Normalize value for key-based matching (from audit script)."""
    if value is None:
        return ""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value)).strip()).upper()


def norm_name(value: Any) -> str:
    """Normalize name for fuzzy matching (from audit script)."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).strip()).lower()


def looks_like_tooling(value: Any) -> bool:
    """Check if value looks like a tooling number (from audit script)."""
    text = norm(value)
    return bool(text and re.match(r"^(TY|GB).+[-](Q|M)\d", text))


def compute_file_sha256(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_excel_hash() -> dict[str, Any]:
    """Verify that the Excel file hash matches the expected authoritative source."""
    if not EXCEL_PATH.exists():
        return {
            "status": "error",
            "message": f"Excel file not found: {EXCEL_PATH}",
            "expected_sha256": EXPECTED_SHA256,
        }

    actual_hash = compute_file_sha256(EXCEL_PATH)
    if actual_hash != EXPECTED_SHA256:
        return {
            "status": "error",
            "message": "Excel file hash mismatch",
            "expected_sha256": EXPECTED_SHA256,
            "actual_sha256": actual_hash,
            "path": str(EXCEL_PATH),
        }

    return {
        "status": "ok",
        "sha256": actual_hash,
        "path": str(EXCEL_PATH),
    }


def get_database_url() -> str:
    """Get database URL from backend/app/config.py settings."""
    sys.path.insert(0, str(BACKEND_DIR))
    from app.config import settings  # noqa: PLC0415

    # Convert asyncpg URL to psycopg2 format
    db_url = settings.DATABASE_URL
    if "postgresql+asyncpg://" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    return db_url


def connect_readonly() -> psycopg2.extensions.connection:
    """Connect to database with forced read-only transaction mode."""
    db_url = get_database_url()
    conn = psycopg2.connect(
        db_url,
        options="-c default_transaction_read_only=on",
    )
    return conn


def get_table_counts(cur: psycopg2.extensions.cursor) -> dict[str, int]:
    """Query row counts for canonical and staging tables."""
    counts = {}

    for table in CANONICAL_TABLES + STAGING_TABLES:
        try:
            cur.execute(f"SELECT COUNT(*) AS count FROM {table}")
            result = cur.fetchone()
            counts[table] = result["count"] if result else 0
        except psycopg2.Error as e:
            counts[table] = {"error": str(e)}

    return counts


def get_unique_indexes(cur: psycopg2.extensions.cursor) -> list[dict[str, Any]]:
    """Query unique indexes from pg_indexes, including partial/expression indexes.

    This queries pg_indexes which contains the full index definition including
    WHERE clauses for partial indexes and expressions, not just pg_constraint
    which only shows basic constraint information.
    """
    query = """
        SELECT
            schemaname,
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexdef ILIKE '%UNIQUE%'
        ORDER BY tablename, indexname
    """
    cur.execute(query)
    indexes = [dict(row) for row in cur.fetchall()]
    return indexes


def verify_database_readonly(cur: psycopg2.extensions.cursor) -> bool:
    """Verify that the connection is truly read-only."""
    cur.execute("SELECT current_setting('transaction_read_only') AS value")
    result = cur.fetchone()
    return result["value"] == "on" if result else False


def validate_required_customers(cur: psycopg2.extensions.cursor) -> tuple[bool, list[str]]:
    """Validate that required customer IDs match expected names."""
    errors = []
    for customer_id, expected_name in REQUIRED_CUSTOMERS.items():
        cur.execute("SELECT id, name FROM customers WHERE id = %s", (customer_id,))
        row = cur.fetchone()
        if not row:
            errors.append(f"Customer ID {customer_id} not found (expected: {expected_name})")
        elif row["name"] != expected_name:
            errors.append(
                f"Customer ID {customer_id} name mismatch: "
                f"expected '{expected_name}', got '{row['name']}'"
            )
    return len(errors) == 0, errors


def load_active_customers(cur: psycopg2.extensions.cursor) -> tuple[list[dict], dict[str, list[int]]]:
    """Load active customers and build name lookup index."""
    cur.execute("SELECT id, name FROM customers WHERE is_active = TRUE ORDER BY id")
    customers = [dict(row) for row in cur.fetchall()]

    # Build name -> customer_ids index
    customers_by_name: dict[str, list[int]] = defaultdict(list)
    for customer in customers:
        customers_by_name[customer["name"]].append(customer["id"])

    return customers, customers_by_name


def load_staging_rows(cur: psycopg2.extensions.cursor) -> list[dict]:
    """Load all excel_import_rows with columns needed for part resolution."""
    cur.execute("""
        SELECT id, parsed_customer_name, parsed_tooling_number,
               parsed_customer_part_no, parsed_customer_part_name, parsed_internal_name, parsed_position,
               source_sheet, source_row,
               resolved_customer_id, resolved_part_id
        FROM excel_import_rows
        ORDER BY id
    """)
    return [dict(row) for row in cur.fetchall()]


def load_parts_data(cur: psycopg2.extensions.cursor) -> dict[int, dict]:
    """Load non-deleted parts indexed by ID."""
    cur.execute("SELECT * FROM parts WHERE is_deleted = FALSE ORDER BY id")
    return {row["id"]: dict(row) for row in cur.fetchall()}


def load_aliases_data(cur: psycopg2.extensions.cursor) -> list[dict]:
    """Load active part_customer_aliases."""
    cur.execute("SELECT * FROM part_customer_aliases WHERE is_active = TRUE ORDER BY id")
    return [dict(row) for row in cur.fetchall()]


def load_tooling_links(cur: psycopg2.extensions.cursor) -> list[dict]:
    """Load tooling_parts joined with non-deleted tooling."""
    cur.execute("""
        SELECT tp.id AS tooling_part_id, tp.part_id, tp.tooling_id,
               tp.position, t.tooling_number, t.tooling_no, t.is_deleted
        FROM tooling_parts tp
        JOIN tooling t ON t.id = tp.tooling_id
        WHERE t.is_deleted = FALSE
        ORDER BY tp.id
    """)
    return [dict(row) for row in cur.fetchall()]


def load_tooling_data(cur: psycopg2.extensions.cursor) -> list[dict]:
    """Load non-deleted tooling records."""
    cur.execute("""
        SELECT id, tooling_number, tooling_no, is_deleted
        FROM tooling
        WHERE is_deleted = FALSE
        ORDER BY id
    """)
    return [dict(row) for row in cur.fetchall()]


def load_existing_aliases_detailed(cur: psycopg2.extensions.cursor) -> list[dict]:
    """Load active part_customer_aliases with all fields for conflict detection."""
    cur.execute("""
        SELECT id, customer_id, part_id, customer_part_no,
               customer_part_name, revision, is_active
        FROM part_customer_aliases
        WHERE is_active = TRUE
        ORDER BY id
    """)
    return [dict(row) for row in cur.fetchall()]


def load_tooling_customer_links(cur: psycopg2.extensions.cursor) -> list[dict]:
    """Load tooling_customer_links."""
    cur.execute("""
        SELECT id, tooling_id, customer_id, relation_type
        FROM tooling_customer_links
        ORDER BY id
    """)
    return [dict(row) for row in cur.fetchall()]


def build_part_indexes(
    parts: dict[int, dict],
    aliases: list[dict],
    tooling_links: list[dict],
) -> dict[str, Any]:
    """Build indexes for part matching (replicates audit script logic)."""
    # Index: tooling_number -> part_ids
    parts_by_tooling: dict[str, set[int]] = defaultdict(set)

    # Add parts with tooling-like values in mold_number, press_tonnage, ppap_no
    for part_id, part in parts.items():
        for field in ("mold_number", "press_tonnage", "ppap_no"):
            if looks_like_tooling(part.get(field)):
                parts_by_tooling[norm(part[field])].add(part_id)

    # Add parts from tooling_parts relationship
    for link in tooling_links:
        tooling_number = link.get("tooling_number") or link.get("tooling_no")
        key = norm(tooling_number)
        if key:
            parts_by_tooling[key].add(link["part_id"])

    # Index: (customer_id, customer_part_no) -> part_ids
    alias_parts: dict[tuple[int, str], set[int]] = defaultdict(set)
    for alias in aliases:
        cpn_key = norm(alias["customer_part_no"])
        alias_parts[(alias["customer_id"], cpn_key)].add(alias["part_id"])

    return {
        "parts": parts,
        "parts_by_tooling": parts_by_tooling,
        "alias_parts": alias_parts,
    }


def choose_part(
    row: dict[str, Any],
    customer_id: int,
    indexes: dict[str, Any],
) -> tuple[int | None, str, list[int]]:
    """Choose part from candidates (replicates audit script logic exactly).

    Returns:
        (resolved_part_id, status, sorted_candidate_ids)

    Status values:
        - "unique": exactly one candidate found
        - "no_part_candidate": no candidates found
        - "multiple_part_candidates": multiple candidates remain after narrowing
    """
    tooling_key = norm(row.get("parsed_tooling_number"))
    cpn_key = norm(row.get("parsed_customer_part_no"))
    internal_key = norm_name(row.get("parsed_internal_name"))
    position_key = norm_name(row.get("parsed_position"))

    # Get candidates from tooling and alias
    tooling_candidates = set(indexes["parts_by_tooling"].get(tooling_key, set()))
    alias_candidates = set(indexes["alias_parts"].get((customer_id, cpn_key), set()))

    # If both exist, prefer intersection; if empty, fall back to tooling only
    if tooling_candidates and alias_candidates:
        candidates = tooling_candidates & alias_candidates
        if not candidates:
            candidates = tooling_candidates
    else:
        candidates = tooling_candidates or alias_candidates

    # Narrow by customer_part_no exact match
    if cpn_key and len(candidates) > 1:
        exact_cpn = {
            part_id
            for part_id in candidates
            if cpn_key in {
                norm(indexes["parts"][part_id].get("customer_product_no")),
                norm(indexes["parts"][part_id].get("part_number")),
            }
        }
        if exact_cpn:
            candidates = exact_cpn

    # Narrow by internal_name exact match
    if internal_key and len(candidates) > 1:
        exact_internal = {
            part_id
            for part_id in candidates
            if norm_name(indexes["parts"][part_id].get("internal_name")) == internal_key
        }
        if exact_internal:
            candidates = exact_internal

    # Narrow by position exact match
    if position_key and len(candidates) > 1:
        exact_position = {
            part_id
            for part_id in candidates
            if norm_name(indexes["parts"][part_id].get("part_position")) == position_key
        }
        if exact_position:
            candidates = exact_position

    if len(candidates) == 1:
        return next(iter(candidates)), "unique", sorted(candidates)
    if not candidates:
        return None, "no_part_candidate", []
    return None, "multiple_part_candidates", sorted(candidates)


def resolve_customer(
    parsed_customer_name: str,
    customers_by_name: dict[str, list[int]],
) -> tuple[int | None, str, list[int]]:
    """Resolve a customer name to customer ID.

    Returns:
        (resolved_id, status, candidate_ids)

    Status values:
        - "resolved": unique match found
        - "customer_not_found": no match found
        - "customer_not_unique": multiple matches found
        - "required_customer_id_mismatch": unique match but wrong required ID
    """
    # Apply alias mapping
    lookup_name = CUSTOMER_ALIASES.get(parsed_customer_name, parsed_customer_name)

    # Lookup customer IDs
    customer_ids = customers_by_name.get(lookup_name, [])

    if len(customer_ids) == 1:
        resolved_id = customer_ids[0]

        # Validate required customer IDs for specific exact full names only
        if lookup_name == "日立安斯泰莫底盘系统（武汉）有限公司":
            if resolved_id != 7329:
                return None, "required_customer_id_mismatch", customer_ids
        elif lookup_name == "日立安斯泰莫底盘系统（苏州）有限公司":
            if resolved_id != 7272:
                return None, "required_customer_id_mismatch", customer_ids

        return resolved_id, "resolved", customer_ids
    elif len(customer_ids) == 0:
        return None, "customer_not_found", []
    else:
        return None, "customer_not_unique", customer_ids


def process_customer_resolution(
    staging_rows: list[dict],
    customers_by_name: dict[str, list[int]],
) -> dict[str, Any]:
    """Process customer resolution for all staging rows.

    Returns a dict with:
        - candidate_rows: rows eligible for customer resolution
        - resolved_rows: rows successfully resolved
        - customer_not_found: rows with no customer match
        - customer_not_unique: rows with multiple customer matches
        - required_customer_id_mismatch: rows where unique candidate has wrong required ID
        - changed_from_old: rows where new resolution differs from old
        - by_customer_name: statistics grouped by customer name
        - details: per-row resolution details
    """
    candidate_rows = 0
    resolved_rows = 0
    customer_not_found = 0
    customer_not_unique = 0
    required_customer_id_mismatch = 0
    changed_from_old = 0

    by_customer_name: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "resolved": 0, "failed": 0})
    details: list[dict[str, Any]] = []

    for row in staging_rows:
        parsed_customer_name = row.get("parsed_customer_name")
        parsed_tooling_number = row.get("parsed_tooling_number")

        # Skip rows without both customer name and tooling number
        if not parsed_customer_name or not parsed_tooling_number:
            continue

        # Skip template/header values
        if is_template_value(parsed_customer_name) or is_template_value(parsed_tooling_number):
            continue

        candidate_rows += 1
        by_customer_name[parsed_customer_name]["total"] += 1

        # Resolve customer
        resolved_id, status, candidate_ids = resolve_customer(parsed_customer_name, customers_by_name)

        # Update counters
        if status == "resolved":
            resolved_rows += 1
            by_customer_name[parsed_customer_name]["resolved"] += 1
        elif status == "customer_not_found":
            customer_not_found += 1
            by_customer_name[parsed_customer_name]["failed"] += 1
        elif status == "customer_not_unique":
            customer_not_unique += 1
            by_customer_name[parsed_customer_name]["failed"] += 1
        elif status == "required_customer_id_mismatch":
            required_customer_id_mismatch += 1
            by_customer_name[parsed_customer_name]["failed"] += 1

        # Check if resolution changed from old value
        old_resolved_customer_id = row.get("resolved_customer_id")
        if resolved_id is not None and old_resolved_customer_id != resolved_id:
            changed_from_old += 1

        # Add detail record
        details.append({
            "staging_id": row["id"],
            "source_sheet": row.get("source_sheet"),
            "source_row": row.get("source_row"),
            "parsed_customer_name": parsed_customer_name,
            "old_resolved_customer_id": old_resolved_customer_id,
            "new_resolved_customer_id": resolved_id,
            "status": status,
            "candidate_customer_ids": candidate_ids if status != "resolved" else None,
        })

    return {
        "candidate_rows": candidate_rows,
        "resolved_rows": resolved_rows,
        "customer_not_found": customer_not_found,
        "customer_not_unique": customer_not_unique,
        "required_customer_id_mismatch": required_customer_id_mismatch,
        "changed_from_old_resolved_customer": changed_from_old,
        "by_customer_name": dict(by_customer_name),
        "details": details,
    }


def process_part_resolution(
    staging_rows: list[dict],
    customers_by_name: dict[str, list[int]],
    part_indexes: dict[str, Any],
) -> dict[str, Any]:
    """Process part resolution for customer-resolved staging rows.

    Returns a dict with:
        - customer_resolved_rows: rows with unique customer resolution
        - unique_part_rows: rows with unique part match
        - no_part_candidate: rows with no part candidates
        - multiple_part_candidates: rows with multiple part candidates
        - customer_unresolved: rows without unique customer
        - changed_from_old_resolved_part: rows where new part differs from old
        - details: per-row part resolution details (stable sorted)
    """
    customer_resolved_rows = 0
    unique_part_rows = 0
    no_part_candidate = 0
    multiple_part_candidates = 0
    customer_unresolved = 0
    changed_from_old_resolved_part = 0

    details: list[dict[str, Any]] = []

    for row in staging_rows:
        parsed_customer_name = row.get("parsed_customer_name")
        parsed_tooling_number = row.get("parsed_tooling_number")

        # Skip rows without both customer name and tooling number
        if not parsed_customer_name or not parsed_tooling_number:
            continue

        # Skip template/header values
        if is_template_value(parsed_customer_name) or is_template_value(parsed_tooling_number):
            continue

        # Resolve customer first
        resolved_customer_id, customer_status, _ = resolve_customer(parsed_customer_name, customers_by_name)

        if customer_status != "resolved":
            customer_unresolved += 1
            details.append({
                "staging_id": row["id"],
                "source_sheet": row.get("source_sheet"),
                "source_row": row.get("source_row"),
                "customer_id": None,
                "parsed_tooling_number": parsed_tooling_number,
                "parsed_customer_part_no": row.get("parsed_customer_part_no"),
                "parsed_customer_part_name": row.get("parsed_customer_part_name"),
                "parsed_internal_name": row.get("parsed_internal_name"),
                "parsed_position": row.get("parsed_position"),
                "status": "customer_unresolved",
                "resolved_part_id": None,
                "part_candidates": None,
                "old_resolved_part_id": row.get("resolved_part_id"),
            })
            continue

        customer_resolved_rows += 1

        # Try to resolve part
        resolved_part_id, part_status, candidate_ids = choose_part(
            row, resolved_customer_id, part_indexes
        )

        # Update counters
        if part_status == "unique":
            unique_part_rows += 1
        elif part_status == "no_part_candidate":
            no_part_candidate += 1
        elif part_status == "multiple_part_candidates":
            multiple_part_candidates += 1

        # Check if resolution changed from old value
        old_resolved_part_id = row.get("resolved_part_id")
        if resolved_part_id is not None and old_resolved_part_id != resolved_part_id:
            changed_from_old_resolved_part += 1

        # Add detail record
        details.append({
            "staging_id": row["id"],
            "source_sheet": row.get("source_sheet"),
            "source_row": row.get("source_row"),
            "customer_id": resolved_customer_id,
            "parsed_tooling_number": parsed_tooling_number,
            "parsed_customer_part_no": row.get("parsed_customer_part_no"),
            "parsed_customer_part_name": row.get("parsed_customer_part_name"),
            "parsed_internal_name": row.get("parsed_internal_name"),
            "parsed_position": row.get("parsed_position"),
            "status": part_status,
            "resolved_part_id": resolved_part_id,
            "part_candidates": candidate_ids if part_status != "unique" else None,
            "old_resolved_part_id": old_resolved_part_id,
        })

    # Stable sort by staging_id
    details.sort(key=lambda x: x["staging_id"])

    return {
        "customer_resolved_rows": customer_resolved_rows,
        "unique_part_rows": unique_part_rows,
        "no_part_candidate": no_part_candidate,
        "multiple_part_candidates": multiple_part_candidates,
        "customer_unresolved": customer_unresolved,
        "changed_from_old_resolved_part": changed_from_old_resolved_part,
        "details": details,
    }


def process_alias_diagnostics(
    part_resolution_details: list[dict],
    existing_aliases: list[dict],
) -> dict[str, Any]:
    """Diagnose alias relationships for unique part rows with planned cross-part conflict detection.

    Business key: (customer_id, norm(customer_part_no), revision='') — does NOT include part_id.

    Algorithm:
    1. Group all unique-part staging rows by business key
    2. For each business key group:
       - If existing alias is unique and matches group's unique expected part -> all rows resolved
       - If existing aliases conflict OR group expects multiple different parts -> all rows alias_conflict
       - If no existing alias and group expects unique part -> generate ONE candidate
    3. Candidates deduplicated by business key (NOT by part_id)
    4. Assertion: each business key maps to at most one candidate

    Returns:
        - alias_resolved: count where active alias exists with same part
        - empty_customer_part_no: count where customer_part_no is empty (deferred)
        - alias_conflict: count where conflicts exist (existing or planned cross-part)
        - missing_alias: count where no alias exists and candidate generated
        - alias_insert_candidates: deduped list with source_refs, customer_part_name_values
        - conflicts: list with reason (existing_alias_conflict / planned_cross_part_conflict)
        - deferred: list of deferred (empty customer_part_no) details
    """
    # Build index of existing aliases: (customer_id, norm(customer_part_no), norm(revision)) -> [(alias_id, part_id), ...]
    existing_alias_index: dict[tuple[int, str, str], list[tuple[int, int]]] = defaultdict(list)
    for alias in existing_aliases:
        key = (alias["customer_id"], norm(alias["customer_part_no"]), norm(alias.get("revision") or ""))
        existing_alias_index[key].append((alias["id"], alias["part_id"]))

    # Group staging rows by business key: (customer_id, norm(customer_part_no), revision='')
    staging_groups: dict[tuple[int, str, str], list[dict]] = defaultdict(list)

    for detail in part_resolution_details:
        if detail["status"] != "unique":
            continue

        customer_id = detail["customer_id"]
        customer_part_no = detail["parsed_customer_part_no"]

        # Empty customer_part_no -> skip grouping, handle separately
        if not customer_part_no or not customer_part_no.strip():
            continue

        business_key = (customer_id, norm(customer_part_no), "")
        staging_groups[business_key].append(detail)

    # Process each business key group
    alias_resolved = 0
    empty_customer_part_no = 0
    alias_conflict = 0
    missing_alias = 0

    conflicts: list[dict] = []
    deferred: list[dict] = []

    # Track candidates by business key (NOT including part_id)
    candidate_keys: dict[tuple[int, str, str], dict] = {}

    # Handle empty customer_part_no separately
    for detail in part_resolution_details:
        if detail["status"] != "unique":
            continue

        customer_part_no = detail["parsed_customer_part_no"]
        if not customer_part_no or not customer_part_no.strip():
            empty_customer_part_no += 1
            deferred.append({
                "staging_id": detail["staging_id"],
                "source_sheet": detail["source_sheet"],
                "source_row": detail["source_row"],
                "customer_id": detail["customer_id"],
                "part_id": detail["resolved_part_id"],
                "reason": "empty_customer_part_no",
            })

    # Process each business key group
    for business_key, group_rows in staging_groups.items():
        customer_id, norm_cpn, revision = business_key

        # Get expected part_ids from this group
        expected_part_ids = {row["resolved_part_id"] for row in group_rows}

        # Get existing aliases for this business key
        existing_entries = existing_alias_index.get(business_key, [])

        # Determine conflict status
        has_existing_conflict = len(existing_entries) > 1 or (
            len(existing_entries) == 1 and existing_entries[0][1] not in expected_part_ids
        )
        has_planned_conflict = len(expected_part_ids) > 1

        if has_existing_conflict or has_planned_conflict:
            # All rows in this group are conflicts
            alias_conflict += len(group_rows)

            for row in group_rows:
                if has_existing_conflict:
                    reason = "existing_alias_conflict"
                else:
                    reason = "planned_cross_part_conflict"

                conflicts.append({
                    "staging_id": row["staging_id"],
                    "source_sheet": row["source_sheet"],
                    "source_row": row["source_row"],
                    "customer_id": customer_id,
                    "expected_part_id": row["resolved_part_id"],
                    "customer_part_no": row["parsed_customer_part_no"],
                    "existing_aliases": [{"alias_id": aid, "part_id": pid} for aid, pid in existing_entries] if has_existing_conflict else [],
                    "planned_part_ids": sorted(expected_part_ids) if has_planned_conflict else None,
                    "reason": reason,
                })

        elif len(existing_entries) == 1 and len(expected_part_ids) == 1 and existing_entries[0][1] in expected_part_ids:
            # Unique alias matches unique expected part -> all rows resolved
            alias_resolved += len(group_rows)

        elif len(existing_entries) == 0 and len(expected_part_ids) == 1:
            # No alias exists, unique expected part -> generate ONE candidate
            missing_alias += len(group_rows)

            # Business key for candidate (NO part_id)
            if business_key not in candidate_keys:
                unique_part_id = next(iter(expected_part_ids))

                # Collect source_refs and customer_part_name_values
                source_refs = []
                customer_part_name_values = set()

                for row in sorted(group_rows, key=lambda r: r["staging_id"]):
                    source_refs.append({
                        "staging_id": row["staging_id"],
                        "source_sheet": row["source_sheet"],
                        "source_row": row["source_row"],
                    })

                    cpn_val = row.get("parsed_customer_part_name")
                    if cpn_val and cpn_val.strip():
                        normalized = norm(cpn_val)
                        if normalized:
                            customer_part_name_values.add(normalized)

                # Determine customer_part_name: only if unique value
                if len(customer_part_name_values) == 1:
                    customer_part_name = next(iter(customer_part_name_values))
                else:
                    customer_part_name = None

                candidate_keys[business_key] = {
                    "customer_id": customer_id,
                    "part_id": unique_part_id,
                    "customer_part_no": group_rows[0]["parsed_customer_part_no"],
                    "customer_part_name": customer_part_name,
                    "customer_part_name_values": sorted(customer_part_name_values),
                    "revision": revision,
                    "source_staging_ids": sorted([row["staging_id"] for row in group_rows]),
                    "source_refs": source_refs,
                }

    # Convert candidates to sorted list and assert uniqueness
    alias_insert_candidates = sorted(candidate_keys.values(), key=lambda x: (x["customer_id"], norm(x["customer_part_no"]), x["revision"]))

    # Assertion: each business key appears at most once
    seen_business_keys = set()
    for candidate in alias_insert_candidates:
        bk = (candidate["customer_id"], norm(candidate["customer_part_no"]), candidate["revision"])
        assert bk not in seen_business_keys, f"Duplicate candidate for business key {bk}"
        seen_business_keys.add(bk)

    return {
        "alias_resolved": alias_resolved,
        "empty_customer_part_no": empty_customer_part_no,
        "alias_conflict": alias_conflict,
        "missing_alias": missing_alias,
        "alias_insert_candidates": alias_insert_candidates,
        "conflicts": conflicts,
        "deferred": deferred,
    }


def process_tooling_diagnostics(
    part_resolution_details: list[dict],
    tooling_data: list[dict],
) -> dict[str, Any]:
    """Diagnose tooling master records.

    Returns:
        - tooling_resolved: count where exactly one non-deleted tooling matches
        - tooling_not_found: count where no match
        - tooling_not_unique: count where multiple matches
        - details: per-row tooling resolution with tooling_id
    """
    # Build index: norm(tooling_number or tooling_no) -> [tooling_id, ...]
    tooling_index: dict[str, list[int]] = defaultdict(list)
    for t in tooling_data:
        key = norm(t["tooling_number"] or t["tooling_no"])
        if key:
            tooling_index[key].append(t["id"])

    tooling_resolved = 0
    tooling_not_found = 0
    tooling_not_unique = 0

    details = []

    for detail in part_resolution_details:
        if detail["status"] != "unique":
            continue

        tooling_number = detail["parsed_tooling_number"]
        tooling_key = norm(tooling_number)

        tooling_ids = tooling_index.get(tooling_key, [])

        if len(tooling_ids) == 1:
            tooling_resolved += 1
            status = "resolved"
            tooling_id = tooling_ids[0]
        elif len(tooling_ids) == 0:
            tooling_not_found += 1
            status = "tooling_not_found"
            tooling_id = None
        else:
            tooling_not_unique += 1
            status = "tooling_not_unique"
            tooling_id = None

        details.append({
            "staging_id": detail["staging_id"],
            "source_sheet": detail["source_sheet"],
            "source_row": detail["source_row"],
            "customer_id": detail["customer_id"],
            "part_id": detail["resolved_part_id"],
            "parsed_tooling_number": tooling_number,
            "tooling_id": tooling_id,
            "status": status,
            "tooling_candidates": tooling_ids if status != "resolved" else None,
        })

    return {
        "tooling_resolved": tooling_resolved,
        "tooling_not_found": tooling_not_found,
        "tooling_not_unique": tooling_not_unique,
        "details": details,
    }


def process_tooling_part_diagnostics(
    tooling_diagnostics: dict,
    existing_tooling_parts: list[dict],
    part_resolution_details: list[dict],
) -> dict[str, Any]:
    """Diagnose tooling-part relationships and generate candidates.

    Returns:
        - resolved: count where relationship exists
        - missing_tooling_part: count where relationship missing
        - tooling_part_insert_candidates: deduped list with aggregated positions
        - position_conflicts: list of candidates with conflicting positions
    """
    # Build index: (tooling_id, part_id) -> [existing position, ...]
    existing_tp_index: dict[tuple[int, int], list[str | None]] = defaultdict(list)
    for tp in existing_tooling_parts:
        key = (tp["tooling_id"], tp["part_id"])
        existing_tp_index[key].append(tp.get("position"))

    resolved = 0
    missing_tooling_part = 0

    # Track candidates: (tooling_id, part_id) -> {positions: set, staging_ids: list}
    candidate_data: dict[tuple[int, int], dict] = {}

    # Build lookup for parsed_position by staging_id
    position_lookup = {d["staging_id"]: d.get("parsed_position") for d in part_resolution_details}

    for detail in tooling_diagnostics["details"]:
        if detail["status"] != "resolved":
            continue

        tooling_id = detail["tooling_id"]
        part_id = detail["part_id"]
        key = (tooling_id, part_id)

        if key in existing_tp_index:
            resolved += 1
        else:
            missing_tooling_part += 1

            if key not in candidate_data:
                candidate_data[key] = {
                    "tooling_id": tooling_id,
                    "part_id": part_id,
                    "positions": set(),
                    "source_staging_ids": [],
                }

            candidate_data[key]["source_staging_ids"].append(detail["staging_id"])

            # Aggregate parsed_position
            parsed_position = position_lookup.get(detail["staging_id"])
            if parsed_position and parsed_position.strip():
                norm_pos = norm_name(parsed_position)
                if norm_pos:
                    candidate_data[key]["positions"].add(norm_pos)

    # Check for position conflicts and prepare candidates
    tooling_part_insert_candidates = []
    position_conflicts = []

    for key, data in candidate_data.items():
        positions = data["positions"]

        if len(positions) > 1:
            # Multiple different positions -> conflict, cancel candidate
            position_conflicts.append({
                "tooling_id": data["tooling_id"],
                "part_id": data["part_id"],
                "conflicting_positions": sorted(positions),
                "source_staging_ids": data["source_staging_ids"],
            })
        else:
            # No conflict or no position data
            tooling_part_insert_candidates.append({
                "tooling_id": data["tooling_id"],
                "part_id": data["part_id"],
                "position": list(positions)[0] if positions else None,
                "source_staging_ids": data["source_staging_ids"],
            })

    # Sort candidates
    tooling_part_insert_candidates.sort(key=lambda x: (x["tooling_id"], x["part_id"]))

    return {
        "resolved": resolved,
        "missing_tooling_part": missing_tooling_part,
        "tooling_part_insert_candidates": tooling_part_insert_candidates,
        "position_conflicts": position_conflicts,
    }


def process_tooling_customer_diagnostics(
    tooling_diagnostics: dict,
    existing_tooling_customer_links: list[dict],
) -> dict[str, Any]:
    """Diagnose tooling-customer relationships.

    Returns:
        - resolved: count where any relation_type relationship exists
        - missing_tooling_customer: count where no relationship exists
        - tooling_customer_insert_candidates: deduped list with relation_type='user'
    """
    # Build index: (tooling_id, customer_id) -> [relation_types]
    existing_tc_index: dict[tuple[int, int], list[str]] = defaultdict(list)
    for tc in existing_tooling_customer_links:
        key = (tc["tooling_id"], tc["customer_id"])
        existing_tc_index[key].append(tc["relation_type"])

    resolved = 0
    missing_tooling_customer = 0

    # Track candidates: (tooling_id, customer_id) -> {staging_ids: list}
    candidate_data: dict[tuple[int, int], list[int]] = defaultdict(list)

    for detail in tooling_diagnostics["details"]:
        if detail["status"] != "resolved":
            continue

        tooling_id = detail["tooling_id"]
        customer_id = detail["customer_id"]
        key = (tooling_id, customer_id)

        if key in existing_tc_index:
            # Any relationship exists -> resolved
            resolved += 1
        else:
            # No relationship -> missing, generate candidate
            missing_tooling_customer += 1
            candidate_data[key].append(detail["staging_id"])

    # Convert to candidate list
    tooling_customer_insert_candidates = [
        {
            "tooling_id": tooling_id,
            "customer_id": customer_id,
            "relation_type": "user",
            "source_staging_ids": staging_ids,
        }
        for (tooling_id, customer_id), staging_ids in candidate_data.items()
    ]

    # Sort candidates
    tooling_customer_insert_candidates.sort(key=lambda x: (x["tooling_id"], x["customer_id"]))

    return {
        "resolved": resolved,
        "missing_tooling_customer": missing_tooling_customer,
        "tooling_customer_insert_candidates": tooling_customer_insert_candidates,
    }


def generate_staging_update_candidates(
    part_resolution_details: list[dict],
    tooling_diagnostics: dict,
    alias_diagnostics: dict,
    tooling_part_diagnostics: dict,
) -> list[dict]:
    """Generate staging_update_candidates for rows that meet all criteria.

    Criteria:
    - customer, part, tooling all uniquely resolved
    - alias exists (resolved) OR has insert candidate without conflict
    - tooling-part exists OR has insert candidate without conflict
    - customer_part_no is not empty

    Returns list of staging row IDs eligible for update.
    """
    # Build lookup for tooling status by staging_id
    tooling_lookup = {d["staging_id"]: d for d in tooling_diagnostics["details"]}

    # Build set of staging_ids with alias conflicts
    alias_conflict_ids = {c["staging_id"] for c in alias_diagnostics["conflicts"]}

    # Build set of staging_ids with deferred (empty customer_part_no)
    alias_deferred_ids = {d["staging_id"] for d in alias_diagnostics["deferred"]}

    # Build set of staging_ids that have insert candidates (these are allowed)
    alias_candidate_staging_ids = set()
    for candidate in alias_diagnostics["alias_insert_candidates"]:
        alias_candidate_staging_ids.update(candidate["source_staging_ids"])

    # Build set of (tooling_id, part_id) with position conflicts
    tp_conflict_keys = {(c["tooling_id"], c["part_id"]) for c in tooling_part_diagnostics["position_conflicts"]}

    candidates = []

    for detail in part_resolution_details:
        if detail["status"] != "unique":
            continue

        staging_id = detail["staging_id"]

        # Check if customer_part_no is empty
        if staging_id in alias_deferred_ids:
            continue

        # Check alias status: must be resolved OR have a candidate
        # Conflicts are already excluded, but we also need to ensure the row has either
        # been resolved or has a candidate
        if staging_id in alias_conflict_ids:
            continue

        # The row must either:
        # 1. Have an alias candidate (missing_alias case), OR
        # 2. Be resolved (not in conflicts and not in candidates means it was resolved)
        # If it's not in conflicts, not in deferred, and not in candidates, it means alias_resolved
        # If it's in candidates, that's also acceptable
        # The key is: it must NOT be in conflicts

        # Check tooling resolution
        tooling_detail = tooling_lookup.get(staging_id)
        if not tooling_detail or tooling_detail["status"] != "resolved":
            continue

        # Check if tooling-part has position conflict
        tooling_id = tooling_detail["tooling_id"]
        part_id = detail["resolved_part_id"]
        if (tooling_id, part_id) in tp_conflict_keys:
            continue

        # All criteria met
        candidates.append({
            "staging_id": staging_id,
            "source_sheet": detail["source_sheet"],
            "source_row": detail["source_row"],
            "customer_id": detail["customer_id"],
            "part_id": part_id,
            "tooling_id": tooling_id,
        })

    return candidates


def compute_report_fingerprint(report: dict[str, Any]) -> str:
    """Compute stable SHA256 fingerprint excluding timestamps and output paths."""
    # Create a copy and remove non-stable fields
    stable_report = report.copy()
    if "metadata" in stable_report:
        meta = stable_report["metadata"].copy()
        meta.pop("generated_at", None)
        meta.pop("report_path", None)
        stable_report["metadata"] = meta

    # Serialize to stable JSON (sorted keys, no ensure_ascii for consistency)
    stable_json = json.dumps(stable_report, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def generate_report(
    excel_verification: dict[str, Any],
    table_counts: dict[str, int],
    unique_indexes: list[dict[str, Any]],
    database_read_only: bool,
    customer_resolution: dict[str, Any],
    part_resolution: dict[str, Any],
    relation_resolution: dict[str, Any] | None = None,
    action_candidates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate the JSON report structure."""
    report = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "script_version": "3A2c_relationship_diagnostics",
            "database_read_only": database_read_only,
        },
        "excel_verification": excel_verification,
        "database_state": {
            "table_counts": table_counts,
            "unique_indexes": unique_indexes,
            "unique_indexes_count": len(unique_indexes),
        },
        "customer_resolution": customer_resolution,
        "part_resolution": part_resolution,
        "operations": {
            "dry_run": True,
            "apply_attempted": False,
            "status": "relationship_diagnostics_complete",
        },
    }

    if relation_resolution is not None:
        report["relation_resolution"] = relation_resolution

    if action_candidates is not None:
        report["action_candidates"] = action_candidates

    return report


def write_report(report: dict[str, Any], report_dir: Path) -> Path:
    """Write JSON report to disk."""
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"part_candidate_resolution_{timestamp}.json"

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # --help is handled by argparse automatically and exits before this point

    # If --apply is specified, abort immediately (before connecting to database)
    if args.apply:
        print("ERROR: --apply mode is not implemented in Phase 3A2c.", file=sys.stderr)
        print("The write operations are reserved for a future phase after validation.", file=sys.stderr)
        print("Current script only performs read-only relationship diagnostics.", file=sys.stderr)
        return 1

    print("Phase 3A2c: Relationship Diagnostics and Action Candidates")
    print("=" * 60)

    # Verify Excel file hash
    print("\n[1/8] Verifying Excel file hash...")
    excel_verification = verify_excel_hash()
    if excel_verification["status"] == "error":
        print(f"  ERROR: {excel_verification['message']}")
        if "actual_sha256" in excel_verification:
            print(f"  Expected: {excel_verification['expected_sha256']}")
            print(f"  Actual:   {excel_verification['actual_sha256']}")
        return 1
    print(f"  OK: {excel_verification['sha256']}")

    # Connect to database
    print("\n[2/8] Connecting to database (read-only mode)...")
    try:
        conn = connect_readonly()
    except Exception as e:
        print(f"  ERROR: Failed to connect to database: {e}", file=sys.stderr)
        return 1

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verify read-only mode
            database_read_only = verify_database_readonly(cur)
            if not database_read_only:
                print("  ERROR: Database connection is not in read-only mode!", file=sys.stderr)
                return 1
            print("  OK: Connection is read-only")

            # Validate required customers
            print("\n[3/8] Validating required customer IDs...")
            valid, errors = validate_required_customers(cur)
            if not valid:
                print("  ERROR: Required customer validation failed:", file=sys.stderr)
                for error in errors:
                    print(f"    - {error}", file=sys.stderr)
                return 1
            print(f"  OK: All {len(REQUIRED_CUSTOMERS)} required customers validated")

            # Query table counts
            print("\n[4/8] Querying database state...")
            table_counts = get_table_counts(cur)
            print("  Table counts:")
            for table, count in table_counts.items():
                if isinstance(count, dict):
                    print(f"    {table}: ERROR - {count['error']}")
                else:
                    print(f"    {table}: {count:,} rows")

            # Query unique indexes
            unique_indexes = get_unique_indexes(cur)
            print(f"\n  Unique indexes found: {len(unique_indexes)}")

            # Load data for customer resolution
            print("\n[5/8] Processing customer and part resolution...")
            customers, customers_by_name = load_active_customers(cur)
            print(f"  Loaded {len(customers)} active customers")

            staging_rows = load_staging_rows(cur)
            print(f"  Loaded {len(staging_rows)} staging rows")

            # Process customer resolution
            customer_resolution = process_customer_resolution(staging_rows, customers_by_name)
            print(f"\n  Customer Resolution Summary:")
            print(f"    Candidate rows:        {customer_resolution['candidate_rows']:,}")
            print(f"    Resolved rows:         {customer_resolution['resolved_rows']:,}")
            print(f"    Customer not found:    {customer_resolution['customer_not_found']:,}")
            print(f"    Customer not unique:   {customer_resolution['customer_not_unique']:,}")

            # Load data for part resolution
            parts = load_parts_data(cur)
            print(f"\n  Loaded {len(parts)} non-deleted parts")

            aliases = load_aliases_data(cur)
            print(f"  Loaded {len(aliases)} active aliases")

            tooling_links = load_tooling_links(cur)
            print(f"  Loaded {len(tooling_links)} tooling-part links")

            part_indexes = build_part_indexes(parts, aliases, tooling_links)

            # Process part resolution
            part_resolution = process_part_resolution(staging_rows, customers_by_name, part_indexes)
            print(f"\n  Part Resolution Summary:")
            print(f"    Customer-resolved rows:      {part_resolution['customer_resolved_rows']:,}")
            print(f"    Unique part rows:            {part_resolution['unique_part_rows']:,}")
            print(f"    No part candidate:           {part_resolution['no_part_candidate']:,}")
            print(f"    Multiple part candidates:    {part_resolution['multiple_part_candidates']:,}")

            # Load data for relationship diagnostics
            print("\n[6/8] Loading relationship data...")
            existing_aliases_detailed = load_existing_aliases_detailed(cur)
            print(f"  Loaded {len(existing_aliases_detailed)} detailed aliases")

            tooling_data = load_tooling_data(cur)
            print(f"  Loaded {len(tooling_data)} non-deleted tooling records")

            tooling_customer_links = load_tooling_customer_links(cur)
            print(f"  Loaded {len(tooling_customer_links)} tooling-customer links")

            # Process relationship diagnostics
            print("\n[7/8] Processing relationship diagnostics...")

            # Alias diagnostics
            alias_diagnostics = process_alias_diagnostics(
                part_resolution["details"],
                existing_aliases_detailed,
            )
            print(f"\n  Alias Diagnostics:")
            print(f"    Alias resolved:             {alias_diagnostics['alias_resolved']:,}")
            print(f"    Empty customer_part_no:     {alias_diagnostics['empty_customer_part_no']:,}")
            print(f"    Alias conflict:             {alias_diagnostics['alias_conflict']:,}")
            print(f"    Missing alias:              {alias_diagnostics['missing_alias']:,}")
            print(f"    Insert candidates:          {len(alias_diagnostics['alias_insert_candidates']):,}")

            # Tooling diagnostics
            tooling_diagnostics = process_tooling_diagnostics(
                part_resolution["details"],
                tooling_data,
            )
            print(f"\n  Tooling Diagnostics:")
            print(f"    Tooling resolved:           {tooling_diagnostics['tooling_resolved']:,}")
            print(f"    Tooling not found:          {tooling_diagnostics['tooling_not_found']:,}")
            print(f"    Tooling not unique:         {tooling_diagnostics['tooling_not_unique']:,}")

            # Tooling-part diagnostics
            tooling_part_diagnostics = process_tooling_part_diagnostics(
                tooling_diagnostics,
                tooling_links,
                part_resolution["details"],
            )
            print(f"\n  Tooling-Part Diagnostics:")
            print(f"    Resolved:                   {tooling_part_diagnostics['resolved']:,}")
            print(f"    Missing tooling-part:       {tooling_part_diagnostics['missing_tooling_part']:,}")
            print(f"    Insert candidates:          {len(tooling_part_diagnostics['tooling_part_insert_candidates']):,}")
            print(f"    Position conflicts:         {len(tooling_part_diagnostics['position_conflicts']):,}")

            # Tooling-customer diagnostics
            tooling_customer_diagnostics = process_tooling_customer_diagnostics(
                tooling_diagnostics,
                tooling_customer_links,
            )
            print(f"\n  Tooling-Customer Diagnostics:")
            print(f"    Resolved:                   {tooling_customer_diagnostics['resolved']:,}")
            print(f"    Missing tooling-customer:   {tooling_customer_diagnostics['missing_tooling_customer']:,}")
            print(f"    Insert candidates:          {len(tooling_customer_diagnostics['tooling_customer_insert_candidates']):,}")

            # Generate staging update candidates
            print("\n[8/8] Generating action candidates...")
            staging_update_candidates = generate_staging_update_candidates(
                part_resolution["details"],
                tooling_diagnostics,
                alias_diagnostics,
                tooling_part_diagnostics,
            )
            print(f"  Staging update candidates:  {len(staging_update_candidates):,}")

            # Prepare relation_resolution section
            relation_resolution = {
                "alias": {
                    "alias_resolved": alias_diagnostics["alias_resolved"],
                    "empty_customer_part_no": alias_diagnostics["empty_customer_part_no"],
                    "alias_conflict": alias_diagnostics["alias_conflict"],
                    "missing_alias": alias_diagnostics["missing_alias"],
                    "conflicts": alias_diagnostics["conflicts"],
                    "deferred": alias_diagnostics["deferred"],
                },
                "tooling": {
                    "tooling_resolved": tooling_diagnostics["tooling_resolved"],
                    "tooling_not_found": tooling_diagnostics["tooling_not_found"],
                    "tooling_not_unique": tooling_diagnostics["tooling_not_unique"],
                },
                "tooling_part": {
                    "resolved": tooling_part_diagnostics["resolved"],
                    "missing_tooling_part": tooling_part_diagnostics["missing_tooling_part"],
                    "position_conflicts": tooling_part_diagnostics["position_conflicts"],
                },
                "tooling_customer": {
                    "resolved": tooling_customer_diagnostics["resolved"],
                    "missing_tooling_customer": tooling_customer_diagnostics["missing_tooling_customer"],
                },
            }

            # Prepare action_candidates section
            action_candidates = {
                "alias_insert_candidates": alias_diagnostics["alias_insert_candidates"],
                "tooling_part_insert_candidates": tooling_part_diagnostics["tooling_part_insert_candidates"],
                "tooling_customer_insert_candidates": tooling_customer_diagnostics["tooling_customer_insert_candidates"],
                "staging_update_candidates": staging_update_candidates,
                "counts": {
                    "alias_inserts": len(alias_diagnostics["alias_insert_candidates"]),
                    "tooling_part_inserts": len(tooling_part_diagnostics["tooling_part_insert_candidates"]),
                    "tooling_customer_inserts": len(tooling_customer_diagnostics["tooling_customer_insert_candidates"]),
                    "staging_updates": len(staging_update_candidates),
                },
            }

            # Generate report
            report = generate_report(
                excel_verification,
                table_counts,
                unique_indexes,
                database_read_only,
                customer_resolution,
                part_resolution,
                relation_resolution,
                action_candidates,
            )

            # Compute fingerprint
            fingerprint = compute_report_fingerprint(report)
            report["metadata"]["fingerprint"] = fingerprint

            # Write report
            report_path = write_report(report, args.report_dir)
            print(f"\n{'=' * 60}")
            print(f"Report written to: {report_path}")
            print(f"\nSummary:")
            print(f"  Database read-only: {database_read_only}")
            print(f"  Script version: 3A2c")
            print(f"  Unique part rows: {part_resolution['unique_part_rows']:,}")
            print(f"  Alias insert candidates: {len(alias_diagnostics['alias_insert_candidates']):,}")
            print(f"  Tooling-part insert candidates: {len(tooling_part_diagnostics['tooling_part_insert_candidates']):,}")
            print(f"  Tooling-customer insert candidates: {len(tooling_customer_diagnostics['tooling_customer_insert_candidates']):,}")
            print(f"  Staging update candidates: {len(staging_update_candidates):,}")
            print(f"  Report fingerprint: {fingerprint[:16]}...")
            print(f"\nThis is a dry-run. No data was modified.")

            return 0

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
