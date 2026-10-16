#!/usr/bin/env python3
"""
Read-only audit of customer sources from Excel vs Database.
Analyzes all worksheets to find customer names and compares with DB.
"""

import sys
import re
from pathlib import Path
from typing import Set, Dict, List, Tuple
import xlrd

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

def normalize_customer_name(name: str) -> str:
    """Normalize customer name for comparison."""
    if not name:
        return ''
    name = str(name).strip()
    # Remove common variations
    name = name.replace('有限公司', '').replace('有限', '')
    name = name.replace('（', '(').replace('）', ')')
    name = name.strip()
    return name

def is_special_sheet(sheet_name: str) -> bool:
    """Check if sheet is special (metadata, not data)."""
    special_patterns = ['客户名称代号', '说明', '目录', '索引']
    return any(p in sheet_name for p in special_patterns)

def is_b_code_sheet(sheet_name: str) -> bool:
    """Check if sheet name is a B-* code (not a customer name)."""
    # B-* pattern: B- followed by digits/letters
    return bool(re.match(r'^B-[\dA-Z]+', sheet_name, re.IGNORECASE))

def extract_customer_from_sheet_name(sheet_name: str) -> str:
    """Extract customer name from sheet name like '客户名(A)'."""
    # Remove trailing code in parentheses
    match = re.match(r'^(.+?)\s*\([A-Z0-9\-]+\)\s*$', sheet_name)
    if match:
        return match.group(1).strip()
    return sheet_name.strip()

def is_customer_part_number(text: str) -> bool:
    """Check if text looks like a part number, not a customer name."""
    if not text:
        return False
    text = str(text).strip()

    # Part number patterns
    part_patterns = [
        r'^[A-Z]{2,}-?\d',  # ABC-123, XC123
        r'^\d{3,}',  # 12345
        r'^[A-Z]\d+[A-Z]',  # A123B
    ]

    return any(re.match(p, text) for p in part_patterns)

def is_header_keyword(text: str) -> bool:
    """Check if text is a header keyword."""
    keywords = ['客户', '产品', '编号', '模具', '料厚', '材料', '备注', '说明']
    text_lower = str(text).lower()
    return any(kw in text_lower for kw in keywords)

def audit_excel_customers(excel_path: Path) -> Dict:
    """Extract all customer names from Excel with source tracking."""
    print(f"[INFO] Reading Excel: {excel_path}")

    workbook = xlrd.open_workbook(str(excel_path))

    # Track customers from different sources
    customers_from_sheet_names = {}  # {customer: [sheet_names]}
    customers_from_column = {}  # {customer: [(sheet, row)]}
    customers_from_customer_code_sheet = {}  # {customer: alias/code}

    # B-* codes found
    b_codes = []

    # Process all sheets
    for sheet_idx in range(workbook.nsheets):
        sheet = workbook.sheet_by_index(sheet_idx)
        sheet_name = sheet.name

        # Skip special sheets
        if is_special_sheet(sheet_name):
            # But check if it's customer code mapping sheet
            if '客户名称代号' in sheet_name:
                print(f"[INFO] Processing customer code sheet: {sheet_name}")
                # Extract customer mappings
                for row_idx in range(sheet.nrows):
                    row_values = [sheet.cell_value(row_idx, col) for col in range(min(3, sheet.ncols))]
                    # Look for customer name and code pairs
                    for val in row_values:
                        val_str = str(val).strip()
                        if val_str and len(val_str) > 2 and not is_header_keyword(val_str):
                            if '有限公司' in val_str or '公司' in val_str:
                                customers_from_customer_code_sheet[val_str] = f"code_sheet_row_{row_idx+1}"
            continue

        # Check if sheet name is B-* code
        if is_b_code_sheet(sheet_name):
            b_codes.append(sheet_name)
            continue

        # Extract customer from sheet name
        sheet_customer = extract_customer_from_sheet_name(sheet_name)
        if sheet_customer and not is_customer_part_number(sheet_customer):
            if sheet_customer not in customers_from_sheet_names:
                customers_from_sheet_names[sheet_customer] = []
            customers_from_sheet_names[sheet_customer].append(sheet_name)

        # Now scan rows for customer column
        # Find header row (look for '客户名称' or similar)
        header_row_idx = None
        customer_col_idx = None

        for row_idx in range(min(10, sheet.nrows)):
            for col_idx in range(sheet.ncols):
                cell_val = str(sheet.cell_value(row_idx, col_idx)).strip()
                if cell_val in ['客户名称', '客户简称', '客户']:
                    header_row_idx = row_idx
                    customer_col_idx = col_idx
                    break
            if header_row_idx is not None:
                break

        # If found customer column, extract values
        if customer_col_idx is not None:
            for row_idx in range(header_row_idx + 1, sheet.nrows):
                try:
                    cell_val = sheet.cell_value(row_idx, customer_col_idx)
                    customer_name = str(cell_val).strip()

                    # Filter out non-customers
                    if not customer_name:
                        continue
                    if is_header_keyword(customer_name):
                        continue
                    if is_customer_part_number(customer_name):
                        continue
                    if len(customer_name) < 2:
                        continue

                    # Valid customer name
                    if customer_name not in customers_from_column:
                        customers_from_column[customer_name] = []
                    customers_from_column[customer_name].append((sheet_name, row_idx + 1))

                except Exception:
                    continue

    return {
        'sheet_names': customers_from_sheet_names,
        'column': customers_from_column,
        'code_sheet': customers_from_customer_code_sheet,
        'b_codes': b_codes
    }

