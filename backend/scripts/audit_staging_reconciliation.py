#!/usr/bin/env python3
"""Read-only audit that re-resolves Excel staging rows against live canonical data."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


BACKEND_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = Path(__file__).resolve().parent / "backups" / "staging_reconciliation"
APPROVED_CUSTOMER_NAMES = {"温州力邦企业": "温州力邦企业有限公司"}
TEMPLATE_VALUES = {
    "客户", "客户名称", "客户件号", "模具编号", "内部名称", "产品名称",
    "产品编号", "模具号", "本厂产品名称", "本厂产品编号",
    "原图产品编号", "原图产品名称",
}


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date, Decimal)):
        return str(value)
    raise TypeError(type(value))


def norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value)).strip()).upper()


def norm_name(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).strip()).lower()


def is_explicit_template(value: Any) -> bool:
    text = "" if value is None else str(value).strip()
    if not text:
        return False
    return text in TEMPLATE_VALUES or text in {"_", "__", "___", "...", "…", "#", "##", "###"}


def looks_like_tooling(value: Any) -> bool:
    text = norm(value)
    return bool(text and re.match(r"^(TY|GB).+[-](Q|M)\d", text))


def connect():
    sys.path.insert(0, str(BACKEND_DIR))
    from app.config import settings  # noqa: PLC0415

    return psycopg2.connect(
        settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1),
        options="-c default_transaction_read_only=on",
    )


def choose_part(
    row: dict[str, Any],
    customer_id: int,
    indexes: dict[str, Any],
) -> tuple[int | None, str, list[int]]:
    tooling_key = norm(row["parsed_tooling_number"])
    cpn_key = norm(row["parsed_customer_part_no"])
    internal_key = norm_name(row["parsed_internal_name"])
    position_key = norm_name(row.get("parsed_position"))

    tooling_candidates = set(indexes["parts_by_tooling"].get(tooling_key, set()))
    alias_candidates = set(indexes["alias_parts"].get((customer_id, cpn_key), set()))
    if tooling_candidates and alias_candidates:
        candidates = tooling_candidates & alias_candidates
        if not candidates:
            candidates = tooling_candidates
    else:
        candidates = tooling_candidates or alias_candidates

    if cpn_key and len(candidates) > 1:
        exact_cpn = {
            part_id
            for part_id in candidates
            if cpn_key
            in {
                norm(indexes["parts"][part_id].get("customer_product_no")),
                norm(indexes["parts"][part_id].get("part_number")),
            }
        }
        if exact_cpn:
            candidates = exact_cpn
    if internal_key and len(candidates) > 1:
        exact_internal = {
            part_id
            for part_id in candidates
            if norm_name(indexes["parts"][part_id].get("internal_name")) == internal_key
        }
        if exact_internal:
            candidates = exact_internal
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


def main() -> None:
    conn = connect()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT current_setting('transaction_read_only') AS value")
            if cur.fetchone()["value"] != "on":
                raise RuntimeError("Audit connection is not read-only")
            cur.execute("SELECT * FROM customers WHERE is_active=TRUE ORDER BY id")
            customers = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT * FROM parts WHERE is_deleted=FALSE ORDER BY id")
            parts = {row["id"]: dict(row) for row in cur.fetchall()}
            cur.execute("SELECT * FROM part_customer_aliases WHERE is_active=TRUE ORDER BY id")
            aliases = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT tp.id AS tooling_part_id, tp.part_id, tp.tooling_id,
                       tp.position, t.tooling_number, t.tooling_no, t.is_deleted
                FROM tooling_parts tp JOIN tooling t ON t.id=tp.tooling_id
                WHERE t.is_deleted=FALSE
                ORDER BY tp.id
                """
            )
            tooling_links = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT * FROM excel_import_rows ORDER BY id")
            staging = [dict(row) for row in cur.fetchall()]

        customers_by_name: dict[str, list[int]] = defaultdict(list)
        for customer in customers:
            customers_by_name[customer["name"]].append(customer["id"])

        parts_by_tooling: dict[str, set[int]] = defaultdict(set)
        for part_id, part in parts.items():
            for field in ("mold_number", "press_tonnage", "ppap_no"):
                if looks_like_tooling(part.get(field)):
                    parts_by_tooling[norm(part[field])].add(part_id)
        tooling_ids_by_part_and_number: dict[tuple[int, str], list[int]] = defaultdict(list)
        for link in tooling_links:
            tooling_number = link.get("tooling_number") or link.get("tooling_no")
            key = norm(tooling_number)
            if key:
                parts_by_tooling[key].add(link["part_id"])
                tooling_ids_by_part_and_number[(link["part_id"], key)].append(link["tooling_id"])

        alias_parts: dict[tuple[int, str], set[int]] = defaultdict(set)
        alias_ids: dict[tuple[int, int, str], list[int]] = defaultdict(list)
        for alias in aliases:
            cpn_key = norm(alias["customer_part_no"])
            alias_parts[(alias["customer_id"], cpn_key)].add(alias["part_id"])
            alias_ids[(alias["customer_id"], alias["part_id"], cpn_key)].append(alias["id"])

        indexes = {
            "parts": parts,
            "parts_by_tooling": parts_by_tooling,
            "alias_parts": alias_parts,
        }
        results: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        customer_failures: Counter[str] = Counter()

        for row in staging:
            customer_name = row.get("parsed_customer_name")
            tooling_number = row.get("parsed_tooling_number")
            if not customer_name or not tooling_number:
                continue
            if is_explicit_template(customer_name) or is_explicit_template(tooling_number):
                continue

            lookup_name = APPROVED_CUSTOMER_NAMES.get(customer_name, customer_name)
            customer_ids = customers_by_name.get(lookup_name, [])
            if len(customer_ids) != 1:
                status = "customer_not_unique" if customer_ids else "customer_not_found"
                status_counts[status] += 1
                customer_failures[customer_name] += 1
                results.append(
                    {
                        "staging_id": row["id"],
                        "source_sheet": row["source_sheet"],
                        "source_row": row["source_row"],
                        "parsed_customer_name": customer_name,
                        "parsed_tooling_number": tooling_number,
                        "status": status,
                        "customer_candidates": customer_ids,
                    }
                )
                continue

            customer_id = customer_ids[0]
            part_id, part_status, candidates = choose_part(row, customer_id, indexes)
            if part_id is None:
                status_counts[part_status] += 1
                results.append(
                    {
                        "staging_id": row["id"],
                        "source_sheet": row["source_sheet"],
                        "source_row": row["source_row"],
                        "parsed_customer_name": customer_name,
                        "parsed_tooling_number": tooling_number,
                        "parsed_customer_part_no": row.get("parsed_customer_part_no"),
                        "parsed_internal_name": row.get("parsed_internal_name"),
                        "status": part_status,
                        "resolved_customer_id": customer_id,
                        "part_candidates": candidates,
                    }
                )
                continue

            cpn_key = norm(row.get("parsed_customer_part_no"))
            exact_alias_ids = alias_ids.get((customer_id, part_id, cpn_key), [])
            exact_tooling_ids = tooling_ids_by_part_and_number.get(
                (part_id, norm(tooling_number)), []
            )
            if len(exact_alias_ids) == 1:
                status = "resolved"
            elif not exact_alias_ids:
                status = "missing_alias"
            else:
                status = "multiple_aliases"
            if len(exact_tooling_ids) == 0:
                tooling_status = "missing_tooling_link"
            elif len(set(exact_tooling_ids)) == 1:
                tooling_status = "resolved"
            else:
                tooling_status = "multiple_tooling_links"
            status_counts[status] += 1
            if tooling_status != "resolved":
                status_counts[tooling_status] += 1
            results.append(
                {
                    "staging_id": row["id"],
                    "source_sheet": row["source_sheet"],
                    "source_row": row["source_row"],
                    "parsed_customer_name": customer_name,
                    "parsed_tooling_number": tooling_number,
                    "parsed_customer_part_no": row.get("parsed_customer_part_no"),
                    "parsed_internal_name": row.get("parsed_internal_name"),
                    "parsed_position": row.get("parsed_position"),
                    "status": status,
                    "tooling_status": tooling_status,
                    "resolved_customer_id": customer_id,
                    "resolved_part_id": part_id,
                    "resolved_alias_ids": exact_alias_ids,
                    "resolved_tooling_ids": sorted(set(exact_tooling_ids)),
                    "old_resolved_customer_id": row.get("resolved_customer_id"),
                    "old_resolved_part_id": row.get("resolved_part_id"),
                    "old_resolved_alias_id": row.get("resolved_alias_id"),
                    "old_resolved_tooling_id": row.get("resolved_tooling_id"),
                }
            )

        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "database_read_only": True,
                "staging_rows_total": len(staging),
                "candidate_rows": len(results),
            },
            "summary": {
                "status_counts": dict(status_counts),
                "customer_failures": dict(customer_failures),
                "rows_with_changed_customer": sum(
                    row.get("resolved_customer_id") is not None
                    and row.get("old_resolved_customer_id") != row.get("resolved_customer_id")
                    for row in results
                ),
                "rows_with_changed_part": sum(
                    row.get("resolved_part_id") is not None
                    and row.get("old_resolved_part_id") != row.get("resolved_part_id")
                    for row in results
                ),
                "rows_with_changed_alias": sum(
                    len(row.get("resolved_alias_ids", [])) == 1
                    and row.get("old_resolved_alias_id") != row["resolved_alias_ids"][0]
                    for row in results
                ),
            },
            "results": results,
        }
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = REPORT_DIR / f"staging_reconciliation_audit_{timestamp}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=json_default),
            encoding="utf-8",
        )
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        print(path)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
