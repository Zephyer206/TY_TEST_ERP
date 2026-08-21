#!/usr/bin/env python3
"""
Left-Right Parts Shared Material/Spec Correction Script

Header-aware implementation that re-reads Excel with merged cells support.
Corrects left-right parts that share material and specifications due to merged cells in Excel.
Operates on staging data (excel_import_rows) and formal tables (parts, tooling_parts, tooling).

SAFETY:
- Defaults to dry-run mode
- Creates backups before any updates
- Only fills NULL/empty values
- Never overwrites existing non-null values with different values
- Reports conflicts for manual review
"""

import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
import argparse
from decimal import Decimal, InvalidOperation

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import psycopg2
import psycopg2.extras
from urllib.parse import urlparse
import xlrd

# Import header detection from authoritative importer
try:
    from scripts.import_excel_authoritative import (
        detect_headers,
        parse_combined_spec,
        parse_cavity_count,
    )
except ImportError:
    from import_excel_authoritative import detect_headers, parse_combined_spec, parse_cavity_count


def safe_numeric_compare(val1, val2, tolerance=None):
    """
    Safely compare two numeric values that may be float or Decimal.
    Converts both to Decimal for precise comparison.

    Args:
        val1: First value (float, Decimal, int, or None)
        val2: Second value (float, Decimal, int, or None)
        tolerance: Optional Decimal tolerance for equality check (default: Decimal('0.001'))

    Returns:
        tuple: (are_equal: bool, diff: Decimal or None)
    """
    if val1 is None or val2 is None:
        return (val1 == val2, None)

    if tolerance is None:
        tolerance = Decimal('0.001')

    try:
        d1 = Decimal(str(val1))
        d2 = Decimal(str(val2))
        diff = abs(d1 - d2)
        are_equal = diff < tolerance
        return (are_equal, diff)
    except (ValueError, InvalidOperation):
        # Fallback to direct comparison if conversion fails
        return (val1 == val2, None)


