#!/usr/bin/env python3
"""
Excel Dynamic Parser - Authoritative Implementation
Phase 2: Parse Excel and stage to import_batches/excel_import_rows
Does NOT write to formal tables (customers/parts/tooling/relationships)
"""

import sys
import os
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
import xlrd

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import psycopg2
import psycopg2.extras
from urllib.parse import urlparse


def get_db_config():
    """Get database config from settings or environment - NO PASSWORD FALLBACK."""
    try:
        # Import settings from backend
        from app.core.config import settings
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured in settings")

        db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        parsed = urlparse(db_url)

        if not parsed.hostname or not parsed.password:
            raise ValueError("DATABASE_URL must include host and password")

        config = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'stamping_system',
            'user': parsed.username or 'postgres',
            'password': parsed.password
        }
        print(f"[INFO] Loaded config from settings: {config['host']}:{config['port']}/{config['database']}")
        return config
    except Exception as e:
        print(f"[ERROR] Could not load database configuration: {e}")
        print("[ERROR] Please configure DATABASE_URL in backend/.env")
        raise


# Column header synonyms - EXACT MATCH FIRST
HEADER_SYNONYMS = {
    # Full exact matches - highest priority
    'customer_name': ['客户名称', '客户简称', '客户'],
    'customer_part_no': ['原图产品编号', '客户产品编号', '客户图号'],
    'customer_part_name': ['原图产品名称1', '原图产品名称2', '客户产品名称', '原图产品名称'],
    'tooling_number': ['本厂产品编号'],  # EXACT - do NOT match partial
    'internal_name': ['本厂产品名称'],   # EXACT - do NOT match partial
    'mold_type': ['模具类型', '模别'],
    'process_step_count': ['模数', '工序数'],
    'cavity_count': ['穴数', '1出几'],
    'material': ['材质', '材料'],
    'spec': ['用料规格(T*W*PH)', '用料规格', '规格'],
    'remark': ['备注', '说明'],
    'thickness': ['料厚', 'T'],
    'width': ['料宽', 'W'],
    'pitch': ['步距', 'P'],
    'gross_weight': ['毛重'],
    'net_weight': ['净重', '单重'],
    'position': ['左右件', '位置'],
}


def normalize_header(header: str) -> str:
    """Normalize header text - remove punctuation and whitespace."""
    if not header:
        return ''
    # Remove whitespace and common punctuation
    normalized = str(header).strip()
    normalized = normalized.replace('：', '').replace(':', '')
    normalized = normalized.replace('（', '').replace('）', '')
    normalized = normalized.replace('(', '').replace(')', '')
    return normalized


def detect_headers(sheet) -> Tuple[Optional[int], Dict[str, int]]:
    """
    Detect header row and column mapping.
    Uses EXACT match first, then substring match with conflict detection.
    Returns: (header_row_index, {field_name: column_index})
    """
    for row_idx in range(min(10, sheet.nrows)):
        row_values = [str(sheet.cell_value(row_idx, col_idx)).strip()
                      for col_idx in range(sheet.ncols)]

        # Normalize all headers
        normalized_headers = [normalize_header(h) for h in row_values]

        # Check if this row looks like a header
        matched_fields = {}
        used_columns = set()  # Prevent multiple fields mapping to same column

        # Pass 1: Exact matches
        for field, synonyms in HEADER_SYNONYMS.items():
            for col_idx, norm_header in enumerate(normalized_headers):
                if col_idx in used_columns:
                    continue
                # Exact match
                if norm_header in synonyms:
                    matched_fields[field] = col_idx
                    used_columns.add(col_idx)
                    break

        # Pass 2: Substring matches (only if not already matched)
        for field, synonyms in HEADER_SYNONYMS.items():
            if field in matched_fields:
                continue  # Already matched exactly

            for col_idx, norm_header in enumerate(normalized_headers):
                if col_idx in used_columns:
                    continue

                # Only allow substring match for specific safe fields
                # Do NOT substring match critical fields like tooling_number, internal_name
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
        # This prevents title rows from being mistaken as headers
        key_fields = ['customer_name', 'tooling_number', 'internal_name', 'customer_part_no']
        matched_key_count = sum(1 for f in key_fields if f in matched_fields)

        # Must have customer_name AND at least 2 other key fields
        if 'customer_name' in matched_fields and matched_key_count >= 3:
            return row_idx, matched_fields

        # OR must have both tooling_number and internal_name (for sheets with these columns)
        if 'tooling_number' in matched_fields and 'internal_name' in matched_fields:
            return row_idx, matched_fields

    return None, {}


