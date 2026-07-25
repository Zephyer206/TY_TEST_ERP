#!/usr/bin/env python3
"""Audit Excel source blocks that may share material/TWP/cavity display fields.

This is read-only.  It deliberately requires explicit one-out evidence and
source-block evidence before classifying a block as mergeable.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import xlrd


ROOT = Path(__file__).resolve().parents[2]
EXCEL_PATH = next((ROOT / "excel").glob("*.xls"))
OUT_JSON = ROOT / "scripts" / "analysis" / "shared_mold_blocks_audit.json"
OUT_MD = ROOT / "scripts" / "analysis" / "shared_mold_blocks_audit.md"


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def norm(value: Any) -> str:
    return re.sub(r"\s+", "", text(value)).replace("（", "(").replace("）", ")")


def header_row(sheet) -> int | None:
    # Use Unicode escapes so this remains robust when invoked from PowerShell.
    required = {
        "\u5ba2\u6237",
        "\u672c\u5382\u4ea7\u54c1\u7f16\u53f7",
        "\u672c\u5382\u4ea7\u54c1\u540d\u79f0",
        "\u6a21\u5177\u7c7b\u578b",
        "\u6750\u8d28",
    }
    for row in range(min(15, sheet.nrows)):
        values = {norm(sheet.cell_value(row, col)) for col in range(sheet.ncols)}
        if required.issubset(values):
            return row
    return None


def merged_map(sheet) -> dict[tuple[int, int], tuple[int, int]]:
    result: dict[tuple[int, int], tuple[int, int]] = {}
    for rlo, rhi, clo, chi in sheet.merged_cells:
        for row in range(rlo, rhi):
            for col in range(clo, chi):
                result[(row, col)] = (rlo, clo)
    return result


def parse_one_out(value: str) -> tuple[int | None, str | None]:
    """Return (cavity_count, explicit evidence text) without guessing."""
    raw = norm(value)
    if not raw:
        return None, None
    match = re.search(r"(?:1|一)出([0-9]+|[一二三四五六七八九十两])", raw)
    if match:
        token = match.group(1)
        chinese = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
                   "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        count = int(token) if token.isdigit() else chinese.get(token)
        return count, match.group(0)
    if "左右各一个" in raw or "左右各1个" in raw or "左右各一件" in raw:
        return 2, "左右各一个"
    return None, None


def value_at(sheet, row: int, col: int, merges: dict[tuple[int, int], tuple[int, int]]) -> str:
    anchor = merges.get((row, col))
    return text(sheet.cell_value(*(anchor or (row, col))))


def anchor_at(row: int, col: int, merges: dict[tuple[int, int], tuple[int, int]]) -> tuple[int, int]:
    return merges.get((row, col), (row, col))


def source_groups(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Build candidate blocks from merged source anchors and local evidence.

    A merged material/spec/remark cell is authoritative source-block evidence.
    When no such merge exists, adjacent identical explicit one-out rows are
    retained as ``undetermined`` so they can be reviewed rather than guessed.
    """
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    anchor_counts: dict[tuple[str, tuple[int, int]], int] = defaultdict(int)
    for record in records:
        for field, anchor in record["anchors"].items():
            anchor_counts[(field, anchor)] += 1

    for record in records:
        for field, anchor in record["anchors"].items():
            if anchor_counts[(field, anchor)] >= 2:
                key = ("anchor", field, anchor)
                groups.setdefault(key, []).append(record)

    # Capture likely pairs with explicit evidence but no merge anchor.
    ordered = [r for r in records if r["tooling_number"]]
    for left, right in zip(ordered, ordered[1:]):
        if right["row"] != left["row"] + 1:
            continue
        if norm(left["customer"]) != norm(right["customer"]):
            continue
        if not left["cavity_evidence"] or left["cavity"] != right["cavity"]:
            continue
        if norm(left["material"]) != norm(right["material"]):
            continue
        if norm(left["spec"]) != norm(right["spec"]):
            continue
        if left["customer_part_no"] == right["customer_part_no"]:
            continue
        key = ("adjacent", left["row"], right["row"])
        groups.setdefault(key, []).extend([left, right])

    # Deduplicate overlapping evidence groups by row/tooling signature.
    unique: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for group in groups.values():
        group = sorted({r["row"]: r for r in group}.values(), key=lambda r: r["row"])
        if len(group) >= 2:
            signature = tuple((r["row"], r["tooling_number"]) for r in group)
            unique[signature] = group
    return list(unique.values())


