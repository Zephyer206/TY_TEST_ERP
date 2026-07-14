#!/usr/bin/env python3
"""
Legacy Customer Reference Classifier - Offline Analysis Only

Pure deterministic classifier for 1038 legacy customer reference parts.
NO database connection. Reads JSON audit files and Excel, produces classification report.

Classification categories:
1. clear_deprecated_only: Active non-target aliases already cover the single proven Excel customer
2. unique_canonical_mapping: Exactly one canonical customer proven, alias absent/incomplete
3. duplicate_legacy_part: Exact same Excel/tooling/customer identity exists as non-target part
4. new_customer_required: Excel proves a customer (e.g., Wuhan) but no safe canonical DB customer
5. invalid_template_part: Part proven to be imported header/template row (delete candidate)
6. ambiguous: No or conflicting evidence; never guess

Requirements:
- Parse Excel with merged-cell awareness
- Map customer names ONLY via audit exact_matches (NO location_or_qualifier)
- Acceptable name mapping: 美的集团 -> customer id 16
- Source sheet hints limit search set only; not customer evidence by themselves
- Skip header/template identities: 客户, 客户名称, 模具编号, etc.
- Exact row evidence only: exact mold/tooling OR exact customer_part + internal_name
- Pure deterministic: assert 1038 input = 1038 output classifications
"""

import sys
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from collections import defaultdict
from decimal import Decimal

# Import Excel parsing helpers
sys.path.insert(0, str(Path(__file__).parent))
from import_excel_authoritative import (
    detect_headers,
    parse_row,
    get_merged_cell_value,
    build_merged_cells_map,
    is_special_sheet
)

try:
    import xlrd
except ImportError:
    print("[FATAL] xlrd not installed. Run: pip install xlrd")
    sys.exit(1)


