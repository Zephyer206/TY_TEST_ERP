#!/usr/bin/env python3
"""
Sync customer codes from Excel to database
"""

import sys
import os
from pathlib import Path
import re

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import xlrd
import psycopg2
from urllib.parse import urlparse


def get_db_config():
    """Get database config."""
    from app.core.config import settings
    db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    parsed = urlparse(db_url)

    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path.lstrip('/'),
        'user': parsed.username,
        'password': parsed.password
    }


def normalize_customer_name(name):
    """Normalize customer name for matching."""
    if not name:
        return ''
    normalized = name.strip().lower()
    normalized = re.sub(r'有限公司|股份有限公司|（.+?）|\(.+?\)', '', normalized)
    return normalized.strip()


def main():
    """Main entry point."""
    print("Syncing customer codes from Excel...")

    # Read customer codes from Excel
    excel_path = 'excel/五金模具及产品清单表.xls'
    if not os.path.exists(excel_path):
        print(f"ERROR: Excel file not found: {excel_path}")
        return 1

    wb = xlrd.open_workbook(excel_path)

    # Find customer code sheet
    sheet = None
    for sheet_name in wb.sheet_names():
        if '客户' in sheet_name and '代号' in sheet_name:
            sheet = wb.sheet_by_name(sheet_name)
            print(f"  Found sheet: {sheet_name}")
            break

    if not sheet:
        print("ERROR: Could not find customer code sheet")
        return 1

    # Parse customer codes - format: 序号, 本厂代号, 客户名称
    customer_codes = {}
    for row_idx in range(2, sheet.nrows):  # Skip header rows
        row = sheet.row_values(row_idx)
        if len(row) >= 3 and row[1] and row[2]:
            code = str(row[1]).strip()
            name = str(row[2]).strip()
            if code and name:
                customer_codes[name] = code

    print(f"  Loaded {len(customer_codes)} customer codes from Excel")

    # Build normalized mapping
    normalized_codes = {}
    for name, code in customer_codes.items():
        normalized = normalize_customer_name(name)
        if normalized not in normalized_codes:
            normalized_codes[normalized] = code

    # Connect to database
    db_config = get_db_config()
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()

    # Get all customers
    cur.execute('SELECT id, name, customer_code FROM customers ORDER BY id')
    db_customers = cur.fetchall()

    print(f"  Processing {len(db_customers)} database customers...")

    used_codes = set()
    updated = 0
    not_found = []

    for cust_id, cust_name, existing_code in db_customers:
        code = None

        # Try exact match
        if cust_name in customer_codes:
            code = customer_codes[cust_name]
        else:
            # Try normalized match
            normalized = normalize_customer_name(cust_name)
            if normalized in normalized_codes:
                code = normalized_codes[normalized]

        if code and code not in used_codes:
            cur.execute('UPDATE customers SET customer_code = %s WHERE id = %s',
                       (code, cust_id))
            used_codes.add(code)
            updated += 1
        else:
            not_found.append((cust_id, cust_name))

    conn.commit()

    print(f"\nResults:")
    print(f"  Updated: {updated} customers")
    print(f"  Not matched: {len(not_found)} customers")

    # Verify
    cur.execute('SELECT COUNT(*) FROM customers WHERE customer_code IS NOT NULL')
    total_with_codes = cur.fetchone()[0]
    print(f"  Total with codes: {total_with_codes}")

    cur.close()
    conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