def classify(group: list[dict[str, Any]]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if len(group) < 2:
        return "single", ["only one tooling row"]

    part_ids = [r["customer_part_no"] or r["part_name"] or r["internal_name"] for r in group]
    tooling_ids = [r["tooling_number"] for r in group]
    different_parts = len(set(filter(None, part_ids))) >= 2
    different_tooling = len(set(filter(None, tooling_ids))) >= 2

    if not different_tooling:
        return "single_tooling", ["tooling number is not distinct"]
    if not different_parts:
        return "same_part_identity", ["part identity is not distinct"]

    cavity_values = {r["cavity"] for r in group if r["cavity"] is not None}
    evidence = [r["cavity_evidence"] for r in group if r["cavity_evidence"]]
    same_material = len({norm(r["material"]) for r in group}) == 1 and bool(norm(group[0]["material"]))
    same_spec = len({norm(r["spec"]) for r in group}) == 1 and bool(norm(group[0]["spec"]))
    shared_anchor = any(len({r["anchors"][field] for r in group}) == 1 for field in ("material", "spec", "remark"))
    same_customer = len({norm(r["customer"]) for r in group}) == 1 and bool(norm(group[0]["customer"]))

    if not same_customer:
        reasons.append("customer context differs or is missing")
    if not evidence:
        reasons.append("no explicit 一出N/左右证据")
    if len(cavity_values) != 1:
        reasons.append("cavity evidence is missing or inconsistent")
    if not same_material:
        reasons.append("material is missing or differs")
    if not same_spec:
        reasons.append("TWP/spec is missing or differs")
    if not shared_anchor:
        reasons.append("no shared Excel merge/source anchor")

    if not reasons:
        return "mergeable", ["explicit one-out evidence, distinct parts/toolings, shared source block"]
    return "undetermined", reasons


def main() -> int:
    workbook = xlrd.open_workbook(str(EXCEL_PATH), formatting_info=True)
    summary = defaultdict(int)
    groups: list[dict[str, Any]] = []

    for sheet_index, sheet in enumerate(workbook.sheets()):
        header = header_row(sheet)
        if header is None:
            continue
        merges = merged_map(sheet)
        last_customer = ""
        records: list[dict[str, Any]] = []
        for row in range(header + 1, sheet.nrows):
            customer = value_at(sheet, row, 1, merges) or last_customer
            if value_at(sheet, row, 1, merges):
                last_customer = customer
            record = {
                "row": row + 1,
                "customer": customer,
                "customer_part_no": value_at(sheet, row, 2, merges),
                "part_name": value_at(sheet, row, 3, merges) or value_at(sheet, row, 4, merges),
                "internal_name": value_at(sheet, row, 6, merges),
                "tooling_number": value_at(sheet, row, 5, merges),
                "mold_type": value_at(sheet, row, 7, merges),
                "mold_count": value_at(sheet, row, 8, merges),
                "material": value_at(sheet, row, 9, merges),
                "spec": value_at(sheet, row, 10, merges),
                "remark": value_at(sheet, row, 11, merges),
                "anchors": {
                    field: anchor_at(row, col, merges)
                    for field, col in (("material", 9), ("spec", 10), ("remark", 11))
                },
            }
            cavity, evidence = parse_one_out(record["spec"] + record["remark"])
            record["cavity"] = cavity
            record["cavity_evidence"] = evidence
            records.append(record)

        for group in source_groups(records):
            kind, reasons = classify(group)
            if kind not in {"mergeable", "undetermined"}:
                continue
            summary[kind] += 1
            groups.append({
                "sheet_index": sheet_index,
                "sheet": sheet.name,
                "rows": [r["row"] for r in group],
                "classification": kind,
                "reasons": reasons,
                "customer": group[0]["customer"],
                "parts": [
                    {
                        "row": r["row"],
                        "customer_part_no": r["customer_part_no"],
                        "part_name": r["part_name"],
                        "internal_name": r["internal_name"],
                        "tooling_number": r["tooling_number"],
                        "mold_type": r["mold_type"],
                        "material": r["material"],
                        "spec": r["spec"],
                        "cavity": r["cavity"],
                        "cavity_evidence": r["cavity_evidence"],
                    }
                    for r in group
                ],
            })

    report = {
        "source": str(EXCEL_PATH),
        "rule": {
            "tooling_number": "never merge",
            "shared_fields": ["material", "spec/TWP", "cavity"],
            "required_evidence": ["same source block/merge anchor", "explicit one-out evidence", "distinct part and tooling identities"],
        },
        "summary": dict(summary),
        "groups": groups,
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Shared mold source-block audit", "", f"Source: `{EXCEL_PATH}`", "", "## Summary", ""]
    for key in ("mergeable", "undetermined"):
        lines.append(f"- {key}: {summary[key]}")
    lines += ["", "## Groups", ""]
    for item in groups:
        lines.append(f"### {item['classification']} · {item['sheet']} · rows {item['rows'][0]}-{item['rows'][-1]}")
        lines.append(f"- Customer: {item['customer']}")
        lines.append(f"- Reasons: {'; '.join(item['reasons'])}")
        lines.append("- Parts/toolings:")
        for part in item["parts"]:
            lines.append(f"  - row {part['row']}: {part['customer_part_no'] or '-'} / {part['part_name'] or '-'} → {part['tooling_number'] or '-'}; material={part['material'] or '-'}; TWP={part['spec'] or '-'}; cavity={part['cavity'] or '-'}")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"summary": dict(summary), "groups": len(groups), "json": str(OUT_JSON), "markdown": str(OUT_MD)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
