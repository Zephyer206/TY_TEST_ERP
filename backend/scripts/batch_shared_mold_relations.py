"""Audit and batch-create explicit shared-mold relations from the source workbook.

The workbook is the only source of truth.  This script never changes tooling or
part rows; it creates a separate, auditable relation table.  A dry run is the
default.  Use ``--apply`` only after reviewing the generated report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import xlrd
from sqlalchemy import select, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import async_session_maker  # noqa: E402
from app.models.tooling import Tooling  # noqa: E402
from app.models.tooling_shared_relation import ToolingSharedRelation  # noqa: E402


SUFFIX_PATTERN = r"(?:-(?:\d+|[A-Z]))*"
ID_RE = re.compile(
    r"[A-Z][A-Z0-9]{1,7}-[A-Z]+\d{3,6}"
    + SUFFIX_PATTERN
    + r"(?:/(?:-?\d+" + SUFFIX_PATTERN + r"|[A-Z]+\d{1,6}" + SUFFIX_PATTERN + r"))*",
    re.IGNORECASE,
)
FULL_ID_RE = re.compile(
    r"^[A-Z][A-Z0-9]{1,7}-[A-Z]+\d{3,6}" + SUFFIX_PATTERN + r"$", re.IGNORECASE
)
CODE_RE = re.compile(
    r"^(?P<family>[A-Z]+)(?P<number>\d{3,6})(?P<suffix>" + SUFFIX_PATTERN + r")$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Evidence:
    sheet: str
    row: int
    source_number: str
    target_expression: str
    note: str


@dataclass(frozen=True)
class IgnoredReference:
    sheet: str
    row: int
    source_number: str
    referenced_numbers: str
    note: str
    reason: str


@dataclass(frozen=True)
class Candidate:
    source_number: str
    target_number: str
    source_id: int
    target_id: int
    sheet: str
    row: int
    note: str
    scope: str = "set"


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace("\u3000", " ").strip()


def split_code(code: str) -> tuple[str, str, str | None] | None:
    """Return (vendor prefix including hyphen, product family, suffix)."""
    code = code.strip().upper()
    if "-" not in code:
        return None
    vendor, body = code.split("-", 1)
    parsed = CODE_RE.match(body)
    if not parsed:
        return None
    return f"{vendor}-", parsed.group("family"), parsed.group("number"), parsed.group("suffix")


def expand_expression(expression: str) -> list[str]:
    """Expand the workbook's common slash shorthand into atomic mold numbers."""
    expression = (
        expression.upper()
        .replace("／", "/")
        .replace("\\", "/")
        .replace("–", "-")
        .replace("—", "-")
        .strip(" .,:;()[]{}")
    )
    if not FULL_ID_RE.match(expression) and "/" not in expression:
        return []
    segments = expression.split("/")
    first = segments[0]
    parsed = split_code(first)
    if not parsed:
        return []
    vendor, family, number, first_suffix = parsed
    width = len(number)
    result: list[str] = []

    def add(fam: str, num: str, suffix: str | None) -> None:
        value = f"{vendor}{fam}{num}{suffix or ''}"
        if value not in result:
            result.append(value)

    # Q0047/48-1/2 means Q0047-1, Q0047-2, Q0048-1, Q0048-2.
    if first_suffix in (None, "") and len(segments) >= 3:
        second = segments[1]
        second_match = re.fullmatch(r"(?P<num>\d{1,6})(?P<suffix>-\d+)", second)
        trailing_suffixes = [s[1:] if s.startswith("-") else s for s in segments[2:]]
        if second_match and all(re.fullmatch(r"\d+", s) for s in trailing_suffixes):
            suffixes = [second_match.group("suffix")[1:], *trailing_suffixes]
            numbers = [number, second_match.group("num").zfill(width)]
            for num in numbers:
                for suffix in suffixes:
                    add(family, num, f"-{suffix}")
            return result

    add(family, number, first_suffix)
    current_family, current_number, current_suffix = family, number, first_suffix
    for segment in segments[1:]:
        segment = segment.strip()
        if not segment:
            continue
        if segment.startswith("-") and segment[1:].isdigit():
            current_suffix = segment
            add(current_family, current_number, current_suffix)
            continue
        full_code = re.fullmatch(
            r"(?P<family>[A-Z]+)(?P<number>\d{1,6})(?P<suffix>" + SUFFIX_PATTERN + r")",
            segment,
        )
        if full_code:
            current_family = full_code.group("family")
            current_number = full_code.group("number").zfill(width)
            current_suffix = full_code.group("suffix")
            add(current_family, current_number, current_suffix)
            continue
        number_suffix = re.fullmatch(
            r"(?P<number>\d{1,6})(?P<suffix>" + SUFFIX_PATTERN + r")",
            segment,
        )
        if number_suffix:
            segment_suffix = number_suffix.group("suffix")
            if not segment_suffix and current_suffix:
                current_suffix = f"-{number_suffix.group('number')}"
                add(current_family, current_number, current_suffix)
            else:
                current_number = number_suffix.group("number").zfill(width)
                current_suffix = segment_suffix or current_suffix
                add(current_family, current_number, current_suffix)
    return result