def get_db_customers() -> Set[str]:
    """Get all customer names from database (read-only)."""
    try:
        import os
        import psycopg2

        # Use local tunnel at 127.0.0.1:5432
        conn = psycopg2.connect(
            host=os.environ.get('ZEPHYR_DB_HOST', '127.0.0.1'),
            port=int(os.environ.get('ZEPHYR_DB_PORT', '5432')),
            database=os.environ.get('ZEPHYR_DB_NAME', 'stamping_system'),
            user=os.environ.get('ZEPHYR_DB_USER', 'postgres'),
            password=os.environ['ZEPHYR_DB_PASSWORD'],
        )

        cur = conn.cursor()

        # Read all customer names
        cur.execute("SELECT name FROM customers ORDER BY name")
        customers = {row[0] for row in cur.fetchall()}

        # Also get count
        cur.execute("SELECT COUNT(*) FROM customers")
        count = cur.fetchone()[0]

        cur.close()
        conn.close()

        print(f"[INFO] Database has {count} customers")
        return customers

    except Exception as e:
        print(f"[ERROR] Could not read database: {e}")
        return set()

def check_customer_api() -> Dict:
    """Check customer API pagination/filtering (read-only)."""
    try:
        import requests

        # Test API endpoint
        base_url = "http://localhost:8000"

        # Get total count
        resp1 = requests.get(f"{base_url}/api/customers?page=1&page_size=10", timeout=5)
        if resp1.status_code != 200:
            return {'error': f'API returned {resp1.status_code}'}

        data1 = resp1.json()
        total = data1.get('total', 0)

        # Get all customers with large page size
        resp2 = requests.get(f"{base_url}/api/customers?page=1&page_size=1000", timeout=10)
        if resp2.status_code != 200:
            return {'error': f'API returned {resp2.status_code}'}

        data2 = resp2.json()
        items = data2.get('items', [])

        return {
            'total': total,
            'returned': len(items),
            'matches': total == len(items)
        }

    except Exception as e:
        return {'error': str(e)}