def is_special_sheet(sheet_name: str) -> Tuple[bool, str]:
    """Check if sheet is special (customer name code, etc.)."""
    special_patterns = [
        ('客户名称代号', 'Customer name codes'),
        ('说明', 'Documentation'),
        ('目录', 'Table of contents'),
        ('索引', 'Index'),
    ]

    for pattern, reason in special_patterns:
        if pattern in sheet_name:
            return True, reason

    return False, ''


def is_empty_row(row_values: List[Any]) -> bool:
    """Check if row is empty."""
    return all(not str(v).strip() for v in row_values)


def is_header_row(row_values: List[Any]) -> bool:
    """Check if row is a header."""
    text = ' '.join(str(v) for v in row_values).lower()
    header_keywords = ['客户', '产品编号', '模具', '料厚', '材料']
    return sum(1 for kw in header_keywords if kw in text) >= 3


def is_summary_row(row_values: List[Any]) -> bool:
    """Check if row is a summary/total."""
    text = ' '.join(str(v) for v in row_values).lower()
    return any(kw in text for kw in ['合计', '小计', '总计', '共计'])


def is_template_row(row_values: List[Any]) -> bool:
    """Check if row is an empty template."""
    # Check for placeholder patterns
    text = ' '.join(str(v) for v in row_values)
    if not text.strip():
        return False

    # Template rows often have repetitive placeholder values
    non_empty = [str(v).strip() for v in row_values if str(v).strip()]
    if len(non_empty) == 0:
        return True

    # Check for common template patterns
    template_patterns = ['____', '...', '###']
    return any(pat in text for pat in template_patterns)


def parse_mold_type(value: str) -> Tuple[Optional[str], bool]:
    """
    Parse mold type and determine if continuous.
    Returns: (mold_type, is_continuous)
    """
    if not value:
        return None, False

    value = str(value).strip()

    # Remove trailing numbers (e.g., "工程模9" -> "工程模")
    # This happens when mold type and step count are combined
    cleaned_value = re.sub(r'\d+$', '', value).strip()

    # Continuous mold patterns
    continuous_patterns = ['连续模', '连续']
    if any(p in cleaned_value for p in continuous_patterns):
        return cleaned_value, True

    # Non-continuous patterns
    non_continuous_patterns = ['工程模', '简易模', '单工序', '级进模']
    if any(p in cleaned_value for p in non_continuous_patterns):
        return cleaned_value, False

    # If contains "模" but not identified, assume non-continuous
    if '模' in cleaned_value:
        return cleaned_value, False

    return cleaned_value if cleaned_value else value, False


def parse_cavity_count(spec: str, remark: str) -> Optional[int]:
    """
    Parse cavity count from spec and remark fields.
    ONLY matches explicit cavity expressions like "1出2", "一出2", "(1出2)".
    Does NOT match T*W*P dimensions like "1*90*88" or "0.8*71*98".
    """
    # Combine spec and remark
    combined = f"{spec or ''} {remark or ''}"

    if not combined.strip():
        return None

    # ONLY match explicit "1出N" or "一出N" patterns
    # DO NOT match plain "1*N" as it could be dimensions
    patterns = [
        r'1\s*出\s*(\d+)',           # 1出2
        r'一\s*出\s*(\d+)',           # 一出2
        r'\(\s*1\s*出\s*(\d+)\s*\)', # (1出2)
        r'\(\s*一\s*出\s*(\d+)\s*\)', # (一出2)
    ]

    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            try:
                count = int(match.group(1))
                if 1 <= count <= 100:  # Reasonable range
                    return count
            except:
                pass

    return None


def parse_process_step_count(value: str) -> Optional[int]:
    """Parse process step count (模数)."""
    if not value:
        return None

    value = str(value).strip()

    # Match numeric patterns: "9", "9模", "9步", etc.
    match = re.search(r'(\d+)', value)
    if match:
        try:
            count = int(match.group(1))
            # Reasonable range for process steps: 1-500
            if 1 <= count <= 500:
                return count
        except:
            pass

    return None


def parse_numeric(value: Any) -> Optional[float]:
    """Parse numeric value (T/W/P/weight)."""
    if value is None or value == '':
        return None

    try:
        # Handle xlrd numeric types
        if isinstance(value, (int, float)):
            return float(value)

        # Parse string
        value_str = str(value).strip()
        # Remove common units
        value_str = value_str.replace('mm', '').replace('MM', '').strip()

        # Extract first number
        match = re.search(r'(\d+\.?\d*)', value_str)
        if match:
            return float(match.group(1))
    except:
        pass

    return None