def extract_expressions(text_value: str) -> list[str]:
    """Extract only mold-number expressions, ignoring ordinary prose."""
    normalized = clean(text_value).upper()
    expressions = []
    for match in ID_RE.finditer(normalized):
        expression = match.group(0).rstrip("-/. ")
        if expression not in expressions:
            expressions.append(expression)
    return expressions


def expand_text(text_value: str) -> list[str]:
    values: list[str] = []
    for expression in extract_expressions(text_value):
        for value in expand_expression(expression):
            if value not in values:
                values.append(value)
    return values


def is_explicit_shared_note(note: str) -> bool:
    """Require an explicit sharing/borrowing phrase, not just any mold ID."""
    normalized = clean(note)
    if any(marker in normalized for marker in ("共用", "共模", "借用", "使用", "同模")):
        return True
    # Notes such as "同TYA-Q0011" or "与TYE-Q0199一套" omit the word 共模.
    for match in ID_RE.finditer(normalized.upper()):
        prefix = normalized[max(0, match.start() - 16) : match.start()]
        if re.search(r"(?:同|与|和|及)\s*[\u4e00-\u9fffA-Za-z0-9、，,()（）-]{0,10}$", prefix):
            return True
        suffix = normalized[match.end() : match.end() + 16]
        if "一套" in suffix:
            return True
    return False


def find_headers(sheet: xlrd.sheet.Sheet) -> tuple[int, dict[str, int]] | None:
    for row in range(min(sheet.nrows, 12)):
        labels = [clean(sheet.cell_value(row, col)) for col in range(sheet.ncols)]
        tooling_col = next(
            (col for col, label in enumerate(labels) if label in {"本厂产品编号", "模具编号"}),
            None,
        )
        # Some sheets repeat a later "备注" column for pricing/status notes;
        # the first remark column belongs to the authoritative mold data.
        remark_col = next(
            (col for col, label in enumerate(labels) if label in {"备注", "备 注"}),
            None,
        )
        if tooling_col is not None and remark_col is not None:
            return row, {"tooling": tooling_col, "remark": remark_col}
    return None


