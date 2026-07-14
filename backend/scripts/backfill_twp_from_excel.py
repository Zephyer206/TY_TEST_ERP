"""Backfill TWP (Thickness/Width/Pitch) from Excel import data.

This script:
1. Reads excel_import_rows with resolved_part_id
2. Parses combined spec fields from ONLY the spec column (header-aware)
3. Only backfills when parts.thickness/width/pitch are ALL null
4. Only backfills when all sources for same part_id agree (unique consistent value)
5. Marks conflicts and does NOT backfill them
6. Dry-run by default, requires --execute flag to apply changes

CRITICAL: Must use detect_headers to find spec column, NEVER scan all raw_data columns.
This prevents misinterpreting customer_part_no (e.g., XC2.39.81) as spec data.
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from decimal import Decimal

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
import xlrd

from app.database import get_db_context
from app.models.part import Part


class TWPParser:
    """Parse TWP (Thickness × Width × Pitch) from various spec formats."""

    @classmethod
    def parse_spec(cls, spec_str: Optional[str]) -> Optional[Tuple[Decimal, Decimal, Decimal]]:
        """Parse a spec string to extract T, W, P.

        Returns:
            (thickness, width, pitch) or None if cannot parse reliably
        """
        if not spec_str or not isinstance(spec_str, str):
            return None

        spec_str = spec_str.strip()
        if not spec_str:
            return None

        # Check for patterns that look like customer part numbers BEFORE removing T/W/P markers
        # e.g., "XC2.39.81", "ABC123", "XC2.39.81/XC2.39.16"
        # Multiple consecutive uppercase letters (except T/W/P at start) or multiple slashes
        if re.search(r'[A-Z]{2,}', spec_str):
            # Check if it's just T/W/P markers at the start
            if not re.match(r'^[TWP]\d', spec_str, re.IGNORECASE):
                return None

        # Multiple slashes indicate customer part number list
        if spec_str.count('/') >= 2:
            return None

        # Remove cavity info (1出3, 一出2, (1出3))
        spec_str = re.sub(r'[一1]\s*出\s*\d+', '', spec_str)
        spec_str = re.sub(r'\([一1]\s*出\s*\d+\)', '', spec_str)

        # Remove leading/embedded T/W/P markers if present
        spec_str = re.sub(r'^T\s*', '', spec_str, flags=re.IGNORECASE)
        spec_str = re.sub(r'W\s*', '', spec_str, flags=re.IGNORECASE)
        spec_str = re.sub(r'P\s*', '', spec_str, flags=re.IGNORECASE)

        # Find all numbers (with optional tolerances in parentheses)
        # Pattern: number optionally followed by (tolerance)
        number_pattern = r'(\d+\.?\d*)(?:\s*\([^\)]+\))?'

        # Find separators: *, ×, x (lowercase x only in word boundary context)
        # DO NOT use X (uppercase) as separator - it's often part of customer codes
        # Split by these separators
        parts = re.split(r'\s*[*×]\s*|\s+x\s+', spec_str)

        # Extract numbers from each part
        numbers = []
        for part in parts:
            # Find the first number in this part
            match = re.search(number_pattern, part)
            if match:
                try:
                    num = Decimal(match.group(1))
                    numbers.append(num)
                except:
                    pass

        # Need exactly 3 numbers for T*W*P
        if len(numbers) != 3:
            return None

        # Basic sanity check: reasonable ranges
        # Thickness: 0.1-10mm, Width: 1-1000mm, Pitch: 1-1000mm
        t, w, p = numbers
        if not (0.1 <= t <= 10 and 1 <= w <= 1000 and 1 <= p <= 1000):
            return None

        return (t, w, p)

    @classmethod
    def test_parser(cls):
        """Test parser with various formats."""
        test_cases = [
            ("0.6*25*53", (Decimal('0.6'), Decimal('25'), Decimal('53'))),
            ("1.2*65*20(1出3)", (Decimal('1.2'), Decimal('65'), Decimal('20'))),
            ("1.0*9.0(±0.05)*27", (Decimal('1.0'), Decimal('9.0'), Decimal('27'))),
            ("1.2×50×30", (Decimal('1.2'), Decimal('50'), Decimal('30'))),
            ("0.8 x 25 x 40", (Decimal('0.8'), Decimal('25'), Decimal('40'))),
            ("T1.2*W50*P40", (Decimal('1.2'), Decimal('50'), Decimal('40'))),
            ("invalid", None),
            ("1.2*50", None),  # Only 2 numbers
            ("100*200*300", None),  # Numbers out of range
            ("XC2.39.81", None),  # Customer part number - should NOT parse
            ("XC2.39.81/XC2.39.16/XC2.39.15", None),  # Multiple customer part numbers
            ("1.5X30X50", None),  # X as separator deprecated - use * or × instead
        ]

        print("Testing TWP Parser:")
        all_pass = True
        for spec_str, expected in test_cases:
            result = cls.parse_spec(spec_str)
            passed = result == expected
            all_pass = all_pass and passed
            status = "PASS" if passed else "FAIL"
            print(f"  {status} '{spec_str}' -> {result}")

        return all_pass


# Import detect_headers from import_excel_authoritative.py
def normalize_header(header: str) -> str:
    """Normalize header text - remove punctuation and whitespace."""
    if not header:
        return ''
    normalized = str(header).strip()
    normalized = normalized.replace('：', '').replace(':', '')
    normalized = normalized.replace('（', '').replace('）', '')
    normalized = normalized.replace('(', '').replace(')', '')
    return normalized


HEADER_SYNONYMS = {
    'customer_name': ['客户名称', '客户简称', '客户'],
    'customer_part_no': ['原图产品编号', '客户产品编号', '客户图号'],
    'customer_part_name': ['原图产品名称1', '原图产品名称2', '客户产品名称', '原图产品名称'],
    'tooling_number': ['本厂产品编号'],
    'internal_name': ['本厂产品名称'],
    'mold_type': ['模具类型', '模别'],
    'process_step_count': ['模数', '工序数'],
    'cavity_count': ['穴数', '1出几'],
    'material': ['材质', '材料'],
    'spec': ['用料规格(T*W*PH)', '用料规格', '规格'],
    'remark': ['备注', '说明'],
    'thickness': ['料厚', 'T'],
    'width': ['料宽', 'W'],
    'pitch': ['步距', 'P'],
}


def detect_headers(sheet) -> Tuple[Optional[int], Dict[str, int]]:
    """
    Detect header row and column mapping.
    Returns: (header_row_index, {field_name: column_index})
    """
    for row_idx in range(min(10, sheet.nrows)):
        row_values = [str(sheet.cell_value(row_idx, col_idx)).strip()
                      for col_idx in range(sheet.ncols)]

        normalized_headers = [normalize_header(h) for h in row_values]

        matched_fields = {}
        used_columns = set()

        # Pass 1: Exact matches
        for field, synonyms in HEADER_SYNONYMS.items():
            for col_idx, norm_header in enumerate(normalized_headers):
                if col_idx in used_columns:
                    continue
                if norm_header in synonyms:
                    matched_fields[field] = col_idx
                    used_columns.add(col_idx)
                    break

        # Pass 2: Substring matches for safe fields
        for field, synonyms in HEADER_SYNONYMS.items():
            if field in matched_fields:
                continue

            for col_idx, norm_header in enumerate(normalized_headers):
                if col_idx in used_columns:
                    continue

                if field in ['customer_name', 'customer_part_no', 'customer_part_name',
                           'material', 'position', 'remark', 'spec']:
                    for syn in synonyms:
                        if syn in norm_header or norm_header in syn:
                            matched_fields[field] = col_idx
                            used_columns.add(col_idx)
                            break
                    if field in matched_fields:
                        break

        # Need at least 3 key fields to be a valid header
        key_fields = ['customer_name', 'tooling_number', 'internal_name', 'customer_part_no']
        matched_key_count = sum(1 for f in key_fields if f in matched_fields)

        if 'customer_name' in matched_fields and matched_key_count >= 3:
            return row_idx, matched_fields

        if 'tooling_number' in matched_fields and 'internal_name' in matched_fields:
            return row_idx, matched_fields

    return None, {}


async def get_sheet_header_map(excel_path: Path) -> Dict[str, Dict[str, int]]:
    """
    Open Excel file and get header mapping for each sheet.
    Returns: {sheet_name: {field_name: column_index}}
    """
    if not excel_path.exists():
        print(f"ERROR: Excel file not found: {excel_path}")
        return {}

    print(f"Opening Excel file: {excel_path}")

    try:
        workbook = xlrd.open_workbook(str(excel_path), formatting_info=False)
    except Exception as e:
        print(f"ERROR: Could not open Excel file: {e}")
        return {}

    sheet_headers = {}

    for sheet_name in workbook.sheet_names():
        sheet = workbook.sheet_by_name(sheet_name)
        header_row_idx, field_map = detect_headers(sheet)

        if header_row_idx is not None and field_map:
            sheet_headers[sheet_name] = field_map
            spec_col = field_map.get('spec')
            print(f"  Sheet '{sheet_name}': found headers at row {header_row_idx}, spec column: {spec_col}")
        else:
            print(f"  Sheet '{sheet_name}': no headers detected, will skip")

    return sheet_headers


async def analyze_excel_import_data(db: AsyncSession, sheet_headers: Dict[str, Dict[str, int]]) -> Dict:
    """Analyze excel_import_rows to find TWP data using header-aware parsing."""

    # Get all IMPORTED rows with resolved_part_id
    result = await db.execute(text("""
        SELECT
            id,
            source_sheet,
            resolved_part_id,
            parsed_thickness,
            parsed_width,
            parsed_pitch,
            raw_data
        FROM excel_import_rows
        WHERE validation_status = 'IMPORTED'
        AND resolved_part_id IS NOT NULL
        ORDER BY resolved_part_id, id
    """))

    rows = result.fetchall()

    print(f"\nAnalyzing {len(rows)} excel import rows...")

    # Group by part_id
    part_specs = {}  # part_id -> list of (row_id, T, W, P)

    parsed_count = 0
    failed_count = 0
    skipped_no_header = 0

    for row in rows:
        row_id, source_sheet, part_id, parsed_t, parsed_w, parsed_p, raw_data = row

        # Priority 1: Use already parsed fields
        twp = None
        if parsed_t and parsed_w and parsed_p:
            twp = (Decimal(str(parsed_t)), Decimal(str(parsed_w)), Decimal(str(parsed_p)))
            parsed_count += 1
        else:
            # Priority 2: Parse from spec column using header map
            if source_sheet in sheet_headers:
                field_map = sheet_headers[source_sheet]
                spec_col_idx = field_map.get('spec')

                if spec_col_idx is not None and raw_data:
                    try:
                        data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                        if isinstance(data, list) and spec_col_idx < len(data):
                            spec_str = str(data[spec_col_idx]).strip() if data[spec_col_idx] else None
                            if spec_str:
                                twp = TWPParser.parse_spec(spec_str)
                                if twp:
                                    parsed_count += 1
                    except:
                        pass
            else:
                # No header map for this sheet - skip parsing from raw_data
                skipped_no_header += 1

        if not twp:
            failed_count += 1
            continue

        if part_id not in part_specs:
            part_specs[part_id] = []
        part_specs[part_id].append((row_id, twp))

    # Analyze consistency
    unique_parts = 0
    conflict_parts = 0
    conflict_examples = []

    part_twp_map = {}  # part_id -> (T, W, P) for unique consistent specs

    for part_id, specs in part_specs.items():
        unique_specs = set(spec[1] for spec in specs)

        if len(unique_specs) == 1:
            # All sources agree
            unique_parts += 1
            part_twp_map[part_id] = list(unique_specs)[0]
        else:
            # Conflict: multiple different specs
            conflict_parts += 1
            if len(conflict_examples) < 5:
                conflict_examples.append({
                    'part_id': part_id,
                    'specs': [{'row_id': r[0], 'twp': r[1]} for r in specs]
                })

    return {
        'total_rows': len(rows),
        'parsed_count': parsed_count,
        'failed_count': failed_count,
        'skipped_no_header': skipped_no_header,
        'total_parts_with_twp': len(part_specs),
        'unique_consistent_parts': unique_parts,
        'conflict_parts': conflict_parts,
        'conflict_examples': conflict_examples,
        'part_twp_map': part_twp_map
    }


async def analyze_parts_backfill_candidates(db: AsyncSession, part_twp_map: Dict) -> Dict:
    """Check which parts can be safely backfilled."""

    if not part_twp_map:
        return {
            'eligible': 0,
            'already_has_data': 0,
            'would_conflict': 0,
            'safe_to_backfill': 0,
            'backfill_candidates': []
        }

    part_ids = list(part_twp_map.keys())

    # Check current TWP status for these parts
    result = await db.execute(
        select(Part.id, Part.internal_name, Part.thickness, Part.width, Part.pitch)
        .where(Part.id.in_(part_ids))
    )

    parts = result.fetchall()

    already_has_data = 0
    would_conflict = 0
    safe_to_backfill = 0
    backfill_candidates = []

    for part in parts:
        part_id, name, t, w, p = part
        new_t, new_w, new_p = part_twp_map[part_id]

        # Check if any field is already populated
        if t is not None or w is not None or p is not None:
            # Check if existing data conflicts with new data
            conflicts = []
            if t is not None and Decimal(str(t)) != new_t:
                conflicts.append('thickness')
            if w is not None and Decimal(str(w)) != new_w:
                conflicts.append('width')
            if p is not None and Decimal(str(p)) != new_p:
                conflicts.append('pitch')

            if conflicts:
                would_conflict += 1
            else:
                already_has_data += 1
        else:
            # All THREE fields are null - safe to backfill
            safe_to_backfill += 1
            backfill_candidates.append({
                'part_id': part_id,
                'name': name,
                'new_twp': (new_t, new_w, new_p)
            })

    return {
        'eligible': len(parts),
        'already_has_data': already_has_data,
        'would_conflict': would_conflict,
        'safe_to_backfill': safe_to_backfill,
        'backfill_candidates': backfill_candidates
    }


async def execute_backfill(db: AsyncSession, candidates: List[Dict], dry_run: bool = True) -> Dict:
    """Execute the backfill operation."""

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)
        return {'updated': 0, 'dry_run': True}

    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = Path(__file__).parent / "backups" / f"parts_twp_backup_{timestamp}.json"
    backup_file.parent.mkdir(parents=True, exist_ok=True)

    backup_data = {
        'timestamp': timestamp,
        'candidates_count': len(candidates),
        'backups': []
    }

    updated_count = 0

    for candidate in candidates:
        part_id = candidate['part_id']
        new_t, new_w, new_p = candidate['new_twp']

        # Get current data for backup
        part = await db.get(Part, part_id)
        if part:
            backup_data['backups'].append({
                'part_id': part_id,
                'name': part.internal_name,
                'old_thickness': float(part.thickness) if part.thickness else None,
                'old_width': float(part.width) if part.width else None,
                'old_pitch': float(part.pitch) if part.pitch else None,
                'new_thickness': float(new_t),
                'new_width': float(new_w),
                'new_pitch': float(new_p)
            })

            # Update
            part.thickness = new_t
            part.width = new_w
            part.pitch = new_p
            updated_count += 1

    # Save backup
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)

    await db.commit()

    print(f"\nBackup saved to: {backup_file}")
    print(f"Updated {updated_count} parts")

    return {
        'updated': updated_count,
        'backup_file': str(backup_file),
        'dry_run': False
    }


async def main():
    """Main execution."""
    import argparse

    parser = argparse.ArgumentParser(description='Backfill TWP from Excel import data')
    parser.add_argument('--execute', action='store_true', help='Execute backfill (default is dry-run)')
    parser.add_argument('--test-parser', action='store_true', help='Test TWP parser only')
    parser.add_argument('--excel', type=str, default='excel/五金模具及产品清单表.xls',
                       help='Path to original Excel file')
    args = parser.parse_args()

    if args.test_parser:
        TWPParser.test_parser()
        return

    print("=" * 60)
    print("TWP Backfill Script (Header-Aware)")
    print("=" * 60)

    # Test parser first
    if not TWPParser.test_parser():
        print("\nParser tests failed! Aborting.")
        return

    # Get Excel file path
    excel_path = Path(__file__).parent.parent.parent / args.excel
    if not excel_path.exists():
        print(f"\nERROR: Excel file not found: {excel_path}")
        print("Please provide correct path with --excel flag")
        return

    # Read sheet headers from original Excel
    sheet_headers = await get_sheet_header_map(excel_path)
    if not sheet_headers:
        print("\nERROR: No sheet headers detected in Excel file")
        return

    async with get_db_context() as db:
        # Step 1: Analyze excel import data
        print("\n" + "=" * 60)
        print("Step 1: Analyzing Excel Import Data (Header-Aware)")
        print("=" * 60)

        analysis = await analyze_excel_import_data(db, sheet_headers)

        print(f"\nTotal import rows: {analysis['total_rows']}")
        print(f"Successfully parsed TWP: {analysis['parsed_count']}")
        print(f"Failed to parse: {analysis['failed_count']}")
        print(f"Skipped (no header map): {analysis['skipped_no_header']}")
        print(f"Parts with TWP data: {analysis['total_parts_with_twp']}")
        print(f"  - Unique consistent: {analysis['unique_consistent_parts']}")
        print(f"  - Conflicting: {analysis['conflict_parts']}")

        if analysis['conflict_examples']:
            print(f"\nConflict examples (first 5):")
            for ex in analysis['conflict_examples']:
                print(f"  Part ID {ex['part_id']}:")
                for spec in ex['specs']:
                    print(f"    Row {spec['row_id']}: T={spec['twp'][0]} W={spec['twp'][1]} P={spec['twp'][2]}")

        # Step 2: Check backfill candidates
        print("\n" + "=" * 60)
        print("Step 2: Analyzing Backfill Candidates")
        print("=" * 60)

        backfill_analysis = await analyze_parts_backfill_candidates(db, analysis['part_twp_map'])

        print(f"\nParts eligible for backfill: {backfill_analysis['eligible']}")
        print(f"  - Already has complete data: {backfill_analysis['already_has_data']}")
        print(f"  - Would conflict with existing: {backfill_analysis['would_conflict']}")
        print(f"  - Safe to backfill (all NULL): {backfill_analysis['safe_to_backfill']}")

        if backfill_analysis['backfill_candidates']:
            print(f"\nSample backfill candidates (first 5):")
            for candidate in backfill_analysis['backfill_candidates'][:5]:
                twp = candidate['new_twp']
                print(f"  Part {candidate['part_id']} ({candidate['name']}): T={twp[0]} W={twp[1]} P={twp[2]}")

        # Step 3: Execute or dry-run
        print("\n" + "=" * 60)
        print("Step 3: Backfill Execution")
        print("=" * 60)

        result = await execute_backfill(
            db,
            backfill_analysis['backfill_candidates'],
            dry_run=not args.execute
        )

        if result['dry_run']:
            print(f"\nDRY RUN: Would update {backfill_analysis['safe_to_backfill']} parts")
            print("Run with --execute flag to apply changes")
        else:
            print(f"\nSUCCESS: Updated {result['updated']} parts")
            print(f"Backup: {result['backup_file']}")

        # Generate report
        report_file = Path(__file__).parent / "backups" / f"twp_backfill_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)

        report = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': result['dry_run'],
            'excel_file': str(excel_path),
            'sheets_with_headers': len(sheet_headers),
            'analysis': {
                'total_import_rows': analysis['total_rows'],
                'parsed_twp': analysis['parsed_count'],
                'failed_parse': analysis['failed_count'],
                'skipped_no_header': analysis['skipped_no_header'],
                'unique_consistent_parts': analysis['unique_consistent_parts'],
                'conflict_parts': analysis['conflict_parts']
            },
            'backfill': {
                'eligible': backfill_analysis['eligible'],
                'already_has_data': backfill_analysis['already_has_data'],
                'would_conflict': backfill_analysis['would_conflict'],
                'safe_to_backfill': backfill_analysis['safe_to_backfill'],
                'updated': result['updated']
            }
        }

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