def json_serializer(obj):
    """Custom JSON serializer for Decimal and Path objects."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def get_db_config():
    """Get database config from settings."""
    try:
        from app.core.config import settings
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured in settings")

        db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        parsed = urlparse(db_url)

        config = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'stamping_system',
            'user': parsed.username or 'postgres',
            'password': parsed.password
        }
        return config
    except Exception as e:
        print(f"[ERROR] Could not load database configuration: {e}")
        raise


def find_excel_file() -> Optional[Path]:
    """Find the Excel file in excel/ directory."""
    excel_dir = Path(__file__).parent.parent.parent / 'excel'
    xls_files = list(excel_dir.glob('*.xls'))

    if not xls_files:
        print(f"[ERROR] No .xls file found in {excel_dir}")
        return None

    if len(xls_files) > 1:
        print(f"[WARNING] Multiple .xls files found, using first: {xls_files[0].name}")

    return xls_files[0]


def build_merged_cell_map(sheet) -> Dict[Tuple[int, int], Tuple[int, int]]:
    """
    Build a mapping from any cell in a merged range to its top-left cell.
    Returns: {(row, col): (top_row, top_col)}
    """
    merged_map = {}

    for (rlo, rhi, clo, chi) in sheet.merged_cells:
        # rlo:rhi is the row range, clo:chi is the column range
        # Map all cells in the range to the top-left cell
        for row in range(rlo, rhi):
            for col in range(clo, chi):
                merged_map[(row, col)] = (rlo, clo)

    return merged_map


def get_cell_value(sheet, row_idx: int, col_idx: int, merged_map: Dict[Tuple[int, int], Tuple[int, int]]) -> Any:
    """
    Get cell value, following merged cell references.
    If cell is part of a merged range, return the value from the top-left cell.
    """
    if (row_idx, col_idx) in merged_map:
        top_row, top_col = merged_map[(row_idx, col_idx)]
        return sheet.cell_value(top_row, top_col)

    return sheet.cell_value(row_idx, col_idx)


def extract_excel_row_data(sheet, header_row_idx: int, column_map: Dict[str, int],
                           merged_map: Dict[Tuple[int, int], Tuple[int, int]],
                           row_number: int) -> Optional[Dict[str, Any]]:
    """
    Extract data from a specific row in Excel, respecting merged cells.
    Uses pre-computed header and merged cell maps for performance.

    Args:
        sheet: xlrd sheet object
        header_row_idx: Header row index
        column_map: Pre-computed column mapping
        merged_map: Pre-computed merged cell mapping
        row_number: 1-based row number (as stored in staging)

    Returns:
        Dict with parsed material, thickness, width, pitch, remark, cavity_count
    """
    try:
        # Convert 1-based row number to 0-based index
        row_idx = row_number - 1

        if row_idx < 0 or row_idx >= sheet.nrows:
            print(f"[WARNING] Row {row_number} out of range in sheet {sheet.name}")
            return None

        # Extract values using merged cell awareness
        def get_mapped_cell(field: str) -> Any:
            col_idx = column_map.get(field)
            if col_idx is not None:
                val = get_cell_value(sheet, row_idx, col_idx, merged_map)
                return str(val).strip() if val else None
            return None

        material = get_mapped_cell('material')
        spec_str = get_mapped_cell('spec')
        remark = get_mapped_cell('remark')
        cavity_raw = get_mapped_cell('cavity_count')

        # Parse combined spec for T/W/P
        thickness, width, pitch = None, None, None
        if spec_str:
            thickness, width, pitch = parse_combined_spec(spec_str)

        # Parse individual T/W/P columns if available and spec didn't provide them
        if thickness is None:
            t_col = get_mapped_cell('thickness')
            if t_col:
                try:
                    thickness = float(t_col)
                except:
                    pass

        if width is None:
            w_col = get_mapped_cell('width')
            if w_col:
                try:
                    width = float(w_col)
                except:
                    pass

        if pitch is None:
            p_col = get_mapped_cell('pitch')
            if p_col:
                try:
                    pitch = float(p_col)
                except:
                    pass

        # Only explicit 1出N/一出N text is cavity evidence.  Wording such as
        # 左右各一套 describes separate tooling and must not become 1出2.
        cavity_count = parse_cavity_count(
            f"{spec_str or ''} {cavity_raw or ''}",
            remark or '',
        )

        return {
            'material': material,
            'thickness': thickness,
            'width': width,
            'pitch': pitch,
            'remark': remark,
            'cavity_count': cavity_count,
            'spec_str': spec_str,
        }

    except Exception as e:
        print(f"[ERROR] Failed to extract Excel row data: {e}")
        return None


def extract_base_tooling_number(tooling_number: str) -> Optional[str]:
    """
    Extract base tooling number by removing -1/-2 suffix.
    Examples:
        TYAA-Q0093-1 -> TYAA-Q0093
        TYAA-Q0093-2 -> TYAA-Q0093
        TYAA-Q0093 -> TYAA-Q0093
    """
    if not tooling_number:
        return None

    # Remove trailing -1 or -2
    if tooling_number.endswith('-1') or tooling_number.endswith('-2'):
        return tooling_number[:-2]

    return tooling_number


def detect_position_from_name(internal_name: str) -> Optional[str]:
    """
    Detect left/right position from internal name.
    Returns: 'left', 'right', or None
    """
    if not internal_name:
        return None

    name_lower = internal_name.lower()

    # Check for explicit left/right markers
    if '左' in internal_name or 'left' in name_lower or '-l' in name_lower:
        return 'left'
    if '右' in internal_name or 'right' in name_lower or '-r' in name_lower:
        return 'right'

    # Check for -1/-2 suffix (common convention: -1=left, -2=right)
    if internal_name.endswith('-1'):
        return 'left'
    if internal_name.endswith('-2'):
        return 'right'

    return None


def find_candidate_groups(cur, excel_file: Path) -> List[Dict[str, Any]]:
    """
    Find candidate left-right part groups by re-reading Excel with merged cell awareness.

    Criteria:
    - Same source_sheet
    - Same base tooling_number (after removing -1/-2)
    - Both have resolved_part_id
    - One is left, one is right (by name or suffix)
    - Rows are adjacent or within merged cell range
    """
    print("\n[INFO] Finding candidate left-right groups from Excel...")

    # Get all staging rows with resolved parts
    cur.execute("""
        SELECT
            id,
            source_sheet,
            source_row,
            parsed_tooling_number,
            parsed_internal_name,
            parsed_material,
            parsed_thickness,
            parsed_width,
            parsed_pitch,
            parsed_position,
            parsed_cavity_count,
            resolved_part_id,
            validation_status
        FROM excel_import_rows
        WHERE resolved_part_id IS NOT NULL
            AND parsed_tooling_number IS NOT NULL
            AND validation_status IN ('VALID', 'IMPORTED')
        ORDER BY source_sheet, source_row
    """)

    rows = cur.fetchall()
    print(f"[INFO] Found {len(rows)} staging rows with resolved parts")

    # Open workbook once and cache sheet contexts
    print(f"[INFO] Opening Excel workbook: {excel_file}")
    workbook = xlrd.open_workbook(str(excel_file), formatting_info=True)

    # Cache sheet contexts (header map and merged map per sheet)
    sheet_contexts = {}

    def get_sheet_context(sheet_name: str) -> Optional[Dict[str, Any]]:
        """Get or create cached sheet context."""
        if sheet_name not in sheet_contexts:
            try:
                sheet = workbook.sheet_by_name(sheet_name)
                header_row_idx, column_map = detect_headers(sheet)

                if header_row_idx is None:
                    print(f"[WARNING] Could not detect headers in sheet {sheet_name}")
                    sheet_contexts[sheet_name] = None
                    return None

                merged_map = build_merged_cell_map(sheet)

                sheet_contexts[sheet_name] = {
                    'sheet': sheet,
                    'header_row_idx': header_row_idx,
                    'column_map': column_map,
                    'merged_map': merged_map,
                }
            except Exception as e:
                print(f"[WARNING] Failed to load sheet {sheet_name}: {e}")
                sheet_contexts[sheet_name] = None
                return None

        return sheet_contexts[sheet_name]

    # Group by sheet and base tooling number
    groups_dict = {}

    for row in rows:
        (row_id, source_sheet, source_row, tooling_number, internal_name,
         material, thickness, width, pitch, position, cavity_count,
         resolved_part_id, validation_status) = row

        base_tooling = extract_base_tooling_number(tooling_number)
        if not base_tooling:
            continue

        # Detect position from name or position field
        detected_position = position or detect_position_from_name(internal_name)

        if not detected_position or detected_position not in ['left', 'right']:
            continue

        # Extract Excel data with merged cell awareness using cached context
        excel_data = None
        sheet_ctx = get_sheet_context(source_sheet)
        if sheet_ctx:
            excel_data = extract_excel_row_data(
                sheet_ctx['sheet'],
                sheet_ctx['header_row_idx'],
                sheet_ctx['column_map'],
                sheet_ctx['merged_map'],
                source_row
            )

        key = (source_sheet, base_tooling)
        if key not in groups_dict:
            groups_dict[key] = []

        groups_dict[key].append({
            'row_id': row_id,
            'source_row': source_row,
            'tooling_number': tooling_number,
            'internal_name': internal_name,
            'staging_material': material,
            'staging_thickness': thickness,
            'staging_width': width,
            'staging_pitch': pitch,
            'staging_position': position,  # Store current staging position
            'position': detected_position,  # Detected position from name/field
            'staging_cavity_count': cavity_count,
            'part_id': resolved_part_id,
            'excel_data': excel_data,  # Fresh data from Excel with merged cells
        })

    # Filter to valid left-right pairs
    candidate_groups = []

    for (sheet, base_tooling), items in groups_dict.items():
        if len(items) != 2:
            continue  # Must be exactly 2 parts

        # Check if one is left and one is right
        positions = {item['position'] for item in items}
        if positions != {'left', 'right'}:
            continue

        # Check if rows are adjacent or close (within 5 rows)
        rows_nums = [item['source_row'] for item in items]
        if max(rows_nums) - min(rows_nums) > 5:
            continue

        # Sort by position (left first)
        items.sort(key=lambda x: x['position'])

        candidate_groups.append({
            'sheet': sheet,
            'base_tooling': base_tooling,
            'left': items[0],
            'right': items[1],
        })

    print(f"[INFO] Found {len(candidate_groups)} candidate left-right groups")
    return candidate_groups


def merge_duplicate_targets(groups: List[Dict[str, Any]]) -> Dict[Tuple[int, int], List[Dict[str, Any]]]:
    """
    Merge duplicate target groups by (left_part_id, right_part_id) key.

    When the same part pair appears in multiple source groups (e.g., same parts in different sheets),
    groups them together for unified processing.

    Args:
        groups: List of candidate groups from find_candidate_groups

    Returns:
        Dict mapping (left_part_id, right_part_id) -> list of source groups with that target
    """
    target_map = {}

    for group in groups:
        left_id = group['left']['part_id']
        right_id = group['right']['part_id']
        # Normalize key: always (smaller_id, larger_id)
        key = (min(left_id, right_id), max(left_id, right_id))

        if key not in target_map:
            target_map[key] = []

        target_map[key].append(group)

    return target_map


def consolidate_duplicate_targets(source_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Consolidate multiple source groups for the same target (left_part_id, right_part_id).

    This function analyzes all sources using analyze_group, collects candidates for each shared field,
    and determines safe merged values or conflicts.

    For each shared field (material/thickness/width/pitch/cavity):
    - 0 non-null candidates -> no value
    - 1 unique candidate -> adopt it
    - Multiple different candidates -> conflict

    For cavity_count: only explicit sources (from Excel) count as candidates.
    For part_id->position mapping: must be consistent across sources.

    Returns:
        {
            'consistent': bool,
            'conflicts': List[str],
            'merged_target': Dict or None,  # Contains sources list, canonical left/right, merged analysis
        }
    """
    if len(source_groups) == 1:
        # Single source: check for analysis conflicts
        analysis = analyze_group(source_groups[0])
        if analysis['conflicts']:
            # Even a single source can have conflicts (e.g., left vs right material differ)
            return {
                'consistent': False,
                'conflicts': analysis['conflicts'],
                'merged_target': None,
            }

        return {
            'consistent': True,
            'conflicts': [],
            'merged_target': {
                'sources': source_groups,
                'canonical_left': source_groups[0]['left'],
                'canonical_right': source_groups[0]['right'],
                'sheet': source_groups[0].get('sheet', 'unknown'),
                'base_tooling': source_groups[0].get('base_tooling', 'unknown'),
                'merged_analysis': analysis,
            }
        }

    # Multiple sources: analyze each and consolidate
    analyses = [analyze_group(group) for group in source_groups]
    conflicts = []

    # First, collect conflicts from individual analyses
    for idx, analysis in enumerate(analyses):
        if analysis['conflicts']:
            for conflict in analysis['conflicts']:
                source_group = source_groups[idx]
                conflicts.append(
                    f"Source {idx+1} (sheet={source_group.get('sheet', 'unknown')}, "
                    f"base_tooling={source_group.get('base_tooling', 'unknown')}, "
                    f"left_row={source_group['left'].get('source_row', '?')}, "
                    f"right_row={source_group['right'].get('source_row', '?')}): {conflict}"
                )

    # Collect candidates for each shared field
    def collect_candidates(field_name: str, is_numeric: bool = False, explicit_only: bool = False):
        """Collect non-null candidates from all analyses."""
        candidates = []
        for idx, analysis in enumerate(analyses):
            value = analysis.get(field_name)
            if value is not None:
                if explicit_only and not analysis.get('has_explicit_cavity_source', False):
                    # For cavity_count, only count if explicit source
                    continue
                candidates.append((idx, value))
        return candidates

    # Material candidates
    material_candidates = collect_candidates('shared_material')
    merged_material = None
    can_fill_material = False

    if len(material_candidates) == 0:
        pass  # No material
    elif len(material_candidates) == 1:
        merged_material = material_candidates[0][1]
        can_fill_material = True
    else:
        # Check if all are the same
        unique_vals = set(val for _, val in material_candidates)
        if len(unique_vals) == 1:
            merged_material = material_candidates[0][1]
            can_fill_material = True
        else:
            conflicts.append(f"Material conflict across sources: {', '.join(str(v) for _, v in material_candidates)}")

    # Thickness candidates
    thickness_candidates = collect_candidates('shared_thickness', is_numeric=True)
    merged_thickness = None
    can_fill_thickness = False

    if len(thickness_candidates) == 0:
        pass
    elif len(thickness_candidates) == 1:
        merged_thickness = thickness_candidates[0][1]
        can_fill_thickness = True
    else:
        # Check if all are numerically equal
        vals = [val for _, val in thickness_candidates]
        all_equal = all(safe_numeric_compare(vals[0], v)[0] for v in vals[1:])
        if all_equal:
            merged_thickness = vals[0]
            can_fill_thickness = True
        else:
            conflicts.append(f"Thickness conflict across sources: {', '.join(str(v) for _, v in thickness_candidates)}")

    # Width candidates
    width_candidates = collect_candidates('shared_width', is_numeric=True)
    merged_width = None
    can_fill_width = False

    if len(width_candidates) == 0:
        pass
    elif len(width_candidates) == 1:
        merged_width = width_candidates[0][1]
        can_fill_width = True
    else:
        vals = [val for _, val in width_candidates]
        all_equal = all(safe_numeric_compare(vals[0], v)[0] for v in vals[1:])
        if all_equal:
            merged_width = vals[0]
            can_fill_width = True
        else:
            conflicts.append(f"Width conflict across sources: {', '.join(str(v) for _, v in width_candidates)}")

    # Pitch candidates
    pitch_candidates = collect_candidates('shared_pitch', is_numeric=True)
    merged_pitch = None
    can_fill_pitch = False

    if len(pitch_candidates) == 0:
        pass
    elif len(pitch_candidates) == 1:
        merged_pitch = pitch_candidates[0][1]
        can_fill_pitch = True
    else:
        vals = [val for _, val in pitch_candidates]
        all_equal = all(safe_numeric_compare(vals[0], v)[0] for v in vals[1:])
        if all_equal:
            merged_pitch = vals[0]
            can_fill_pitch = True
        else:
            conflicts.append(f"Pitch conflict across sources: {', '.join(str(v) for _, v in pitch_candidates)}")

    # Cavity candidates - explicit_only=True
    cavity_candidates = collect_candidates('shared_cavity', explicit_only=True)
    merged_cavity = None
    can_fill_cavity = False
    has_explicit_cavity_source = len(cavity_candidates) > 0

    if len(cavity_candidates) == 0:
        pass
    elif len(cavity_candidates) == 1:
        merged_cavity = cavity_candidates[0][1]
        can_fill_cavity = True
    else:
        unique_vals = set(val for _, val in cavity_candidates)
        if len(unique_vals) == 1:
            merged_cavity = cavity_candidates[0][1]
            can_fill_cavity = True
        else:
            conflicts.append(f"Cavity count conflict across sources: {', '.join(str(v) for _, v in cavity_candidates)}")

    # Check part_id -> position mapping consistency (if part_id and position fields exist)
    if 'part_id' in source_groups[0]['left'] and 'position' in source_groups[0]['left']:
        left_id = source_groups[0]['left']['part_id']
        right_id = source_groups[0]['right']['part_id']

        for idx, group in enumerate(source_groups[1:], start=1):
            if group['left'].get('part_id') != left_id or group['right'].get('part_id') != right_id:
                # Check if reversed
                if group['left'].get('part_id') == right_id and group['right'].get('part_id') == left_id:
                    conflicts.append(f"Source {idx+1}: part_id->position mapping reversed (left={right_id}, right={left_id})")
                else:
                    conflicts.append(f"Source {idx+1}: part_id mismatch")

            # Check position consistency
            if group['left'].get('position') != source_groups[0]['left'].get('position'):
                conflicts.append(f"Source {idx+1}: left position differs ({source_groups[0]['left'].get('position')} vs {group['left'].get('position')})")
            if group['right'].get('position') != source_groups[0]['right'].get('position'):
                conflicts.append(f"Source {idx+1}: right position differs ({source_groups[0]['right'].get('position')} vs {group['right'].get('position')})")

    if conflicts:
        return {
            'consistent': False,
            'conflicts': conflicts,
            'merged_target': None,
        }

    # Build merged analysis
    merged_analysis = {
        'can_fill_material': can_fill_material,
        'shared_material': merged_material,
        'can_fill_thickness': can_fill_thickness,
        'shared_thickness': merged_thickness,
        'can_fill_width': can_fill_width,
        'shared_width': merged_width,
        'can_fill_pitch': can_fill_pitch,
        'shared_pitch': merged_pitch,
        'can_fill_cavity': can_fill_cavity,
        'shared_cavity': merged_cavity,
        'has_explicit_cavity_source': has_explicit_cavity_source,
        'conflicts': [],
    }

    return {
        'consistent': True,
        'conflicts': [],
        'merged_target': {
            'sources': source_groups,
            'canonical_left': source_groups[0]['left'],
            'canonical_right': source_groups[0]['right'],
            'sheet': source_groups[0].get('sheet', 'unknown'),
            'base_tooling': source_groups[0].get('base_tooling', 'unknown'),
            'merged_analysis': merged_analysis,
        }
    }