def safe_json_serialize(obj):
    """Safely serialize objects for JSON output, handling Decimal and other types."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime,)):
        return obj.isoformat()
    elif isinstance(obj, set):
        return list(obj)
    elif obj is None:
        return None
    return obj


def find_latest_file(pattern: Path) -> Optional[Path]:
    """Find the most recent file matching pattern."""
    parent = pattern.parent
    glob_pattern = pattern.name

    matching = list(parent.glob(glob_pattern))
    if not matching:
        return None

    # Sort by modification time, newest first
    return sorted(matching, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def load_customer_import_audit(audit_path: Path) -> Dict[str, Any]:
    """Load customer import audit with name normalization mappings."""
    print(f"[INFO] Loading customer import audit: {audit_path.name}")

    with open(audit_path, 'r', encoding='utf-8') as f:
        audit = json.load(f)

    return audit


def load_raw_evidence(evidence_path: Path) -> Dict[str, Any]:
    """Load raw evidence JSON with 1038 invalid customer parts."""
    print(f"[INFO] Loading raw evidence: {evidence_path.name}")

    with open(evidence_path, 'r', encoding='utf-8') as f:
        evidence = json.load(f)

    # Validate count
    assert evidence['validation']['total_parts_affected'] == 1038, \
        f"Expected 1038 parts, got {evidence['validation']['total_parts_affected']}"

    return evidence


def build_customer_name_map(audit: Dict[str, Any]) -> Dict[str, Tuple[int, str]]:
    """
    Build parsed_customer_name -> (canonical_id, canonical_name) map.

    ONLY uses exact_matches from audit. NO location_or_qualifier mappings.
    Safe acceptable name mapping: 温州力邦企业 -> customer id 16 / 温州力邦企业有限公司
    """
    name_map = {}

    # Process exact matches only
    for entry in audit['name_normalization']['exact_matches']:
        parsed = entry['parsed']
        customer_id = entry['customer_id']
        db_name = entry['db_name']

        name_map[parsed] = (customer_id, db_name)

    # Add safe acceptable name mapping
    name_map['温州力邦企业'] = (16, '温州力邦企业有限公司')

    print(f"[INFO] Built customer name map with {len(name_map)} exact matches + safe acceptable")
    print(f"[WARN] Rejecting location_or_qualifier mappings (e.g., Wuhan variants)")

    return name_map


def build_source_sheet_hints(audit: Dict[str, Any]) -> Dict[int, str]:
    """
    Build invalid_customer_id -> source_sheet_hint map from audit duplicate_customers.

    High-confidence empty duplicates use name; truncated uses reconstructed_customer_label when present.
    """
    hints = {}

    if 'duplicate_customers' in audit:
        duplicate_customers = audit['duplicate_customers']

        # Process high_confidence_empty_duplicates
        if 'high_confidence_empty_duplicates' in duplicate_customers:
            for record in duplicate_customers['high_confidence_empty_duplicates']:
                customer_id = record.get('id')
                if customer_id:
                    hints[customer_id] = record.get('name', '')

        # Process truncated records
        if 'truncated' in duplicate_customers:
            for record in duplicate_customers['truncated']:
                customer_id = record.get('id')
                if customer_id:
                    reconstructed = record.get('reconstructed_customer_label')
                    hints[customer_id] = reconstructed if reconstructed else record.get('name', '')

    # Assert exactly 60 hints built
    assert len(hints) == 60, f"Expected exactly 60 source sheet hints, got {len(hints)}"

    print(f"[INFO] Built {len(hints)} source sheet hints from audit duplicate_customers")
    return hints


def is_header_or_template_value(value: Optional[str]) -> bool:
    """
    Detect if a value is a header/template placeholder.

    Returns True for real template identities, placeholder patterns, or None/empty values.
    Does NOT treat normal Chinese text as template.
    """
    if not value:
        return True  # None/empty values are considered template placeholders

    normalized = str(value).strip()

    # Empty or whitespace only
    if not normalized:
        return True

    # Real header/template identities from Excel (Chinese characters)
    template_identities = {
        '客户', '客户名称', '客户件号', '模具编号', '内部名称', '产品名称',
        '产品编号', '模具号', '本厂产品名称', '本厂产品编号',
        '原图产品编号', '原图产品名称'
    }
    if normalized in template_identities:
        return True

    # Placeholder patterns: underscore, ellipsis, hash symbols
    if normalized in ['_', '__', '___', '...', '…', '#', '##', '###']:
        return True

    # All underscores
    if normalized and all(c == '_' for c in normalized):
        return True

    # All hash symbols
    if normalized and all(c == '#' for c in normalized):
        return True

    return False


def is_explicit_header_or_template_value(value: Optional[str]) -> bool:
    """Return True only for a non-empty explicit header/template placeholder."""
    if value is None:
        return False
    normalized = str(value).strip()
    if not normalized:
        return False
    return is_header_or_template_value(normalized)


def has_explicit_template_identity(part: Dict[str, Any]) -> bool:
    """
    Check if a part has explicit template/header identity in key fields.

    Checks 5 fields: mold_number, press_tonnage, ppap_no, customer_product_no, internal_name.

    Returns True ONLY if ANY non-empty field is an explicit template/header placeholder.
    Returns False if all fields are empty OR if they only contain normal business values.

    This differs from is_header_or_template_value which treats None/empty as True.
    """
    field_names = ['mold_number', 'press_tonnage', 'ppap_no', 'customer_product_no', 'internal_name']

    for field_name in field_names:
        if is_explicit_header_or_template_value(part.get(field_name)):
            return True

    # No explicit template identity found in non-empty fields
    return False


def looks_like_tooling_identifier(value: Optional[str]) -> bool:
    """
    Check if a value looks like a real tooling identifier.

    Returns True for values like TY*/GB* containing -Q/-M pattern.
    Excludes headers and empty values.
    """
    if not value or is_header_or_template_value(value):
        return False

    normalized = str(value).strip()

    # Must start with TY or GB (common tooling prefixes)
    if not (normalized.startswith('TY') or normalized.startswith('GB')):
        return False

    # Must contain -Q or -M (tooling type indicators)
    if '-Q' not in normalized and '-M' not in normalized:
        return False

    return True


def is_known_mold_type(value: Optional[str]) -> bool:
    """
    Check if value is a known mold type designation (not an internal name).

    Known mold types: 冲模, 折弯模, 连续模, 端子模, 工程模, 拉伸模+冲孔, etc.
    """
    if not value:
        return False

    normalized = str(value).strip()

    # Known mold type keywords
    mold_types = {
        '冲模', '折弯模', '连续模', '端子模', '工程模',
        '拉伸模', '冲孔模', '拉伸模+冲孔', '冲孔+折弯'
    }

    return normalized in mold_types


def build_tooling_candidates(part: Dict[str, Any]) -> List[str]:
    """
    Build tooling identifier candidates from part fields.

    Legacy shifted-column recovery: some old parts have real tooling number
    in press_tonnage or ppap_no fields instead of mold_number.

    Returns list of normalized tooling candidates (non-empty, non-header).
    """
    candidates = []

    # Check mold_number first (standard location)
    mold_number = part.get('mold_number')
    if mold_number and looks_like_tooling_identifier(mold_number):
        candidates.append(normalize_for_matching(mold_number))

    # Check press_tonnage (legacy shifted column)
    press_tonnage = part.get('press_tonnage')
    if press_tonnage and looks_like_tooling_identifier(press_tonnage):
        candidates.append(normalize_for_matching(press_tonnage))

    # Check ppap_no (legacy shifted column)
    ppap_no = part.get('ppap_no')
    if ppap_no and looks_like_tooling_identifier(ppap_no):
        candidates.append(normalize_for_matching(ppap_no))

    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)

    return unique_candidates


def build_internal_name_candidates(part: Dict[str, Any]) -> List[str]:
    """
    Build internal name candidates from part fields.

    Legacy shifted-column recovery: some old parts have real internal name
    in mold_number field, while internal_name contains a mold type.

    Returns list of normalized internal name candidates (excluding tooling IDs,
    headers, and known mold types).
    """
    candidates = []

    # Check internal_name first (standard location)
    internal_name = part.get('internal_name')
    if (internal_name and
        not is_header_or_template_value(internal_name) and
        not looks_like_tooling_identifier(internal_name) and
        not is_known_mold_type(internal_name)):
        candidates.append(normalize_for_matching(internal_name))

    # Check mold_number (legacy shifted column - may contain internal name)
    mold_number = part.get('mold_number')
    if (mold_number and
        not is_header_or_template_value(mold_number) and
        not looks_like_tooling_identifier(mold_number) and
        not is_known_mold_type(mold_number)):
        candidates.append(normalize_for_matching(mold_number))

    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)

    return unique_candidates


def compute_excel_hash(excel_path: Path) -> str:
    """Compute SHA256 hash of Excel file."""
    sha256 = hashlib.sha256()
    with open(excel_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def parse_excel_sheets(excel_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse all Excel data sheets with merged-cell awareness.

    Returns: {sheet_name: [normalized_row_dicts]}
    Each row dict contains: source_sheet, source_row, parsed_customer_name,
    customer_part_no, tooling_number, internal_name, material, T/W/P, etc.

    Skips rows with header/template placeholder identities.
    """
    print(f"[INFO] Parsing Excel: {excel_path.name}")

    workbook = xlrd.open_workbook(str(excel_path), formatting_info=True)
    sheets_data = {}
    skipped_template_rows = 0

    for sheet_idx in range(workbook.nsheets):
        sheet = workbook.sheet_by_index(sheet_idx)
        sheet_name = sheet.name

        # Skip special sheets
        is_special, _ = is_special_sheet(sheet_name)
        if is_special:
            continue

        # Build merged cells map
        merged_cells_map = build_merged_cells_map(sheet)

        # Detect headers
        header_row_idx, column_map = detect_headers(sheet)
        if header_row_idx is None:
            continue

        sheet_rows = []
        last_customer = None

        # Parse data rows
        for row_idx in range(header_row_idx + 1, sheet.nrows):
            # Extract row values with merged cell support
            row_values = [
                get_merged_cell_value(sheet, row_idx, col_idx, merged_cells_map)
                for col_idx in range(sheet.ncols)
            ]

            # Parse row
            try:
                parsed_data = parse_row(row_values, column_map, sheet_name, last_customer)

                # Update last_customer
                if parsed_data.get('parsed_customer_name'):
                    col_idx = column_map.get('customer_name')
                    if col_idx is not None and col_idx < len(row_values):
                        cell_val = row_values[col_idx]
                        if cell_val and str(cell_val).strip():
                            last_customer = parsed_data['parsed_customer_name']

                # Add metadata
                parsed_data['source_sheet'] = sheet_name
                parsed_data['source_row'] = row_idx + 1

                # Skip only explicit non-empty header/template placeholders. Missing
                # internal names or customer part numbers are valid legacy Excel rows.
                if any(is_explicit_header_or_template_value(value) for value in (
                    parsed_data.get('parsed_customer_name'),
                    parsed_data.get('parsed_tooling_number'),
                    parsed_data.get('parsed_internal_name'),
                    parsed_data.get('parsed_customer_part_no'),
                )):
                    skipped_template_rows += 1
                    continue

                # Exact tooling is authoritative even when optional identity fields are blank.
                if (parsed_data.get('parsed_customer_name') and
                    parsed_data.get('parsed_tooling_number')):
                    sheet_rows.append(parsed_data)

            except Exception as e:
                # Skip error rows silently for offline processing
                pass

        if sheet_rows:
            sheets_data[sheet_name] = sheet_rows
            print(f"  [INFO] {sheet_name}: {len(sheet_rows)} valid rows")

    total_rows = sum(len(rows) for rows in sheets_data.values())
    print(f"[INFO] Parsed {len(sheets_data)} data sheets, {total_rows} total valid rows")
    print(f"[INFO] Skipped {skipped_template_rows} header/template placeholder rows")

    return sheets_data


