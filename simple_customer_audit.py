#!/usr/bin/env python3
"""
Simple customer source audit - Excel only
Shows all unique customers found in Excel with their sources
"""

import sys
import re
from pathlib import Path
from typing import Set, Dict, List
import xlrd

def normalize_customer_name(name: str) -> str:
    """Normalize customer name for comparison."""
    if not name:
        return ''
    name = str(name).strip()
    name = name.replace('有限公司', '').replace('有限', '')
    name = name.replace('（', '(').replace('）', ')')
    return name.strip()

def is_special_sheet(sheet_name: str) -> bool:
    """Check if sheet is special (metadata)."""
    return any(p in sheet_name for p in ['客户名称代号', '说明', '目录', '索引'])

def is_b_code_sheet(sheet_name: str) -> bool:
    """Check if sheet name is a B-* code."""
    return bool(re.match(r'^B-[\dA-Z]+', sheet_name, re.IGNORECASE))

def extract_customer_from_sheet_name(sheet_name: str) -> str:
    """Extract customer name from sheet name like '客户名(A)'."""
    match = re.match(r'^(.+?)\s*\([A-Z0-9\-]+\)\s*$', sheet_name)
    if match:
        return match.group(1).strip()
    return sheet_name.strip()

def is_customer_part_number(text: str) -> bool:
    """Check if text looks like a part number."""
    if not text:
        return False
    text = str(text).strip()
    part_patterns = [r'^[A-Z]{2,}-?\d', r'^\d{3,}', r'^[A-Z]\d+[A-Z]']
    return any(re.match(p, text) for p in part_patterns)

def is_header_keyword(text: str) -> bool:
    """Check if text is a header keyword."""
    keywords = ['客户', '产品', '编号', '模具', '料厚', '材料', '备注', '说明']
    return any(kw in str(text).lower() for kw in keywords)

def main():
    print("="*80)
    print("CUSTOMER SOURCE AUDIT - EXCEL ANALYSIS")
    print("="*80)

    excel_path = Path(__file__).parent / 'excel' / '五金模具及产品清单表.xls'
    if not excel_path.exists():
        print(f"[ERROR] Excel file not found: {excel_path}")
        return 1

    print(f"\n[INFO] Reading: {excel_path.name}")

    workbook = xlrd.open_workbook(str(excel_path))

    # Track customers
    sheet_name_customers = {}  # {customer: [sheet_names]}
    column_customers = {}  # {customer: [(sheet, row)]}
    code_sheet_customers = set()
    b_codes = []

    print(f"[INFO] Total sheets: {workbook.nsheets}")
    print("\n" + "="*80)
    print("PROCESSING SHEETS")
    print("="*80)

    for sheet_idx in range(workbook.nsheets):
        sheet = workbook.sheet_by_index(sheet_idx)
        sheet_name = sheet.name

        # Handle special sheets
        if is_special_sheet(sheet_name):
            if '客户名称代号' in sheet_name:
                print(f"\n[SPECIAL] {sheet_name} - Customer code mapping sheet")
                for row_idx in range(sheet.nrows):
                    for col in range(min(3, sheet.ncols)):
                        val = str(sheet.cell_value(row_idx, col)).strip()
                        if val and len(val) > 2 and not is_header_keyword(val):
                            if '公司' in val:
                                code_sheet_customers.add(val)
            continue

        # Handle B-* codes
        if is_b_code_sheet(sheet_name):
            b_codes.append(sheet_name)
            continue

        # Extract from sheet name
        sheet_customer = extract_customer_from_sheet_name(sheet_name)
        if sheet_customer and not is_customer_part_number(sheet_customer):
            if sheet_customer not in sheet_name_customers:
                sheet_name_customers[sheet_customer] = []
            sheet_name_customers[sheet_customer].append(sheet_name)

        # Find customer column
        customer_col_idx = None
        header_row_idx = None

        for row_idx in range(min(10, sheet.nrows)):
            for col_idx in range(sheet.ncols):
                cell = str(sheet.cell_value(row_idx, col_idx)).strip()
                if cell in ['客户名称', '客户简称', '客户']:
                    header_row_idx = row_idx
                    customer_col_idx = col_idx
                    break
            if customer_col_idx is not None:
                break

        # Extract from column
        if customer_col_idx is not None:
            for row_idx in range(header_row_idx + 1, sheet.nrows):
                try:
                    val = str(sheet.cell_value(row_idx, customer_col_idx)).strip()
                    if val and len(val) >= 2 and not is_header_keyword(val) and not is_customer_part_number(val):
                        if val not in column_customers:
                            column_customers[val] = []
                        column_customers[val].append((sheet_name, row_idx + 1))
                except:
                    pass

    # Combine all sources
    all_customers = set(sheet_name_customers.keys()) | set(column_customers.keys()) | code_sheet_customers

    print(f"\n{'='*80}")
    print("SUMMARY")
    print("="*80)
    print(f"From sheet names:        {len(sheet_name_customers)}")
    print(f"From customer columns:   {len(column_customers)}")
    print(f"From code sheet:         {len(code_sheet_customers)}")
    print(f"B-* codes (excluded):    {len(b_codes)}")
    print(f"Total unique customers:  {len(all_customers)}")

    # Normalize
    normalized = {normalize_customer_name(c): c for c in all_customers}
    print(f"After normalization:     {len(normalized)}")

    print(f"\n{'='*80}")
    print("ALL UNIQUE CUSTOMERS (sorted)")
    print("="*80)

    for idx, customer in enumerate(sorted(all_customers), 1):
        print(f"\n{idx}. {customer}")

        sources = []
        if customer in sheet_name_customers:
            sources.append(f"   └─ Sheet name: {len(sheet_name_customers[customer])} sheet(s)")

        if customer in column_customers:
            count = len(column_customers[customer])
            sources.append(f"   └─ Column data: {count} row(s)")

        if customer in code_sheet_customers:
            sources.append(f"   └─ Code sheet")

        for src in sources:
            print(src)

    # Check specific customers
    print(f"\n{'='*80}")
    print("SPECIFIC CHECKS")
    print("="*80)

    h4287_found = [c for c in all_customers if 'H4287' in c or 'h4287' in c.lower()]
    print(f"\nH4287 customer: {h4287_found if h4287_found else 'NOT FOUND'}")

    # Database comparison note
    print(f"\n{'='*80}")
    print("DATABASE COMPARISON")
    print("="*80)
    print("Database connection not available.")
    print(f"Excel found {len(all_customers)} unique customers.")
    print("User reports database has 101 customers.")
    print(f"Potential missing: {len(all_customers) - 101} = {len(all_customers) - 101} customers")

    print(f"\n{'='*80}")
    print("AUDIT COMPLETE")
    print("="*80)

    return 0

if __name__ == "__main__":
    sys.exit(main())