def main():
    """Main audit entry point."""
    print("="*80)
    print("CUSTOMER SOURCE AUDIT - READ-ONLY")
    print("="*80)

    # Find Excel file
    excel_path = Path(__file__).parent / 'excel' / '五金模具及产品清单表.xls'
    if not excel_path.exists():
        print(f"[ERROR] Excel file not found: {excel_path}")
        return 1

    # Extract customers from Excel
    print("\n[1] EXTRACTING CUSTOMERS FROM EXCEL")
    print("-"*80)
    excel_data = audit_excel_customers(excel_path)

    sheet_name_customers = set(excel_data['sheet_names'].keys())
    column_customers = set(excel_data['column'].keys())
    code_sheet_customers = set(excel_data['code_sheet'].keys())

    # Combine all sources
    all_excel_customers = sheet_name_customers | column_customers | code_sheet_customers

    print(f"\nExcel customer sources:")
    print(f"  From sheet names: {len(sheet_name_customers)}")
    print(f"  From customer column: {len(column_customers)}")
    print(f"  From code sheet: {len(code_sheet_customers)}")
    print(f"  B-* codes (excluded): {len(excel_data['b_codes'])}")
    print(f"  Total unique customers: {len(all_excel_customers)}")

    # Read database
    print("\n[2] READING DATABASE CUSTOMERS")
    print("-"*80)
    db_customers = get_db_customers()

    # Compare
    print("\n[3] COMPARISON")
    print("-"*80)

    # Normalize for comparison
    excel_normalized = {normalize_customer_name(c): c for c in all_excel_customers}
    db_normalized = {normalize_customer_name(c): c for c in db_customers}

    # Find missing
    missing_in_db = set(excel_normalized.keys()) - set(db_normalized.keys())

    print(f"Excel unique (normalized): {len(excel_normalized)}")
    print(f"DB unique (normalized): {len(db_normalized)}")
    print(f"Missing in DB: {len(missing_in_db)}")

    # Report missing customers with evidence
    if missing_in_db:
        print("\n[4] MISSING CUSTOMERS (with evidence)")
        print("-"*80)

        for idx, norm_name in enumerate(sorted(missing_in_db), 1):
            original_name = excel_normalized[norm_name]
            print(f"\n{idx}. {original_name}")

            # Show sources
            sources = []
            if original_name in excel_data['sheet_names']:
                sheets = excel_data['sheet_names'][original_name]
                sources.append(f"  Sheet name: {sheets}")

            if original_name in excel_data['column']:
                locations = excel_data['column'][original_name][:3]  # Show first 3
                loc_str = ", ".join([f"{s}:{r}" for s, r in locations])
                if len(excel_data['column'][original_name]) > 3:
                    loc_str += f" ... (+{len(excel_data['column'][original_name])-3} more)"
                sources.append(f"  Column data: {loc_str}")

            if original_name in excel_data['code_sheet']:
                sources.append(f"  Code sheet: {excel_data['code_sheet'][original_name]}")

            for src in sources:
                print(src)

    # Check for specific customers mentioned
    print("\n[5] SPECIFIC CUSTOMER CHECKS")
    print("-"*80)

    # Check H4287
    h4287_in_excel = any('H4287' in c or 'h4287' in c.lower() for c in all_excel_customers)
    h4287_in_db = any('H4287' in c or 'h4287' in c.lower() for c in db_customers)
    print(f"H4287 in Excel: {h4287_in_excel}")
    print(f"H4287 in DB: {h4287_in_db}")

    # Check API pagination
    print("\n[6] API PAGINATION CHECK")
    print("-"*80)
    api_result = check_customer_api()
    if 'error' in api_result:
        print(f"API check failed: {api_result['error']}")
        print("(Server may not be running)")
    else:
        print(f"API total count: {api_result['total']}")
        print(f"API returned items: {api_result['returned']}")
        print(f"Matches: {api_result['matches']}")

        if api_result['total'] != len(db_customers):
            print(f"⚠ WARNING: API total ({api_result['total']}) != DB count ({len(db_customers)})")

    print("\n" + "="*80)
    print("AUDIT COMPLETE")
    print("="*80)

    return 0

if __name__ == "__main__":
    sys.exit(main())