def read_evidence(workbook_path: Path) -> tuple[list[Evidence], list[IgnoredReference]]:
    workbook = xlrd.open_workbook(workbook_path, on_demand=True)
    evidence: list[Evidence] = []
    ignored: list[IgnoredReference] = []
    for sheet_name in workbook.sheet_names():
        sheet = workbook.sheet_by_name(sheet_name)
        header = find_headers(sheet)
        if not header:
            continue
        header_row, columns = header
        for row in range(header_row + 1, sheet.nrows):
            source = clean(sheet.cell_value(row, columns["tooling"]))
            note = clean(sheet.cell_value(row, columns["remark"]))
            if not source or not note:
                continue
            source_ids = expand_text(source)
            note_ids = expand_text(note)
            if not source_ids or not note_ids:
                continue
            source_set = set(source_ids)
            target_ids = [value for value in note_ids if value not in source_set]
            if not target_ids:
                continue
            if not is_explicit_shared_note(note):
                ignored.append(
                    IgnoredReference(
                        sheet=sheet_name,
                        row=row + 1,
                        source_number=source,
                        referenced_numbers=", ".join(target_ids),
                        note=note,
                        reason="reference_without_explicit_shared_mold_phrase",
                    )
                )
                continue
            evidence.append(
                Evidence(
                    sheet=sheet_name,
                    row=row + 1,
                    source_number=source,
                    target_expression=", ".join(target_ids),
                    note=note,
                )
            )
    return evidence, ignored


def display_number(tooling: Tooling) -> str:
    return clean(tooling.tooling_number or tooling.tooling_no)


async def load_toolings() -> tuple[dict[str, list[Tooling]], dict[int, Tooling]]:
    async with async_session_maker() as session:
        rows = (await session.execute(select(Tooling))).scalars().all()
    by_number: dict[str, list[Tooling]] = defaultdict(list)
    by_id = {tooling.id: tooling for tooling in rows}
    for tooling in rows:
        number = display_number(tooling).upper()
        if number:
            by_number[number].append(tooling)
    return by_number, by_id


def resolve(number: str, by_number: dict[str, list[Tooling]]) -> tuple[Tooling | None, str]:
    matches = by_number.get(number.upper(), [])
    if len(matches) == 1:
        return matches[0], "exact"
    if not matches:
        return None, "unmatched"
    return None, "ambiguous"