def normalize_for_matching(value: Optional[str]) -> str:
    """Normalize string for fuzzy matching (lowercase, strip, collapse whitespace)."""
    if not value:
        return ""
    return re.sub(r'\s+', ' ', str(value).strip().lower())


def match_excel_rows(
    part_evidence: Dict[str, Any],
    excel_data: Dict[str, List[Dict[str, Any]]],
    customer_name_map: Dict[str, Tuple[int, str]],
    source_sheet_hints: Dict[int, str]
) -> Tuple[List[Dict[str, Any]], Set[int], List[str]]:
    """
    Find matching Excel rows for a part using exact row evidence only.

    Returns: (matched_rows, matched_canonical_customer_ids, match_methods)

    Exact row evidence only:
    - Exact non-generic tooling candidates (mold_number, press_tonnage, ppap_no)
    - If multiple rows, narrow by customer_product_no then internal_name candidates
    - OR exact customer_product_no + normalized internal_name candidates

    Matched rows include ALL exact matches (even unmapped customers).
    Matched canonical IDs only include customers in customer_name_map.
    """
    part = part_evidence['part']
    invalid_customer = part_evidence['invalid_customer']

    # Build tooling and internal name candidates (legacy shifted-column recovery)
    tooling_candidates = build_tooling_candidates(part)
    internal_name_candidates = build_internal_name_candidates(part)
    customer_product_no = normalize_for_matching(part.get('customer_product_no'))

    # Get source sheet hint (limits search set only)
    source_sheet_hint = source_sheet_hints.get(invalid_customer['id'], '')

    matched_rows = []
    matched_canonical_ids = set()
    match_methods = []

    # Determine search set: if source sheet hint exists, limit to that sheet; otherwise search all
    search_data = {}
    if source_sheet_hint and source_sheet_hint in excel_data:
        search_data[source_sheet_hint] = excel_data[source_sheet_hint]
    else:
        search_data = excel_data

    # Skip matching for parts with explicit template identities
    if has_explicit_template_identity(part):
        return [], set(), []

    # Priority A: Exact tooling candidate match
    if tooling_candidates:
        for tooling_candidate in tooling_candidates:
            tooling_matches = []
            for sheet_name, rows in search_data.items():
                for row in rows:
                    row_tooling = normalize_for_matching(row.get('parsed_tooling_number'))
                    if row_tooling and tooling_candidate == row_tooling:
                        tooling_matches.append(row)

            # If multiple tooling matches, narrow by customer_product_no
            if len(tooling_matches) > 1 and customer_product_no:
                narrowed = []
                for row in tooling_matches:
                    row_customer_part = normalize_for_matching(row.get('parsed_customer_part_no'))
                    if row_customer_part and customer_product_no == row_customer_part:
                        narrowed.append(row)
                if narrowed:
                    tooling_matches = narrowed

            # If still multiple, narrow by internal_name candidates
            if len(tooling_matches) > 1 and internal_name_candidates:
                for internal_candidate in internal_name_candidates:
                    narrowed = []
                    for row in tooling_matches:
                        row_internal = normalize_for_matching(row.get('parsed_internal_name'))
                        if row_internal and internal_candidate == row_internal:
                            narrowed.append(row)
                    if narrowed:
                        tooling_matches = narrowed
                        break  # Use first successful narrowing

            # Add ALL matched rows (even if customer not in map)
            for row in tooling_matches:
                if row not in matched_rows:  # Avoid duplicates
                    matched_rows.append(row)
                    row_customer_name = row.get('parsed_customer_name', '')
                    # Only add to canonical IDs if customer is mapped
                    if row_customer_name in customer_name_map:
                        canonical_id, _ = customer_name_map[row_customer_name]
                        matched_canonical_ids.add(canonical_id)
                    match_methods.append(f"exact_tooling:{row['source_sheet']}:{row['source_row']}")

    # Priority B: Exact customer_product_no + internal_name candidate match (only if no tooling matches)
    if not matched_rows and customer_product_no and internal_name_candidates:
        for internal_candidate in internal_name_candidates:
            for sheet_name, rows in search_data.items():
                for row in rows:
                    row_customer_part = normalize_for_matching(row.get('parsed_customer_part_no'))
                    row_internal = normalize_for_matching(row.get('parsed_internal_name'))

                    if (row_customer_part and customer_product_no == row_customer_part and
                        row_internal and internal_candidate == row_internal):

                        if row not in matched_rows:  # Avoid duplicates
                            matched_rows.append(row)
                            row_customer_name = row.get('parsed_customer_name', '')
                            # Only add to canonical IDs if customer is mapped
                            if row_customer_name in customer_name_map:
                                canonical_id, _ = customer_name_map[row_customer_name]
                                matched_canonical_ids.add(canonical_id)
                            match_methods.append(f"exact_customer_part+internal:{row['source_sheet']}:{row['source_row']}")

    return matched_rows, matched_canonical_ids, match_methods