def analyze_group(group: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a left-right group using Excel data to determine what can be safely filled.
    Uses both staging data and fresh Excel data with merged cell awareness.

    Returns:
        {
            'can_fill_material': bool,
            'shared_material': str or None,
            'can_fill_thickness': bool,
            'shared_thickness': float or None,
            'can_fill_width': bool,
            'shared_width': float or None,
            'can_fill_pitch': bool,
            'shared_pitch': float or None,
            'can_fill_cavity': bool,
            'shared_cavity': int or None,
            'has_explicit_cavity_source': bool,
            'conflicts': List[str],
        }
    """
    left = group['left']
    right = group['right']
    conflicts = []

    # Get Excel data (with merged cells)
    left_excel = left.get('excel_data') or {}
    right_excel = right.get('excel_data') or {}

    # Material analysis - prefer Excel data
    left_mat = left_excel.get('material') or left['staging_material']
    right_mat = right_excel.get('material') or right['staging_material']

    can_fill_material = False
    shared_material = None

    if left_mat and right_mat:
        if left_mat == right_mat:
            can_fill_material = True
            shared_material = left_mat
        else:
            conflicts.append(f"Material conflict: left='{left_mat}' vs right='{right_mat}'")
    elif left_mat and not right_mat:
        can_fill_material = True
        shared_material = left_mat
    elif right_mat and not left_mat:
        can_fill_material = True
        shared_material = right_mat

    # Thickness analysis - prefer Excel data
    left_t = left_excel.get('thickness') if left_excel.get('thickness') is not None else left['staging_thickness']
    right_t = right_excel.get('thickness') if right_excel.get('thickness') is not None else right['staging_thickness']

    can_fill_thickness = False
    shared_thickness = None

    if left_t is not None and right_t is not None:
        are_equal, diff = safe_numeric_compare(left_t, right_t)
        if are_equal:
            can_fill_thickness = True
            shared_thickness = left_t
        else:
            conflicts.append(f"Thickness conflict: left={left_t} vs right={right_t}")
    elif left_t is not None and right_t is None:
        can_fill_thickness = True
        shared_thickness = left_t
    elif right_t is not None and left_t is None:
        can_fill_thickness = True
        shared_thickness = right_t

    # Width analysis
    left_w = left_excel.get('width') if left_excel.get('width') is not None else left['staging_width']
    right_w = right_excel.get('width') if right_excel.get('width') is not None else right['staging_width']

    can_fill_width = False
    shared_width = None

    if left_w is not None and right_w is not None:
        are_equal, diff = safe_numeric_compare(left_w, right_w)
        if are_equal:
            can_fill_width = True
            shared_width = left_w
        else:
            conflicts.append(f"Width conflict: left={left_w} vs right={right_w}")
    elif left_w is not None and right_w is None:
        can_fill_width = True
        shared_width = left_w
    elif right_w is not None and left_w is None:
        can_fill_width = True
        shared_width = right_w

    # Pitch analysis
    left_p = left_excel.get('pitch') if left_excel.get('pitch') is not None else left['staging_pitch']
    right_p = right_excel.get('pitch') if right_excel.get('pitch') is not None else right['staging_pitch']

    can_fill_pitch = False
    shared_pitch = None

    if left_p is not None and right_p is not None:
        are_equal, diff = safe_numeric_compare(left_p, right_p)
        if are_equal:
            can_fill_pitch = True
            shared_pitch = left_p
        else:
            conflicts.append(f"Pitch conflict: left={left_p} vs right={right_p}")
    elif left_p is not None and right_p is None:
        can_fill_pitch = True
        shared_pitch = left_p
    elif right_p is not None and left_p is None:
        can_fill_pitch = True
        shared_pitch = right_p

    # Cavity count analysis - ONLY if explicit source found
    left_cav = left_excel.get('cavity_count')
    right_cav = right_excel.get('cavity_count')

    can_fill_cavity = False
    shared_cavity = None
    has_explicit_cavity_source = False

    if left_cav is not None or right_cav is not None:
        has_explicit_cavity_source = True
        if left_cav is not None and right_cav is not None:
            if left_cav == right_cav:
                can_fill_cavity = True
                shared_cavity = left_cav
            else:
                conflicts.append(f"Cavity count conflict: left={left_cav} vs right={right_cav}")
        elif left_cav is not None:
            can_fill_cavity = True
            shared_cavity = left_cav
        elif right_cav is not None:
            can_fill_cavity = True
            shared_cavity = right_cav

    return {
        'can_fill_material': can_fill_material,
        'shared_material': shared_material,
        'can_fill_thickness': can_fill_thickness,
        'shared_thickness': shared_thickness,
        'can_fill_width': can_fill_width,
        'shared_width': shared_width,
        'can_fill_pitch': can_fill_pitch,
        'shared_pitch': shared_pitch,
        'can_fill_cavity': can_fill_cavity,
        'shared_cavity': shared_cavity,
        'has_explicit_cavity_source': has_explicit_cavity_source,
        'conflicts': conflicts,
    }


def add_or_merge_action(plan: Dict[str, Any], table_key: str, record_id: int, field: str, value: Any, source_info: str) -> None:
    """
    Add or merge an action into the plan. Handles conflict detection:
    - Same record_id + field with same value -> deduplicate (no-op)
    - Same record_id + field with different value -> record conflict and block the record

    Args:
        plan: The action plan dict
        table_key: 'staging_updates', 'part_updates', 'tooling_part_updates', or 'tooling_updates'
        record_id: The record ID
        field: The field name
        value: The proposed value
        source_info: Description of the source (for conflict messages)
    """
    if record_id not in plan[table_key]:
        plan[table_key][record_id] = {}

    existing_value = plan[table_key][record_id].get(field)

    if existing_value is None:
        # First time seeing this field for this record
        plan[table_key][record_id][field] = value
    else:
        # Already have a value for this field
        if isinstance(value, (int, float)) and isinstance(existing_value, (int, float)):
            are_equal, _ = safe_numeric_compare(existing_value, value)
            if are_equal:
                # Same value, deduplicate
                return
        elif existing_value == value:
            # Same value, deduplicate
            return

        # Different values -> conflict
        plan['conflicts'].append({
            'type': 'action_conflict',
            'table': table_key,
            'record_id': record_id,
            'field': field,
            'existing_value': existing_value,
            'proposed_value': value,
            'source': source_info,
        })

        # Mark this record as blocked
        if '_blocked_records' not in plan:
            plan['_blocked_records'] = {}
        if table_key not in plan['_blocked_records']:
            plan['_blocked_records'][table_key] = set()
        plan['_blocked_records'][table_key].add(record_id)


def build_action_plan(merged_targets: List[Dict[str, Any]], cur) -> Dict[str, Any]:
    """
    Build a unique action plan from merged targets.

    This function takes merged targets (output of consolidate_duplicate_targets),
    iterates through all sources to generate staging row actions, and uses the
    merged analysis to generate formal table actions once per canonical left/right.

    Returns a deduplicated plan where each record appears only once:
    - staging_updates: {row_id: {field: value}}
    - part_updates: {part_id: {field: value}}
    - tooling_part_updates: {tp_id: {field: value}}
    - tooling_updates: {tooling_id: {field: value}}
    - conflicts: [{type, message, ...}]
    - warnings: [{table, record_id, field, db_value, proposed_value, reason}]
    - target_ids: {source_groups: set, unique_target_groups: set, ...}
    - summary: {source_groups: int, unique_target_groups: int, ...}

    Args:
        merged_targets: List of merged target dicts from consolidate_duplicate_targets
        cur: Database cursor

    Returns:
        Action plan dict
    """
    plan = {
        'staging_updates': {},  # row_id -> {field: value}
        'part_updates': {},     # part_id -> {field: value}
        'tooling_part_updates': {},  # tp_id -> {field: value}
        'tooling_updates': {},  # tooling_id -> {field: value}
        'conflicts': [],
        'warnings': [],
        'target_ids': {
            'source_groups': set(),
            'unique_target_groups': set(),
            'unique_staging_rows': set(),
            'unique_parts': set(),
            'unique_tooling_parts': set(),
            'unique_tooling': set(),
        },
    }

    for merged_target in merged_targets:
        sources = merged_target['sources']
        canonical_left = merged_target['canonical_left']
        canonical_right = merged_target['canonical_right']
        analysis = merged_target['merged_analysis']
        base_tooling = merged_target['base_tooling']

        # Track target IDs
        target_key = (canonical_left['part_id'], canonical_right['part_id'])
        plan['target_ids']['unique_target_groups'].add(target_key)
        plan['target_ids']['unique_parts'].add(canonical_left['part_id'])
        plan['target_ids']['unique_parts'].add(canonical_right['part_id'])

        for source_group in sources:
            source_key = (source_group['sheet'], source_group['base_tooling'],
                         source_group['left']['source_row'], source_group['right']['source_row'])
            plan['target_ids']['source_groups'].add(source_key)

        # Check for analysis conflicts
        if analysis.get('conflicts'):
            plan['conflicts'].append({
                'type': 'analysis_conflict',
                'sheet': merged_target['sheet'],
                'base_tooling': base_tooling,
                'left_part_id': canonical_left['part_id'],
                'right_part_id': canonical_right['part_id'],
                'conflicts': analysis['conflicts'],
            })
            continue

        # Plan staging updates - iterate through ALL sources
        for source_group in sources:
            for side in ['left', 'right']:
                item = source_group[side]
                row_id = item['row_id']
                source_info = f"sheet={source_group['sheet']}, tooling={base_tooling}, side={side}"

                # Track staging row ID
                plan['target_ids']['unique_staging_rows'].add(row_id)

                # Check staging conflicts with Excel data
                excel_data = item.get('excel_data') or {}

                # Material conflict check
                if analysis['can_fill_material'] and item['staging_material'] and item['staging_material'] != analysis['shared_material']:
                    plan['warnings'].append({
                        'table': 'excel_import_rows',
                        'record_id': row_id,
                        'field': 'parsed_material',
                        'db_value': item['staging_material'],
                        'proposed_value': analysis['shared_material'],
                        'reason': 'DB staging material differs from shared value - not overwriting',
                    })

                # Thickness conflict check
                if analysis['can_fill_thickness'] and item['staging_thickness'] is not None:
                    are_equal, _ = safe_numeric_compare(item['staging_thickness'], analysis['shared_thickness'])
                    if not are_equal:
                        plan['warnings'].append({
                            'table': 'excel_import_rows',
                            'record_id': row_id,
                            'field': 'parsed_thickness',
                            'db_value': float(item['staging_thickness']),
                            'proposed_value': float(analysis['shared_thickness']) if analysis['shared_thickness'] else None,
                            'reason': 'DB staging thickness differs from shared value - not overwriting',
                        })

                # Width conflict check
                if analysis['can_fill_width'] and item['staging_width'] is not None:
                    are_equal, _ = safe_numeric_compare(item['staging_width'], analysis['shared_width'])
                    if not are_equal:
                        plan['warnings'].append({
                            'table': 'excel_import_rows',
                            'record_id': row_id,
                            'field': 'parsed_width',
                            'db_value': float(item['staging_width']),
                            'proposed_value': float(analysis['shared_width']) if analysis['shared_width'] else None,
                            'reason': 'DB staging width differs from shared value - not overwriting',
                        })

                # Pitch conflict check
                if analysis['can_fill_pitch'] and item['staging_pitch'] is not None:
                    are_equal, _ = safe_numeric_compare(item['staging_pitch'], analysis['shared_pitch'])
                    if not are_equal:
                        plan['warnings'].append({
                            'table': 'excel_import_rows',
                            'record_id': row_id,
                            'field': 'parsed_pitch',
                            'db_value': float(item['staging_pitch']),
                            'proposed_value': float(analysis['shared_pitch']) if analysis['shared_pitch'] else None,
                            'reason': 'DB staging pitch differs from shared value - not overwriting',
                        })

                # Cavity conflict check
                if analysis['can_fill_cavity'] and item['staging_cavity_count'] and item['staging_cavity_count'] != analysis['shared_cavity']:
                    plan['warnings'].append({
                        'table': 'excel_import_rows',
                        'record_id': row_id,
                        'field': 'parsed_cavity_count',
                        'db_value': item['staging_cavity_count'],
                        'proposed_value': analysis['shared_cavity'],
                        'reason': 'DB staging cavity differs from shared value - not overwriting',
                    })

                updates = {}
                if analysis['can_fill_material'] and not item['staging_material']:
                    updates['parsed_material'] = analysis['shared_material']
                if analysis['can_fill_thickness'] and item['staging_thickness'] is None:
                    updates['parsed_thickness'] = analysis['shared_thickness']
                if analysis['can_fill_width'] and item['staging_width'] is None:
                    updates['parsed_width'] = analysis['shared_width']
                if analysis['can_fill_pitch'] and item['staging_pitch'] is None:
                    updates['parsed_pitch'] = analysis['shared_pitch']
                if not item['staging_cavity_count'] and analysis['can_fill_cavity']:
                    updates['parsed_cavity_count'] = analysis['shared_cavity']

                # Handle parsed_position
                staging_position = item.get('staging_position')
                if staging_position is None or staging_position == '':
                    updates['parsed_position'] = item['position']
                elif staging_position != item['position']:
                    plan['warnings'].append({
                        'table': 'excel_import_rows',
                        'record_id': row_id,
                        'field': 'parsed_position',
                        'db_value': staging_position,
                        'proposed_value': item['position'],
                        'reason': 'DB parsed_position differs from detected position - not overwriting',
                    })

                # Add actions with conflict detection
                for field, value in updates.items():
                    add_or_merge_action(plan, 'staging_updates', row_id, field, value, source_info)

        # Plan part updates - use canonical left/right only once
        for side, item in [('left', canonical_left), ('right', canonical_right)]:
            part_id = item['part_id']
            source_info = f"canonical {side}, tooling={base_tooling}"

            # Get current part values
            cur.execute("""
                SELECT material_name, thickness, width, pitch, part_position
                FROM parts WHERE id = %s
            """, (part_id,))
            part_row = cur.fetchone()
            if not part_row:
                continue

            db_material, db_thickness, db_width, db_pitch, db_position = part_row

            updates = {}

            # Material
            if analysis['can_fill_material']:
                if not db_material:
                    updates['material_name'] = analysis['shared_material']
                elif db_material != analysis['shared_material']:
                    plan['warnings'].append({
                        'table': 'parts',
                        'record_id': part_id,
                        'field': 'material_name',
                        'db_value': db_material,
                        'proposed_value': analysis['shared_material'],
                        'reason': 'DB value differs from shared value - not overwriting',
                    })

            # Thickness
            if analysis['can_fill_thickness']:
                if db_thickness is None:
                    updates['thickness'] = analysis['shared_thickness']
                else:
                    are_equal, _ = safe_numeric_compare(db_thickness, analysis['shared_thickness'])
                    if not are_equal:
                        plan['warnings'].append({
                            'table': 'parts',
                            'record_id': part_id,
                            'field': 'thickness',
                            'db_value': float(db_thickness) if db_thickness else None,
                            'proposed_value': float(analysis['shared_thickness']) if analysis['shared_thickness'] else None,
                            'reason': 'DB value differs from shared value - not overwriting',
                        })

            # Width
            if analysis['can_fill_width']:
                if db_width is None:
                    updates['width'] = analysis['shared_width']
                else:
                    are_equal, _ = safe_numeric_compare(db_width, analysis['shared_width'])
                    if not are_equal:
                        plan['warnings'].append({
                            'table': 'parts',
                            'record_id': part_id,
                            'field': 'width',
                            'db_value': float(db_width) if db_width else None,
                            'proposed_value': float(analysis['shared_width']) if analysis['shared_width'] else None,
                            'reason': 'DB value differs from shared value - not overwriting',
                        })

            # Pitch
            if analysis['can_fill_pitch']:
                if db_pitch is None:
                    updates['pitch'] = analysis['shared_pitch']
                else:
                    are_equal, _ = safe_numeric_compare(db_pitch, analysis['shared_pitch'])
                    if not are_equal:
                        plan['warnings'].append({
                            'table': 'parts',
                            'record_id': part_id,
                            'field': 'pitch',
                            'db_value': float(db_pitch) if db_pitch else None,
                            'proposed_value': float(analysis['shared_pitch']) if analysis['shared_pitch'] else None,
                            'reason': 'DB value differs from shared value - not overwriting',
                        })

            # Position - check for conflicts with existing value
            if db_position and db_position != item['position']:
                plan['warnings'].append({
                    'table': 'parts',
                    'record_id': part_id,
                    'field': 'part_position',
                    'db_value': db_position,
                    'proposed_value': item['position'],
                    'reason': 'DB part_position differs from detected position - not overwriting',
                })
            elif not db_position and item['position']:
                updates['part_position'] = item['position']

            # Add actions with conflict detection
            for field, value in updates.items():
                add_or_merge_action(plan, 'part_updates', part_id, field, value, source_info)

        # Plan tooling_parts updates
        for side, item in [('left', canonical_left), ('right', canonical_right)]:
            if not item['position']:
                continue

            cur.execute("""
                SELECT id, position FROM tooling_parts WHERE part_id = %s
            """, (item['part_id'],))

            tp_rows = cur.fetchall()
            for tp_id, tp_position in tp_rows:
                plan['target_ids']['unique_tooling_parts'].add(tp_id)

                if tp_position and tp_position != item['position']:
                    plan['warnings'].append({
                        'table': 'tooling_parts',
                        'record_id': tp_id,
                        'field': 'position',
                        'db_value': tp_position,
                        'proposed_value': item['position'],
                        'reason': 'DB tooling_parts position differs from detected position - not overwriting',
                    })
                elif not tp_position:
                    source_info = f"canonical {side}, part_id={item['part_id']}"
                    add_or_merge_action(plan, 'tooling_part_updates', tp_id, 'position', item['position'], source_info)

        # Plan tooling updates
        if analysis['can_fill_cavity'] and analysis['has_explicit_cavity_source']:
            for side, item in [('left', canonical_left), ('right', canonical_right)]:
                cur.execute("""
                    SELECT DISTINCT t.id, t.cavity_count
                    FROM tooling t
                    JOIN tooling_parts tp ON tp.tooling_id = t.id
                    WHERE tp.part_id = %s
                """, (item['part_id'],))

                tooling_rows = cur.fetchall()
                for t_id, t_cavity in tooling_rows:
                    plan['target_ids']['unique_tooling'].add(t_id)

                    if t_cavity is None or t_cavity == 0:
                        source_info = f"canonical {side}, part_id={item['part_id']}"
                        add_or_merge_action(plan, 'tooling_updates', t_id, 'cavity_count', analysis['shared_cavity'], source_info)
                    elif t_cavity != analysis['shared_cavity']:
                        plan['warnings'].append({
                            'table': 'tooling',
                            'record_id': t_id,
                            'field': 'cavity_count',
                            'db_value': t_cavity,
                            'proposed_value': analysis['shared_cavity'],
                            'reason': 'DB value differs from shared value - not overwriting',
                        })

    # Remove blocked records from update plans
    if '_blocked_records' in plan:
        for table_key, blocked_ids in plan['_blocked_records'].items():
            for record_id in blocked_ids:
                if record_id in plan[table_key]:
                    del plan[table_key][record_id]
        del plan['_blocked_records']

    # Deduplicate warnings
    seen_warnings = set()
    unique_warnings = []
    for warning in plan['warnings']:
        key = (warning['table'], warning['record_id'], warning['field'])
        if key not in seen_warnings:
            seen_warnings.add(key)
            unique_warnings.append(warning)
    plan['warnings'] = unique_warnings

    # Build summary
    plan['summary'] = {
        'source_groups': len(plan['target_ids']['source_groups']),
        'unique_target_groups': len(plan['target_ids']['unique_target_groups']),
        'unique_staging_rows': len(plan['target_ids']['unique_staging_rows']),
        'unique_parts': len(plan['target_ids']['unique_parts']),
        'unique_tooling_parts': len(plan['target_ids']['unique_tooling_parts']),
        'unique_tooling': len(plan['target_ids']['unique_tooling']),
    }

    return plan


def execute_action_plan(cur, plan: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    """
    Execute the action plan built by build_action_plan.

    In dry-run mode: only prints actions and returns planned_* counts.
    In apply mode: executes UPDATE statements and returns updated_* counts.

    For each table, updates are grouped by record_id, with multiple fields
    combined into a single UPDATE statement per record.

    Field names are validated against a whitelist. Values are parameterized.

    Args:
        cur: Database cursor
        plan: Action plan from build_action_plan
        dry_run: If True, only simulate; if False, execute UPDATEs

    Returns:
        Stats dict with planned_*/updated_* counts
    """
    # Field whitelists for each table
    FIELD_WHITELIST = {
        'staging_updates': {'parsed_material', 'parsed_thickness', 'parsed_width',
                           'parsed_pitch', 'parsed_cavity_count', 'parsed_position'},
        'part_updates': {'material_name', 'thickness', 'width', 'pitch', 'part_position'},
        'tooling_part_updates': {'position'},
        'tooling_updates': {'cavity_count'},
    }

    TABLE_NAMES = {
        'staging_updates': 'excel_import_rows',
        'part_updates': 'parts',
        'tooling_part_updates': 'tooling_parts',
        'tooling_updates': 'tooling',
    }

    stats = {
        'planned_staging_rows' if dry_run else 'updated_staging_rows': 0,
        'planned_parts' if dry_run else 'updated_parts': 0,
        'planned_tooling_parts' if dry_run else 'updated_tooling_parts': 0,
        'planned_tooling' if dry_run else 'updated_tooling': 0,
    }

    stat_keys = {
        'staging_updates': 'planned_staging_rows' if dry_run else 'updated_staging_rows',
        'part_updates': 'planned_parts' if dry_run else 'updated_parts',
        'tooling_part_updates': 'planned_tooling_parts' if dry_run else 'updated_tooling_parts',
        'tooling_updates': 'planned_tooling' if dry_run else 'updated_tooling',
    }

    if dry_run:
        print("\n[DRY-RUN] Would execute the following actions:")

    for table_key in ['staging_updates', 'part_updates', 'tooling_part_updates', 'tooling_updates']:
        updates = plan.get(table_key, {})
        if not updates:
            continue

        table_name = TABLE_NAMES[table_key]
        whitelist = FIELD_WHITELIST[table_key]

        for record_id, fields in updates.items():
            if not fields:
                continue

            # Validate all field names against whitelist
            for field_name in fields.keys():
                if field_name not in whitelist:
                    raise ValueError(f"Invalid field name '{field_name}' for table {table_name}")

            # Build UPDATE statement
            set_clauses = [f"{field} = %s" for field in fields.keys()]
            values = list(fields.values())

            if table_key == 'part_updates':
                # Parts table needs updated_at
                set_clauses.append("updated_at = NOW()")

            query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id = %s"
            values.append(record_id)

            if dry_run:
                print(f"\n[DRY-RUN] {table_name} record {record_id}:")
                for field, value in fields.items():
                    print(f"  {field} -> {value}")
                stats[stat_keys[table_key]] += 1
            else:
                cur.execute(query, values)
                stats[stat_keys[table_key]] += 1

    return stats


def check_duplicate_consistency(source_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    DEPRECATED: Backward compatibility wrapper for consolidate_duplicate_targets.
    Use consolidate_duplicate_targets instead.
    """
    result = consolidate_duplicate_targets(source_groups)
    return {
        'consistent': result['consistent'],
        'conflicts': result['conflicts'],
        'merged_group': result['merged_target'],
    }


def apply_corrections(cur, groups: List[Dict[str, Any]], dry_run: bool = True) -> Dict[str, Any]:
    """
    DEPRECATED: This function is kept for backward compatibility only.
    Use the new unified flow: merge_duplicate_targets -> consolidate_duplicate_targets ->
    build_action_plan -> execute_action_plan instead.

    This function no longer executes SQL directly. It delegates to the unified action plan flow.

    Returns:
        Stats dict with counts
    """
    raise RuntimeError(
        "apply_corrections() is deprecated. "
        "Use the unified flow: "
        "merge_duplicate_targets() -> consolidate_duplicate_targets() -> "
        "build_action_plan() -> execute_action_plan()"
    )


def backup_records(cur, part_ids: List[int], backup_dir: Path) -> Dict[str, Path]:
    """
    Backup records that will be updated.

    Returns:
        Dict with backup file paths
    """
    print(f"\n[INFO] Creating backups in {backup_dir}...")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_files = {}

    # Backup parts
    cur.execute("""
        SELECT * FROM parts WHERE id = ANY(%s)
    """, (part_ids,))
    parts_backup = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    parts_file = backup_dir / f'parts_backup_{timestamp}.json'
    with open(parts_file, 'w', encoding='utf-8') as f:
        json.dump(parts_backup, f, indent=2, ensure_ascii=False, default=json_serializer)
    backup_files['parts'] = parts_file
    print(f"  Backed up {len(parts_backup)} parts records")

    # Backup tooling_parts
    cur.execute("""
        SELECT * FROM tooling_parts WHERE part_id = ANY(%s)
    """, (part_ids,))
    tooling_parts_backup = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    tooling_parts_file = backup_dir / f'tooling_parts_backup_{timestamp}.json'
    with open(tooling_parts_file, 'w', encoding='utf-8') as f:
        json.dump(tooling_parts_backup, f, indent=2, ensure_ascii=False, default=json_serializer)
    backup_files['tooling_parts'] = tooling_parts_file
    print(f"  Backed up {len(tooling_parts_backup)} tooling_parts records")

    # Backup tooling
    cur.execute("""
        SELECT DISTINCT t.*
        FROM tooling t
        JOIN tooling_parts tp ON tp.tooling_id = t.id
        WHERE tp.part_id = ANY(%s)
    """, (part_ids,))
    tooling_backup = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    tooling_file = backup_dir / f'tooling_backup_{timestamp}.json'
    with open(tooling_file, 'w', encoding='utf-8') as f:
        json.dump(tooling_backup, f, indent=2, ensure_ascii=False, default=json_serializer)
    backup_files['tooling'] = tooling_file
    print(f"  Backed up {len(tooling_backup)} tooling records")

    # Backup staging rows
    cur.execute("""
        SELECT * FROM excel_import_rows WHERE resolved_part_id = ANY(%s)
    """, (part_ids,))
    staging_backup = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    staging_file = backup_dir / f'staging_backup_{timestamp}.json'
    with open(staging_file, 'w', encoding='utf-8') as f:
        json.dump(staging_backup, f, indent=2, ensure_ascii=False, default=json_serializer)
    backup_files['staging'] = staging_file
    print(f"  Backed up {len(staging_backup)} staging records")

    return backup_files


def generate_report(all_targets: List[Dict[str, Any]], plan: Dict[str, Any], stats: Dict[str, Any], backup_files: Dict[str, Path], report_dir: Path, dry_run: bool) -> Dict[str, Path]:
    """
    Generate JSON and Markdown reports for consolidated targets.

    Args:
        all_targets: List of target dicts with 'status', 'merged_target', and 'conflicts' keys
        plan: Action plan from build_action_plan
        stats: Statistics dict
        backup_files: Backup file paths
        report_dir: Report directory
        dry_run: Whether in dry-run mode

    Returns:
        Dict with 'json' and 'markdown' file paths
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # JSON report
    json_report = {
        'timestamp': timestamp,
        'mode': 'DRY_RUN' if dry_run else 'APPLY',
        'stats': stats,
        'summary': plan.get('summary', {}),
        'warnings': plan.get('warnings', []),
        'action_conflicts': [c for c in plan.get('conflicts', []) if c.get('type') == 'action_conflict'],
        'target_conflicts': [c for c in plan.get('conflicts', []) if c.get('type') == 'analysis_conflict'],
        'targets': [],
        'backups': {k: str(v) for k, v in backup_files.items()},
    }

    for target_info in all_targets:
        status = target_info['status']
        target_data = {
            'status': status,
        }

        if status == 'safe':
            merged = target_info['merged_target']
            target_data.update({
                'sheet': merged['sheet'],
                'base_tooling': merged['base_tooling'],
                'target_key': (merged['canonical_left']['part_id'], merged['canonical_right']['part_id']),
                'sources': [
                    {
                        'sheet': src['sheet'],
                        'base_tooling': src['base_tooling'],
                        'left_row': src['left']['source_row'],
                        'right_row': src['right']['source_row'],
                    }
                    for src in merged['sources']
                ],
                'canonical_left': {
                    'part_id': merged['canonical_left']['part_id'],
                    'internal_name': merged['canonical_left']['internal_name'],
                },
                'canonical_right': {
                    'part_id': merged['canonical_right']['part_id'],
                    'internal_name': merged['canonical_right']['internal_name'],
                },
                'merged_analysis': {
                    'shared_material': merged['merged_analysis']['shared_material'],
                    'shared_thickness': merged['merged_analysis']['shared_thickness'],
                    'shared_width': merged['merged_analysis']['shared_width'],
                    'shared_pitch': merged['merged_analysis']['shared_pitch'],
                    'shared_cavity': merged['merged_analysis']['shared_cavity'],
                    'has_explicit_cavity_source': merged['merged_analysis']['has_explicit_cavity_source'],
                },
            })
        elif status == 'duplicate_conflict':
            target_data.update({
                'reason': 'duplicate_conflict',
                'target_key': target_info.get('target_key'),
                'conflicts': target_info['conflicts'],
                'sources': target_info.get('sources', []),
            })

        json_report['targets'].append(target_data)

    json_file = report_dir / f'left_right_correction_{timestamp}.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False, default=json_serializer)
    print(f"\n[INFO] JSON report: {json_file}")

    # Markdown report
    staging_key = 'planned_staging_rows' if dry_run else 'updated_staging_rows'
    parts_key = 'planned_parts' if dry_run else 'updated_parts'
    tooling_parts_key = 'planned_tooling_parts' if dry_run else 'updated_tooling_parts'
    tooling_key = 'planned_tooling' if dry_run else 'updated_tooling'

    md_lines = [
        f"# Left-Right Shared Spec Correction Report",
        f"",
        f"**Timestamp**: {timestamp}",
        f"**Mode**: {'DRY-RUN' if dry_run else 'APPLY'}",
        f"",
        f"## Summary",
        f"",
        f"- Source groups: {plan.get('summary', {}).get('source_groups', 0)}",
        f"- Unique target groups: {plan.get('summary', {}).get('unique_target_groups', 0)}",
        f"- Safe targets: {stats.get('safe_targets', 0)}",
        f"- Duplicate conflict targets: {stats.get('duplicate_conflict_targets', 0)}",
        f"- Unique staging rows: {plan.get('summary', {}).get('unique_staging_rows', 0)}",
        f"- Unique parts: {plan.get('summary', {}).get('unique_parts', 0)}",
        f"- Unique tooling_parts: {plan.get('summary', {}).get('unique_tooling_parts', 0)}",
        f"- Unique tooling: {plan.get('summary', {}).get('unique_tooling', 0)}",
    ]

    md_lines.extend([
        f"- {'Planned' if dry_run else 'Updated'} staging rows: {stats.get(staging_key, 0)}",
        f"- {'Planned' if dry_run else 'Updated'} parts: {stats.get(parts_key, 0)}",
        f"- {'Planned' if dry_run else 'Updated'} tooling_parts: {stats.get(tooling_parts_key, 0)}",
        f"- {'Planned' if dry_run else 'Updated'} tooling: {stats.get(tooling_key, 0)}",
    ])

    if plan.get('warnings'):
        md_lines.extend([
            f"- Warnings: {len(plan['warnings'])}",
        ])

    if plan.get('conflicts'):
        md_lines.extend([
            f"- Action conflicts: {len(plan['conflicts'])}",
        ])

    md_lines.extend([
        f"",
        f"## Backups",
        f"",
    ])

    for name, path in backup_files.items():
        md_lines.append(f"- {name}: `{path}`")

    if stats.get('duplicate_conflict_targets', 0) > 0:
        md_lines.extend([
            f"",
            f"## Duplicate Conflicts",
            f"",
            f"Targets with conflicting data across multiple source groups:",
            f"",
        ])
        for target_info in all_targets:
            if target_info['status'] == 'duplicate_conflict':
                target_key = target_info.get('target_key', 'unknown')
                md_lines.extend([
                    f"### Target {target_key}",
                    f"",
                ])

                # Show sources if available
                if target_info.get('sources'):
                    md_lines.append("**Sources:**")
                    for src in target_info['sources']:
                        md_lines.append(
                            f"- Sheet: {src.get('sheet')}, Base tooling: {src.get('base_tooling')}, "
                            f"Left: row_id={src.get('left_row_id')}, part_id={src.get('left_part_id')}, "
                            f"Right: row_id={src.get('right_row_id')}, part_id={src.get('right_part_id')}"
                        )
                    md_lines.append("")

                md_lines.append("**Conflicts:**")
                for conflict in target_info['conflicts']:
                    md_lines.append(f"- {conflict}")
                md_lines.append("")

    if plan.get('conflicts'):
        md_lines.extend([
            f"",
            f"## Action Conflicts",
            f"",
            f"Conflicts detected when building the action plan:",
            f"",
        ])
        for conflict in plan['conflicts']:
            if conflict['type'] == 'analysis_conflict':
                md_lines.extend([
                    f"### {conflict['base_tooling']} on {conflict['sheet']}",
                    f"",
                    f"- Left part: {conflict['left_part_id']}",
                    f"- Right part: {conflict['right_part_id']}",
                    f"",
                    f"Issues:",
                ])
                for issue in conflict['conflicts']:
                    md_lines.append(f"- {issue}")
                md_lines.append("")
            elif conflict['type'] == 'action_conflict':
                md_lines.extend([
                    f"- **{conflict['table']}** record {conflict['record_id']}, field `{conflict['field']}`:",
                    f"  - Existing value: `{conflict.get('existing_value', 'N/A')}`",
                    f"  - Proposed value: `{conflict.get('proposed_value', 'N/A')}`",
                    f"  - Source: {conflict.get('source', 'unknown')}",
                    f"",
                ])

    if plan.get('warnings'):
        md_lines.extend([
            f"",
            f"## Warnings",
            f"",
            f"DB values that differ from proposed values (not overwritten):",
            f"",
        ])
        for warning in plan['warnings']:
            md_lines.extend([
                f"- **{warning['table']}** record {warning['record_id']}, field `{warning['field']}`:",
                f"  - DB value: `{warning['db_value']}`",
                f"  - Proposed value: `{warning['proposed_value']}`",
                f"  - Reason: {warning['reason']}",
                f"",
            ])

    md_file = report_dir / f'left_right_correction_{timestamp}.md'
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    print(f"[INFO] Markdown report: {md_file}")

    return {
        'json': json_file,
        'markdown': md_file,
    }


def main():
    parser = argparse.ArgumentParser(description='Correct left-right shared specs')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--backup-dir', type=str, default='./backups/left_right_correction',
                       help='Backup directory')
    parser.add_argument('--report-dir', type=str, default='./reports/left_right_correction',
                       help='Report directory')
    args = parser.parse_args()

    dry_run = not args.apply
    backup_dir = Path(args.backup_dir)
    report_dir = Path(args.report_dir)

    print("="*70)
    print("Left-Right Parts Shared Material/Spec Correction")
    print("Unified Action Plan Executor (B1)")
    print("="*70)
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY CHANGES'}")
    print(f"Backup dir: {backup_dir}")
    print(f"Report dir: {report_dir}")

    # Find Excel file
    excel_file = find_excel_file()
    if not excel_file:
        return 1

    print(f"\n[INFO] Excel file: {excel_file}")

    # Get database config
    try:
        db_config = get_db_config()
    except Exception as e:
        print(f"[FATAL] {e}")
        return 1

    # Connect to database
    conn = psycopg2.connect(**db_config)
    conn.autocommit = False  # Use transactions
    cur = conn.cursor()

    try:
        # Step 1: Find candidate groups
        print("\n[STEP 1] Finding candidate groups...")
        groups = find_candidate_groups(cur, excel_file)

        if not groups:
            print("\n[INFO] No candidate groups found")
            return 0

        # Step 2: Merge duplicate targets
        print(f"\n[STEP 2] Merging duplicate targets from {len(groups)} groups...")
        target_map = merge_duplicate_targets(groups)
        print(f"[INFO] Found {len(target_map)} unique target pairs")

        # Step 3: Consolidate duplicate targets
        print("\n[STEP 3] Consolidating duplicate targets...")
        safe_targets = []
        duplicate_conflict_targets = []

        for target_key, source_groups in target_map.items():
            result = consolidate_duplicate_targets(source_groups)
            if result['consistent']:
                safe_targets.append(result['merged_target'])
            else:
                # Store complete information about conflicting target
                duplicate_conflict_targets.append({
                    'target_key': target_key,
                    'conflicts': result['conflicts'],
                    'source_count': len(source_groups),
                    'sources': [
                        {
                            'sheet': src['sheet'],
                            'base_tooling': src['base_tooling'],
                            'left_row_id': src['left']['row_id'],
                            'left_source_row': src['left']['source_row'],
                            'left_part_id': src['left']['part_id'],
                            'right_row_id': src['right']['row_id'],
                            'right_source_row': src['right']['source_row'],
                            'right_part_id': src['right']['part_id'],
                        }
                        for src in source_groups
                    ],
                })
                print(f"\n[DUPLICATE CONFLICT] Target {target_key}:")
                for conflict in result['conflicts']:
                    print(f"  {conflict}")

        print(f"[INFO] Safe targets: {len(safe_targets)}")
        print(f"[INFO] Duplicate conflict targets: {len(duplicate_conflict_targets)}")

        # Step 4: Build action plan
        print("\n[STEP 4] Building action plan from safe targets...")
        plan = build_action_plan(safe_targets, cur)

        print(f"[INFO] Plan summary:")
        print(f"  Source groups: {plan['summary']['source_groups']}")
        print(f"  Unique target groups: {plan['summary']['unique_target_groups']}")
        print(f"  Unique staging rows: {plan['summary']['unique_staging_rows']}")
        print(f"  Unique parts: {plan['summary']['unique_parts']}")
        print(f"  Unique tooling_parts: {plan['summary']['unique_tooling_parts']}")
        print(f"  Unique tooling: {plan['summary']['unique_tooling']}")
        print(f"  Planned staging updates: {len(plan['staging_updates'])}")
        print(f"  Planned part updates: {len(plan['part_updates'])}")
        print(f"  Planned tooling_part updates: {len(plan['tooling_part_updates'])}")
        print(f"  Planned tooling updates: {len(plan['tooling_updates'])}")
        print(f"  Warnings: {len(plan['warnings'])}")
        print(f"  Conflicts: {len(plan['conflicts'])}")

        # Step 5: Backup before applying
        backup_files = {}
        if not dry_run and safe_targets:
            print("\n[STEP 5] Creating backups...")
            all_part_ids = list(plan['target_ids']['unique_parts'])
            backup_files = backup_records(cur, all_part_ids, backup_dir)

        # Step 6: Execute action plan
        print(f"\n[STEP 6] {'Simulating' if dry_run else 'Executing'} action plan...")
        exec_stats = execute_action_plan(cur, plan, dry_run=dry_run)

        # Combine stats
        stats = {
            'safe_targets': len(safe_targets),
            'duplicate_conflict_targets': len(duplicate_conflict_targets),
        }
        stats.update(exec_stats)

        # Generate reports BEFORE commit
        print("\n[STEP 7] Generating reports...")
        all_targets = [
            {'status': 'safe', 'merged_target': t} for t in safe_targets
        ] + [
            {'status': 'duplicate_conflict', 'target_key': t['target_key'],
             'conflicts': t['conflicts'], 'sources': t['sources']}
            for t in duplicate_conflict_targets
        ]

        try:
            report_paths = generate_report(all_targets, plan, stats, backup_files, report_dir, dry_run)
        except Exception as e:
            print(f"\n[ERROR] Report generation failed: {e}")
            if not dry_run:
                print("[ROLLBACK] Rolling back transaction due to report generation failure")
                conn.rollback()
                # Clean up any partially generated reports
                try:
                    if report_paths:
                        for path in report_paths.values():
                            if path and Path(path).exists():
                                Path(path).unlink()
                                print(f"[CLEANUP] Removed incomplete report: {path}")
                except:
                    pass
                raise
            else:
                conn.rollback()
                raise

        # Commit or rollback
        if dry_run:
            conn.rollback()
            print("\n[DRY-RUN] No changes applied (transaction rolled back)")
        else:
            conn.commit()
            print("\n[SUCCESS] Changes committed")

        # Print final stats
        staging_key = 'planned_staging_rows' if dry_run else 'updated_staging_rows'
        parts_key = 'planned_parts' if dry_run else 'updated_parts'
        tooling_parts_key = 'planned_tooling_parts' if dry_run else 'updated_tooling_parts'
        tooling_key = 'planned_tooling' if dry_run else 'updated_tooling'

        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Source groups: {plan['summary']['source_groups']}")
        print(f"Unique target groups: {plan['summary']['unique_target_groups']}")
        print(f"Safe targets: {stats['safe_targets']}")
        print(f"Duplicate conflict targets: {stats['duplicate_conflict_targets']}")
        print(f"Unique staging rows: {plan['summary']['unique_staging_rows']}")
        print(f"Unique parts: {plan['summary']['unique_parts']}")
        print(f"Unique tooling_parts: {plan['summary']['unique_tooling_parts']}")
        print(f"Unique tooling: {plan['summary']['unique_tooling']}")
        print(f"{'Planned' if dry_run else 'Updated'} staging rows: {stats.get(staging_key, 0)}")
        print(f"{'Planned' if dry_run else 'Updated'} parts: {stats.get(parts_key, 0)}")
        print(f"{'Planned' if dry_run else 'Updated'} tooling_parts: {stats.get(tooling_parts_key, 0)}")
        print(f"{'Planned' if dry_run else 'Updated'} tooling: {stats.get(tooling_key, 0)}")
        print(f"Warnings: {len(plan['warnings'])}")
        print(f"Action conflicts: {len(plan['conflicts'])}")
        print("="*70)

        return 0

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