async def build_report(workbook_path: Path) -> dict:
    evidence, ignored = read_evidence(workbook_path)
    by_number, by_id = await load_toolings()
    candidates: dict[tuple[int, int], Candidate] = {}
    unresolved: list[dict] = []
    ambiguous: list[dict] = []
    for item in evidence:
        source_numbers = expand_text(item.source_number)
        target_numbers = [x.strip() for x in item.target_expression.split(",") if x.strip()]
        source_rows: list[Tooling] = []
        target_rows: list[Tooling] = []
        for number in source_numbers:
            tooling, status = resolve(number, by_number)
            if tooling:
                source_rows.append(tooling)
            elif status == "ambiguous":
                ambiguous.append({"kind": "source", "number": number, "sheet": item.sheet, "row": item.row, "note": item.note})
            else:
                unresolved.append({"kind": "source", "number": number, "sheet": item.sheet, "row": item.row, "note": item.note})
        for number in target_numbers:
            tooling, status = resolve(number, by_number)
            if tooling:
                target_rows.append(tooling)
            elif status == "ambiguous":
                ambiguous.append({"kind": "target", "number": number, "sheet": item.sheet, "row": item.row, "note": item.note})
            else:
                unresolved.append({"kind": "target", "number": number, "sheet": item.sheet, "row": item.row, "note": item.note})
        if not source_rows or not target_rows:
            continue
        for source in source_rows:
            for target in target_rows:
                if source.id == target.id:
                    continue
                left, right = sorted((source.id, target.id))
                left_tooling = by_id[left]
                right_tooling = by_id[right]
                candidates.setdefault(
                    (left, right),
                    Candidate(
                        source_number=display_number(left_tooling),
                        target_number=display_number(right_tooling),
                        source_id=left,
                        target_id=right,
                        sheet=item.sheet,
                        row=item.row,
                        note=item.note,
                    ),
                )
    existing: set[tuple[int, int]] = set()
    async with async_session_maker() as session:
        try:
            rows = (await session.execute(select(ToolingSharedRelation.tooling_id, ToolingSharedRelation.related_tooling_id))).all()
            existing = {(min(a, b), max(a, b)) for a, b in rows}
        except Exception:
            # The relation table is intentionally created only when --apply is used.
            existing = set()
    new_candidates = [candidate for key, candidate in candidates.items() if key not in existing]
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "workbook": str(workbook_path),
        "evidence_rows": len(evidence),
        "candidate_pairs": len(candidates),
        "existing_pairs": len(existing),
        "new_pairs": len(new_candidates),
        "unresolved_count": len(unresolved),
        "ambiguous_count": len(ambiguous),
        "ignored_reference_count": len(ignored),
        "candidates": [asdict(candidate) for candidate in new_candidates],
        "unresolved": unresolved,
        "ambiguous": ambiguous,
        "ignored_references": [asdict(item) for item in ignored],
    }


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tooling_shared_relations (
    id SERIAL PRIMARY KEY,
    tooling_id INTEGER NOT NULL REFERENCES tooling(id) ON DELETE CASCADE,
    related_tooling_id INTEGER NOT NULL REFERENCES tooling(id) ON DELETE CASCADE,
    relation_type VARCHAR(30) NOT NULL DEFAULT 'SHARED_MOLD',
    relation_scope VARCHAR(20) NOT NULL DEFAULT 'set',
    source_sheet VARCHAR(255),
    source_row INTEGER,
    source_note TEXT,
    confidence VARCHAR(30) NOT NULL DEFAULT 'EXPLICIT_NOTE',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_tooling_shared_relations_distinct CHECK (tooling_id <> related_tooling_id),
    CONSTRAINT uq_tooling_shared_relations_pair UNIQUE (tooling_id, related_tooling_id, relation_type)
)
"""

CREATE_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS ix_tooling_shared_relations_tooling_id "
    "ON tooling_shared_relations (tooling_id)",
    "CREATE INDEX IF NOT EXISTS ix_tooling_shared_relations_related_tooling_id "
    "ON tooling_shared_relations (related_tooling_id)",
)


async def apply_report(report: dict) -> int:
    async with async_session_maker() as session:
        await session.execute(text(CREATE_TABLE_SQL))
        for statement in CREATE_INDEX_SQL:
            await session.execute(text(statement))
        inserted = 0
        for item in report["candidates"]:
            exists = await session.scalar(
                select(ToolingSharedRelation.id).where(
                    ToolingSharedRelation.tooling_id == item["source_id"],
                    ToolingSharedRelation.related_tooling_id == item["target_id"],
                    ToolingSharedRelation.relation_type == "SHARED_MOLD",
                )
            )
            if exists:
                continue
            session.add(
                ToolingSharedRelation(
                    tooling_id=item["source_id"],
                    related_tooling_id=item["target_id"],
                    relation_type="SHARED_MOLD",
                    relation_scope=item.get("scope", "set"),
                    source_sheet=item["sheet"],
                    source_row=item["row"],
                    source_note=item["note"],
                    confidence="EXPLICIT_NOTE",
                )
            )
            inserted += 1
        await session.commit()
        return inserted


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, default=ROOT / "excel" / "五金模具及产品清单表.xls")
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "shared_mold_relations_dry_run.json")
    parser.add_argument("--apply", action="store_true", help="Create the relation table and insert new pairs")
    args = parser.parse_args()
    report = await build_report(args.workbook)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.apply:
        inserted = await apply_report(report)
        print(f"APPLIED inserted={inserted} new_pairs={report['new_pairs']}")
    else:
        print(
            "DRY_RUN "
            f"evidence={report['evidence_rows']} candidates={report['candidate_pairs']} "
            f"new={report['new_pairs']} unresolved={report['unresolved_count']} "
            f"ambiguous={report['ambiguous_count']} report={args.report}"
        )
        for item in report["candidates"][:20]:
            print(f"PAIR {item['source_number']} <-> {item['target_number']} ({item['sheet']}:{item['row']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