def classify_part(
    part_evidence: Dict[str, Any],
    excel_data: Dict[str, List[Dict[str, Any]]],
    customer_name_map: Dict[str, Tuple[int, str]],
    source_sheet_hints: Dict[int, str]
) -> Dict[str, Any]:
    """
    Pure deterministic classifier for a single part.

    Returns classification result with category, evidence, and reason.
    """
    part = part_evidence['part']
    invalid_customer = part_evidence['invalid_customer']
    part_customer_aliases = part_evidence.get('part_customer_aliases', [])
    duplicate_candidates = part_evidence.get('duplicate_candidates', [])

    # Build candidates for evidence (legacy shifted-column recovery)
    tooling_candidates = build_tooling_candidates(part)
    internal_name_candidates = build_internal_name_candidates(part)

    # Check if this part has explicit template/header identities
    if has_explicit_template_identity(part):
        return {
            'part_id': part['id'],
            'invalid_customer_id': invalid_customer['id'],
            'invalid_customer_name': invalid_customer['name'],
            'category': 'invalid_template_part',
            'canonical_customer_id': None,
            'canonical_customer_name': None,
            'duplicate_part_id': None,
            'evidence': {
                'template_identities': {
                    'mold_number': part.get('mold_number'),
                    'press_tonnage': part.get('press_tonnage'),
                    'ppap_no': part.get('ppap_no'),
                    'customer_product_no': part.get('customer_product_no'),
                    'internal_name': part.get('internal_name')
                }
            },
            'reason': 'Part contains header/template placeholder identities (delete candidate)'
        }

    # Match Excel rows
    matched_excel_rows, matched_canonical_ids, match_methods = match_excel_rows(
        part_evidence, excel_data, customer_name_map, source_sheet_hints
    )

    # Compute unmapped customer names from matched rows
    unmapped_customer_names = set()
    for row in matched_excel_rows:
        customer_name = row.get('parsed_customer_name', '')
        if customer_name and customer_name not in customer_name_map:
            unmapped_customer_names.add(customer_name)

    # Build detailed evidence for matched rows (limit to reasonable count to avoid hundreds)
    excel_row_evidence = []
    if matched_excel_rows and len(matched_excel_rows) <= 10:  # Only store details for <= 10 matches
        for row, method in zip(matched_excel_rows, match_methods):
            excel_row_evidence.append({
                'match_method': method,
                'sheet': row['source_sheet'],
                'row': row['source_row'],
                'tooling': row.get('parsed_tooling_number'),
                'customer_part_no': row.get('parsed_customer_part_no'),
                'internal_name': row.get('parsed_internal_name'),
                'parsed_customer_name': row.get('parsed_customer_name')
            })
    elif matched_excel_rows:
        # Too many matches - store summary only
        excel_row_evidence = [{
            'match_method': 'summary_too_many_matches',
            'count': len(matched_excel_rows),
            'sheets': list(set(r['source_sheet'] for r in matched_excel_rows))
        }]

    # Check for duplicate parts (same tooling/customer identity, different customer_id)
    duplicate_part_id = None
    duplicate_customer_id = None
    for dup in duplicate_candidates:
        if dup['customer_id'] != invalid_customer['id']:
            # Check if this duplicate matches one of our canonical customers
            if dup['customer_id'] in matched_canonical_ids:
                # Verify exact identity match using tooling candidates
                dup_mold = normalize_for_matching(dup.get('mold_number'))
                for tooling_candidate in tooling_candidates:
                    if dup_mold and tooling_candidate and dup_mold == tooling_candidate:
                        duplicate_part_id = dup['id']
                        duplicate_customer_id = dup['customer_id']
                        break
                if duplicate_part_id:
                    break

    # Classification logic

    # Category 1: clear_deprecated_only
    # Active non-target aliases already cover the single proven Excel customer
    # Requires: at least one exact row proof AND exactly one canonical id
    if part_customer_aliases and matched_canonical_ids and len(matched_canonical_ids) == 1 and matched_excel_rows:
        alias_customer_ids = set(alias['customer_id'] for alias in part_customer_aliases)
        if matched_canonical_ids.issubset(alias_customer_ids):
            canonical_id = list(matched_canonical_ids)[0]
            canonical_name = customer_name_map.get(
                [r['parsed_customer_name'] for r in matched_excel_rows
                 if r['parsed_customer_name'] in customer_name_map][0]
            )[1] if matched_excel_rows else "unknown"

            return {
                'part_id': part['id'],
                'invalid_customer_id': invalid_customer['id'],
                'invalid_customer_name': invalid_customer['name'],
                'category': 'clear_deprecated_only',
                'canonical_customer_id': canonical_id,
                'canonical_customer_name': canonical_name,
                'duplicate_part_id': None,
                'evidence': {
                    'tooling_candidates': tooling_candidates,
                    'internal_name_candidates': internal_name_candidates,
                    'excel_row_evidence': excel_row_evidence,
                    'existing_aliases': len(part_customer_aliases),
                    'alias_customers': list(alias_customer_ids)
                },
                'reason': f'Aliases already cover canonical customer {canonical_id}'
            }

    # Category 3: duplicate_legacy_part
    # Exact same Excel/tooling/customer identity exists as non-target part
    # Requires: exact identity AND matching non-target canonical customer
    if duplicate_part_id and duplicate_customer_id and matched_excel_rows:
        canonical_name = customer_name_map.get(
            [r['parsed_customer_name'] for r in matched_excel_rows
             if r['parsed_customer_name'] in customer_name_map][0]
        )[1] if matched_excel_rows else "unknown"

        return {
            'part_id': part['id'],
            'invalid_customer_id': invalid_customer['id'],
            'invalid_customer_name': invalid_customer['name'],
            'category': 'duplicate_legacy_part',
            'canonical_customer_id': duplicate_customer_id,
            'canonical_customer_name': canonical_name,
            'duplicate_part_id': duplicate_part_id,
            'evidence': {
                'tooling_candidates': tooling_candidates,
                'internal_name_candidates': internal_name_candidates,
                'excel_row_evidence': excel_row_evidence,
                'duplicate_candidates': len(duplicate_candidates)
            },
            'reason': f'Duplicate of part {duplicate_part_id} with customer {duplicate_customer_id}'
        }

    # Category 2: unique_canonical_mapping
    # Exactly one canonical customer proven, alias absent/incomplete
    # Requires: at least one exact row proof AND exactly one canonical id AND no unmapped customers
    if len(matched_canonical_ids) == 1 and matched_excel_rows and not unmapped_customer_names:
        canonical_id = list(matched_canonical_ids)[0]

        # Get canonical name from first matched row
        canonical_name = None
        for row in matched_excel_rows:
            if row['parsed_customer_name'] in customer_name_map:
                canonical_name = customer_name_map[row['parsed_customer_name']][1]
                break

        if not canonical_name:
            canonical_name = "unknown"

        return {
            'part_id': part['id'],
            'invalid_customer_id': invalid_customer['id'],
            'invalid_customer_name': invalid_customer['name'],
            'category': 'unique_canonical_mapping',
            'canonical_customer_id': canonical_id,
            'canonical_customer_name': canonical_name,
            'duplicate_part_id': None,
            'evidence': {
                'tooling_candidates': tooling_candidates,
                'internal_name_candidates': internal_name_candidates,
                'excel_row_evidence': excel_row_evidence,
                'existing_aliases': len(part_customer_aliases)
            },
            'reason': f'Single canonical customer {canonical_id} proven by Excel evidence'
        }

    # Category 4: new_customer_required
    # Excel proves unmapped customer(s) but no safe canonical DB customer exists
    # If exactly one unmapped customer and no mapped canonical IDs, return new_customer_required
    if matched_excel_rows and unmapped_customer_names:
        if len(unmapped_customer_names) == 1 and not matched_canonical_ids:
            # Wuhan case: one unmapped customer, no conflicting mapped customers
            unmapped_name = list(unmapped_customer_names)[0]
            return {
                'part_id': part['id'],
                'invalid_customer_id': invalid_customer['id'],
                'invalid_customer_name': invalid_customer['name'],
                'category': 'new_customer_required',
                'canonical_customer_id': None,
                'canonical_customer_name': None,
                'duplicate_part_id': None,
                'evidence': {
                    'tooling_candidates': tooling_candidates,
                    'internal_name_candidates': internal_name_candidates,
                    'excel_row_evidence': excel_row_evidence,
                    'unmapped_customers': list(unmapped_customer_names)
                },
                'reason': f'Excel proves customer "{unmapped_name}" but no safe canonical mapping exists'
            }
        else:
            # Multiple unmapped customers or mixed mapped/unmapped - ambiguous conflict
            conflicts = []
            if matched_canonical_ids and unmapped_customer_names:
                conflicts.append(f'Mixed mapped customers {matched_canonical_ids} and unmapped {unmapped_customer_names}')
            elif len(unmapped_customer_names) > 1:
                conflicts.append(f'Multiple unmapped customers: {unmapped_customer_names}')

            return {
                'part_id': part['id'],
                'invalid_customer_id': invalid_customer['id'],
                'invalid_customer_name': invalid_customer['name'],
                'category': 'ambiguous',
                'canonical_customer_id': None,
                'canonical_customer_name': None,
                'duplicate_part_id': None,
                'evidence': {
                    'tooling_candidates': tooling_candidates,
                    'internal_name_candidates': internal_name_candidates,
                    'excel_row_evidence': excel_row_evidence,
                    'matched_canonical_ids': list(matched_canonical_ids),
                    'unmapped_customers': list(unmapped_customer_names),
                    'conflicts': conflicts
                },
                'reason': '; '.join(conflicts)
            }

    # Category 5: ambiguous
    # No or conflicting evidence
    conflicts = []
    if len(matched_canonical_ids) > 1:
        conflicts.append(f'Multiple canonical customers: {matched_canonical_ids}')
    if not matched_excel_rows:
        conflicts.append('No Excel evidence found')

    return {
        'part_id': part['id'],
        'invalid_customer_id': invalid_customer['id'],
        'invalid_customer_name': invalid_customer['name'],
        'category': 'ambiguous',
        'canonical_customer_id': None,
        'canonical_customer_name': None,
        'duplicate_part_id': None,
        'evidence': {
            'tooling_candidates': tooling_candidates,
            'internal_name_candidates': internal_name_candidates,
            'excel_row_evidence': excel_row_evidence if matched_excel_rows else [],
            'matched_canonical_ids': list(matched_canonical_ids),
            'unmapped_customers': list(unmapped_customer_names),
            'conflicts': conflicts
        },
        'reason': '; '.join(conflicts) if conflicts else 'Insufficient evidence'
    }