def parse_position(value: str) -> Optional[str]:
    """Parse position (左/右/上/下)."""
    if not value:
        return None

    value = str(value).strip().upper()

    position_map = {
        '左': 'LEFT',
        '右': 'RIGHT',
        '上': 'TOP',
        '下': 'BOTTOM',
        'L': 'LEFT',
        'R': 'RIGHT',
        'T': 'TOP',
        'B': 'BOTTOM',
    }

    for key, val in position_map.items():
        if key in value:
            return val

    return None


def parse_row(row_values: List[Any], column_map: Dict[str, int], sheet_name: str, last_customer: str) -> Dict[str, Any]:
    """
    Parse a single row and extract all fields.
    Returns dict with parsed values.

    Args:
        row_values: Cell values from the row
        column_map: Field name to column index mapping
        sheet_name: Name of the sheet (for customer inheritance)
        last_customer: Last non-empty customer from previous rows
    """
    def get_cell(field: str) -> Any:
        col_idx = column_map.get(field)
        if col_idx is not None and col_idx < len(row_values):
            val = row_values[col_idx]
            return str(val).strip() if val else None
        return None

    # Extract raw values
    customer_name = get_cell('customer_name')

    # Customer inheritance: if empty, use last_customer or extract from sheet_name
    if not customer_name:
        if last_customer:
            customer_name = last_customer
        else:
            # Try to extract customer from sheet name (e.g., "浙江万宝机械有限公司(A)")
            # Remove trailing letters in parentheses
            import re
            match = re.match(r'^(.+?)\s*\([A-Z0-9\-]+\)\s*$', sheet_name)
            if match:
                customer_name = match.group(1).strip()

    customer_part_no = get_cell('customer_part_no')
    customer_part_name = get_cell('customer_part_name')
    tooling_number = get_cell('tooling_number')
    internal_name = get_cell('internal_name')
    mold_type_raw = get_cell('mold_type')
    process_step_raw = get_cell('process_step_count')
    cavity_raw = get_cell('cavity_count')
    material = get_cell('material')
    spec = get_cell('spec')
    remark = get_cell('remark')

    # Parse mold type
    parsed_mold_type, is_continuous = parse_mold_type(mold_type_raw)

    # Parse process step count - ONLY for non-continuous molds
    # Continuous molds must have NULL process_step_count
    if is_continuous:
        parsed_process_step = None
    else:
        parsed_process_step = parse_process_step_count(process_step_raw)

    # Parse cavity count from spec and remark
    parsed_cavity = parse_cavity_count(spec, remark)
    if not parsed_cavity:
        parsed_cavity = parse_cavity_count(cavity_raw, '')

    # Parse TWP
    thickness = parse_numeric(get_cell('thickness'))
    width = parse_numeric(get_cell('width'))
    pitch = parse_numeric(get_cell('pitch'))

    # Parse weights
    gross_weight = parse_numeric(get_cell('gross_weight'))
    net_weight = parse_numeric(get_cell('net_weight'))

    # Parse position
    position = parse_position(get_cell('position'))

    return {
        'parsed_customer_name': customer_name,
        'parsed_customer_part_no': customer_part_no,
        'parsed_customer_part_name': customer_part_name,
        'parsed_tooling_number': tooling_number,
        'parsed_internal_name': internal_name,
        'parsed_mold_type': parsed_mold_type,
        'parsed_is_continuous': is_continuous,
        'parsed_process_step_count': parsed_process_step,
        'parsed_cavity_count': parsed_cavity,
        'parsed_material': material,
        'parsed_thickness': thickness,
        'parsed_width': width,
        'parsed_pitch': pitch,
        'parsed_gross_weight': gross_weight,
        'parsed_net_weight': net_weight,
        'parsed_position': position,
    }