def main():
    """Main entry point."""
    print("="*70)
    print("Legacy Customer Reference Classifier - Offline Analysis")
    print("="*70)

    # Paths
    script_dir = Path(__file__).parent
    backup_dir = script_dir / 'backups'
    audit_dir = backup_dir / 'customer_import_audit'
    legacy_ref_dir = backup_dir / 'customer_cleanup' / 'legacy_ref_audit'
    excel_dir = script_dir.parent.parent / 'excel'

    # Find input files
    audit_path = audit_dir / 'customer_import_audit_1.json'
    evidence_pattern = legacy_ref_dir / 'raw_evidence_*.json'
    evidence_path = find_latest_file(evidence_pattern)
    excel_path = excel_dir / '五金模具及产品清单表.xls'

    if not audit_path.exists():
        print(f"[FATAL] Customer import audit not found: {audit_path}")
        return 1

    if not evidence_path:
        print(f"[FATAL] No raw evidence files found matching: {evidence_pattern}")
        return 1

    if not excel_path.exists():
        print(f"[FATAL] Excel file not found: {excel_path}")
        return 1

    # Load data
    audit = load_customer_import_audit(audit_path)
    raw_evidence = load_raw_evidence(evidence_path)
    customer_name_map = build_customer_name_map(audit)
    source_sheet_hints = build_source_sheet_hints(audit)

    # Compute Excel hash
    excel_hash = compute_excel_hash(excel_path)
    print(f"[INFO] Excel SHA256: {excel_hash}")

    # Parse Excel
    excel_data = parse_excel_sheets(excel_path)

    # Classify all parts
    print("\n[INFO] Classifying 1038 parts...")
    classifications = []
    category_counts = defaultdict(int)
    invalid_customer_counts = defaultdict(int)
    canonical_destination_counts = defaultdict(int)

    for part_evidence in raw_evidence['evidence']:
        result = classify_part(part_evidence, excel_data, customer_name_map, source_sheet_hints)
        classifications.append(result)

        # Update counters
        category_counts[result['category']] += 1
        invalid_customer_counts[result['invalid_customer_id']] += 1

        if result['canonical_customer_id']:
            canonical_destination_counts[result['canonical_customer_id']] += 1

    # Validate count
    assert len(classifications) == 1038, f"Expected 1038 classifications, got {len(classifications)}"

    # Collect reasons for ambiguous, new_customer_required, and invalid_template_part
    ambiguous_reasons = defaultdict(list)
    new_customer_reasons = defaultdict(list)
    template_part_ids = []

    for result in classifications:
        if result['category'] == 'ambiguous':
            ambiguous_reasons[result['reason']].append(result['part_id'])
        elif result['category'] == 'new_customer_required':
            customer_list = ', '.join(result['evidence'].get('unmapped_customers', []))
            new_customer_reasons[customer_list].append(result['part_id'])
        elif result['category'] == 'invalid_template_part':
            template_part_ids.append(result['part_id'])

    # Prepare output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = legacy_ref_dir / f'classification_{timestamp}'

    output_json = output_base.with_suffix('.json')
    output_md = output_base.with_suffix('.md')

    # JSON report
    report = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'script': 'classify_legacy_customer_refs.py',
            'database_unchanged': True,
            'input_files': {
                'audit': str(audit_path.name),
                'raw_evidence': str(evidence_path.name),
                'excel': str(excel_path.name),
                'excel_sha256': excel_hash
            }
        },
        'validation': {
            'expected_parts': 1038,
            'classified_parts': len(classifications),
            'assertion_passed': len(classifications) == 1038
        },
        'summary': {
            'category_totals': dict(category_counts),
            'invalid_customer_totals': dict(invalid_customer_counts),
            'canonical_destination_totals': dict(canonical_destination_counts)
        },
        'ambiguous_reasons': {
            reason: {'count': len(part_ids), 'example_part_ids': part_ids[:5]}
            for reason, part_ids in ambiguous_reasons.items()
        },
        'new_customer_reasons': {
            customers: {'count': len(part_ids), 'example_part_ids': part_ids[:5]}
            for customers, part_ids in new_customer_reasons.items()
        },
        'invalid_template_parts': {
            'count': len(template_part_ids),
            'part_ids': template_part_ids
        },
        'classifications': classifications
    }

    # Write JSON with safe serialization
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=safe_json_serialize)

    print(f"\n[SUCCESS] JSON report: {output_json.name}")

    # Markdown report
    md_lines = [
        f"# Legacy Customer Reference Classification Report",
        f"",
        f"**Timestamp:** {datetime.now().isoformat()}",
        f"**Database Unchanged:** True (offline analysis only)",
        f"",
        f"## Input Files",
        f"",
        f"- Audit: `{audit_path.name}`",
        f"- Raw Evidence: `{evidence_path.name}`",
        f"- Excel: `{excel_path.name}`",
        f"- Excel SHA256: `{excel_hash}`",
        f"",
        f"## Validation",
        f"",
        f"- Expected parts: 1038",
        f"- Classified parts: {len(classifications)}",
        f"- Assertion passed: ✓" if len(classifications) == 1038 else "✗",
        f"",
        f"## Category Totals",
        f"",
    ]

    for category, count in sorted(category_counts.items()):
        md_lines.append(f"- **{category}**: {count}")

    md_lines.extend([
        f"",
        f"## Invalid Customer Totals",
        f"",
    ])

    for customer_id, count in sorted(invalid_customer_counts.items()):
        md_lines.append(f"- Customer {customer_id}: {count} parts")

    md_lines.extend([
        f"",
        f"## Canonical Destination Totals",
        f"",
    ])

    for customer_id, count in sorted(canonical_destination_counts.items()):
        md_lines.append(f"- Customer {customer_id}: {count} parts")

    if ambiguous_reasons:
        md_lines.extend([
            f"",
            f"## Ambiguous Reasons",
            f"",
        ])
        for reason, part_ids in sorted(ambiguous_reasons.items()):
            md_lines.append(f"- **{reason}**: {len(part_ids)} parts")
            md_lines.append(f"  - Examples: {', '.join(map(str, part_ids[:5]))}")

    if new_customer_reasons:
        md_lines.extend([
            f"",
            f"## New Customer Required",
            f"",
        ])
        for customers, part_ids in sorted(new_customer_reasons.items()):
            md_lines.append(f"- **{customers}**: {len(part_ids)} parts")
            md_lines.append(f"  - Examples: {', '.join(map(str, part_ids[:5]))}")

    if template_part_ids:
        md_lines.extend([
            f"",
            f"## Invalid Template Parts (Delete Candidates)",
            f"",
            f"- **Count**: {len(template_part_ids)} parts",
            f"  - Part IDs: {', '.join(map(str, template_part_ids[:20]))}{'...' if len(template_part_ids) > 20 else ''}",
        ])

    md_lines.extend([
        f"",
        f"## Classification Details",
        f"",
        f"See `{output_json.name}` for complete classification data with evidence.",
        f"",
    ])

    with open(output_md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))

    print(f"[SUCCESS] Markdown report: {output_md.name}")

    # Console summary
    print("\n" + "="*70)
    print("CLASSIFICATION SUMMARY")
    print("="*70)
    print(f"Total parts classified: {len(classifications)}")
    print(f"\nCategory breakdown:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count}")
    print("="*70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