def classify_row(row_values: List[Any], parsed_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Classify row as VALID/SKIPPED/REVIEW/ERROR.
    Returns: (status, reason)

    VALID requires: customer + internal_name + tooling_number
    Missing any of these goes to REVIEW with specific reason.
    """
    # Skip empty rows
    if is_empty_row(row_values):
        return 'SKIPPED', 'Empty row'

    # Skip header rows
    if is_header_row(row_values):
        return 'SKIPPED', 'Header row'

    # Skip summary rows
    if is_summary_row(row_values):
        return 'SKIPPED', 'Summary row'

    # Skip template rows
    if is_template_row(row_values):
        return 'SKIPPED', 'Template row'

    # Extract key fields
    has_customer = bool(parsed_data.get('parsed_customer_name'))
    has_tooling = bool(parsed_data.get('parsed_tooling_number'))
    has_internal = bool(parsed_data.get('parsed_internal_name'))

    # Must have customer
    if not has_customer:
        return 'SKIPPED', 'No customer name'

    # VALID requires: customer + internal_name + tooling_number
    if has_customer and has_tooling and has_internal:
        return 'VALID', ''

    # Missing tooling or internal goes to REVIEW with specific reason
    missing = []
    if not has_tooling:
        missing.append('tooling_number')
    if not has_internal:
        missing.append('internal_name')

    reason = f"Missing required fields: {', '.join(missing)}"
    return 'REVIEW', reason


def process_excel(excel_path: Path, db_config: Dict[str, Any]):
    """Process Excel file and write to staging tables."""
    print(f"\n[INFO] Opening Excel file: {excel_path}")

    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    # Calculate file hash
    with open(excel_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()

    file_size = excel_path.stat().st_size
    file_name = excel_path.name

    print(f"[INFO] File: {file_name}")
    print(f"[INFO] Size: {file_size} bytes")
    print(f"[INFO] Hash: {file_hash}")

    # Open workbook
    workbook = xlrd.open_workbook(str(excel_path))
    total_sheets = workbook.nsheets

    print(f"[INFO] Total sheets: {total_sheets}")

    # Connect to database
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()

    try:
        # Check for existing batches with same file
        cur.execute("""
            SELECT id FROM import_batches
            WHERE file_name = %s OR file_hash = %s
        """, (file_name, file_hash))

        existing_batch_ids = [row[0] for row in cur.fetchall()]

        if existing_batch_ids:
            print(f"[INFO] Found existing batch(es): {existing_batch_ids}")
            print(f"[INFO] Deleting old data...")

            # Delete child rows first
            cur.execute("""
                DELETE FROM excel_import_rows
                WHERE batch_id = ANY(%s)
            """, (existing_batch_ids,))
            deleted_rows = cur.rowcount
            print(f"  Deleted {deleted_rows} rows from excel_import_rows")

            # Delete parent batches
            cur.execute("""
                DELETE FROM import_batches
                WHERE id = ANY(%s)
            """, (existing_batch_ids,))
            deleted_batches = cur.rowcount
            print(f"  Deleted {deleted_batches} batch(es)")

            conn.commit()

        # Create new batch
        cur.execute("""
            INSERT INTO import_batches
            (file_name, file_hash, file_size, total_sheets, status, started_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (file_name, file_hash, file_size, total_sheets, 'PROCESSING', datetime.now()))

        batch_id = cur.fetchone()[0]
        conn.commit()

        print(f"[INFO] Created batch {batch_id}")

        # Process sheets
        data_sheets = 0
        total_rows = 0
        valid_rows = 0
        review_rows = 0
        skipped_rows = 0
        error_rows = 0

        for sheet_idx in range(total_sheets):
            sheet = workbook.sheet_by_index(sheet_idx)
            sheet_name = sheet.name

            print(f"\n[INFO] Processing sheet {sheet_idx + 1}/{total_sheets}: {sheet_name}")

            # Check if special sheet
            is_special, special_reason = is_special_sheet(sheet_name)
            if is_special:
                print(f"  [SKIP] Special sheet: {special_reason}")
                continue

            # Detect headers
            header_row_idx, column_map = detect_headers(sheet)

            if header_row_idx is None:
                print(f"  [SKIP] Could not detect headers")
                continue

            print(f"  [INFO] Found headers at row {header_row_idx + 1}")
            print(f"  [INFO] Mapped columns: {list(column_map.keys())}")

            # Debug: print first few data rows if tooling_number is missing
            if 'tooling_number' not in column_map and sheet_idx < 5:
                print(f"  [DEBUG] Missing tooling_number! Header row {header_row_idx}:")
                row_values = [str(sheet.cell_value(header_row_idx, col_idx)).strip()
                             for col_idx in range(min(15, sheet.ncols))]
                for idx, val in enumerate(row_values):
                    if val:
                        print(f"    col_{idx}: {repr(val)}")

            data_sheets += 1

            # Track last non-empty customer for inheritance
            last_customer = None

            # Process data rows
            for row_idx in range(header_row_idx + 1, sheet.nrows):
                total_rows += 1

                # Extract row values
                row_values = [sheet.cell_value(row_idx, col_idx)
                            for col_idx in range(sheet.ncols)]

                # Parse row
                try:
                    parsed_data = parse_row(row_values, column_map, sheet_name, last_customer)

                    # Update last_customer for next row
                    if parsed_data.get('parsed_customer_name'):
                        # Only update if it was explicitly in the cell, not inherited
                        col_idx = column_map.get('customer_name')
                        if col_idx is not None and col_idx < len(row_values):
                            cell_val = row_values[col_idx]
                            if cell_val and str(cell_val).strip():
                                last_customer = parsed_data['parsed_customer_name']

                    # Classify row
                    status, reason = classify_row(row_values, parsed_data)

                    # Count by status
                    if status == 'VALID':
                        valid_rows += 1
                    elif status == 'REVIEW':
                        review_rows += 1
                    elif status == 'SKIPPED':
                        skipped_rows += 1
                    elif status == 'ERROR':
                        error_rows += 1

                    # Insert to staging
                    cur.execute("""
                        INSERT INTO excel_import_rows (
                            batch_id, source_sheet, source_row, raw_data,
                            validation_status, validation_errors,
                            parsed_customer_name, parsed_customer_part_no,
                            parsed_customer_part_name,
                            parsed_tooling_number, parsed_internal_name,
                            parsed_mold_type, parsed_is_continuous,
                            parsed_process_step_count, parsed_cavity_count,
                            parsed_material, parsed_thickness, parsed_width,
                            parsed_pitch, parsed_gross_weight, parsed_net_weight,
                            parsed_position
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        batch_id, sheet_name, row_idx + 1,
                        psycopg2.extras.Json([str(v) for v in row_values]),
                        status, reason if reason else None,
                        parsed_data.get('parsed_customer_name'),
                        parsed_data.get('parsed_customer_part_no'),
                        parsed_data.get('parsed_customer_part_name'),
                        parsed_data.get('parsed_tooling_number'),
                        parsed_data.get('parsed_internal_name'),
                        parsed_data.get('parsed_mold_type'),
                        parsed_data.get('parsed_is_continuous'),
                        parsed_data.get('parsed_process_step_count'),
                        parsed_data.get('parsed_cavity_count'),
                        parsed_data.get('parsed_material'),
                        parsed_data.get('parsed_thickness'),
                        parsed_data.get('parsed_width'),
                        parsed_data.get('parsed_pitch'),
                        parsed_data.get('parsed_gross_weight'),
                        parsed_data.get('parsed_net_weight'),
                        parsed_data.get('parsed_position'),
                    ))

                except Exception as e:
                    error_rows += 1
                    print(f"  [ERROR] Row {row_idx + 1}: {e}")

                    # Insert error row
                    cur.execute("""
                        INSERT INTO excel_import_rows (
                            batch_id, source_sheet, source_row, raw_data,
                            validation_status, validation_errors
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        batch_id, sheet_name, row_idx + 1,
                        psycopg2.extras.Json([str(v) for v in row_values]),
                        'ERROR', str(e)
                    ))

                # Commit every 500 rows
                if total_rows % 500 == 0:
                    conn.commit()
                    print(f"  [INFO] Processed {total_rows} rows...")

            conn.commit()
            print(f"  [INFO] Sheet complete: {sheet.nrows - header_row_idx - 1} rows processed")

        # Update batch status
        cur.execute("""
            UPDATE import_batches
            SET status = %s,
                data_sheets = %s,
                total_rows = %s,
                valid_rows = %s,
                failed_rows = %s,
                completed_at = %s
            WHERE id = %s
        """, ('COMPLETED', data_sheets, total_rows, valid_rows,
              error_rows, datetime.now(), batch_id))

        conn.commit()

        # Print summary
        print(f"\n{'='*70}")
        print(f"IMPORT SUMMARY")
        print(f"{'='*70}")
        print(f"Total sheets: {total_sheets}")
        print(f"Data sheets: {data_sheets}")
        print(f"Special sheets: {total_sheets - data_sheets}")
        print(f"Total rows scanned: {total_rows}")
        print(f"  VALID: {valid_rows}")
        print(f"  REVIEW: {review_rows}")
        print(f"  SKIPPED: {skipped_rows}")
        print(f"  ERROR: {error_rows}")
        print(f"{'='*70}")

    finally:
        cur.close()
        conn.close()


def main():
    """Main entry point."""
    print("="*70)
    print("Excel Dynamic Parser - Phase 2")
    print("="*70)

    # Get database config
    try:
        db_config = get_db_config()
    except Exception as e:
        print(f"[FATAL] {e}")
        return 1

    # Excel file path
    excel_path = Path(__file__).parent.parent.parent / 'excel' / '五金模具及产品清单表.xls'

    try:
        process_excel(excel_path, db_config)
        print("\n[SUCCESS] Import completed")
        return 0
    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
