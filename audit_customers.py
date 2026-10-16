#!/usr/bin/env python3
"""
Read-only customer audit script
Extracts all customer sources from Excel and compares with database
"""
import xlrd
import re
import json
from collections import defaultdict
import psycopg2
from pathlib import Path

# Customer sources tracking
customers_from_sheets = {}  # name -> [sheet_names]
customers_from_code_sheet = {}  # code -> full_name
customers_from_data_column = {}  # name -> [(sheet, row_count)]
customer_part_no_customers = {}  # name -> [(sheet, row, customer_part_no)]
b_code_sheets = []

SKIP_PATTERNS = ['目录', '五金模具进度', 'Sheet2']

def is_skip_sheet(name):
    for pattern in SKIP_PATTERNS:
        if pattern in name:
            return True
    return False

def extract_customer_from_sheet_name(name):
    """Extract customer name from sheet name"""
    name = name.strip()

    # Pattern 1: '浙江万宝机械有限公司(A)' -> '浙江万宝机械有限公司', 'A'
    match = re.match(r'^(.+?)\s*\(([A-Z0-9\-]+)\)\s*$', name)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # Pattern 2: 'A-J南京德马' -> '南京德马', 'A-J'
    match = re.match(r'^([A-Z]{1,2}-[A-Z0-9]+)(.+)$', name)
    if match:
        code = match.group(1).strip()
        customer = match.group(2).strip()
        if not any(x in customer for x in ['备用', '模具', '进度', '60T']):
            return customer, code

    # Pattern 3: Simple codes like 'ZF', 'IBI', 'ITT'
    if re.match(r'^[A-Z]{2,4}$', name):
        return name, name

    # Pattern 4: B-* patterns
    if re.match(r'^B-[A-Z]', name):
        return None, name

    return None, None

def audit_excel(excel_path):
    """Audit Excel file for all customer sources"""
    print('='*70)
    print('CUSTOMER AUDIT - EXCEL SOURCE')
    print('='*70)

    wb = xlrd.open_workbook(excel_path, formatting_info=False)

    # === STEP 1: Parse customer code sheet ===
    print('\n[1] Customer Code Sheet')
    code_sheet = None
    for sheet_idx in range(wb.nsheets):
        sheet = wb.sheet_by_index(sheet_idx)
        if '客户名称代号' in sheet.name:
            code_sheet = sheet
            break

    if code_sheet:
        print(f'    Found: {code_sheet.name}')
        header_row = 1
        for row_idx in range(header_row + 1, code_sheet.nrows):
            try:
                code = str(code_sheet.cell_value(row_idx, 1)).strip()
                name = str(code_sheet.cell_value(row_idx, 2)).strip()

                if code and name and code not in ['', '代号', '编号']:
                    customers_from_code_sheet[code] = name
            except:
                pass

        print(f'    Extracted: {len(customers_from_code_sheet)} customers')

    # === STEP 2: Parse all sheet names ===
    print('\n[2] Sheet Names')
    for sheet_idx in range(wb.nsheets):
        sheet = wb.sheet_by_index(sheet_idx)
        sheet_name = sheet.name.strip()

        if is_skip_sheet(sheet_name) or '客户名称代号' in sheet_name:
            continue

        customer, code = extract_customer_from_sheet_name(sheet_name)

        if customer:
            if customer not in customers_from_sheets:
                customers_from_sheets[customer] = []
            customers_from_sheets[customer].append(sheet_name)

        if code and code.startswith('B-'):
            b_code_sheets.append(sheet_name)

    print(f'    Customers from sheet names: {len(customers_from_sheets)}')
    print(f'    B-* code sheets: {len(b_code_sheets)}')

    # === STEP 3: Parse customer columns in data sheets ===
    print('\n[3] Customer Name Columns')
    processed_sheets = 0

    for sheet_idx in range(wb.nsheets):
        sheet = wb.sheet_by_index(sheet_idx)
        sheet_name = sheet.name.strip()

        if is_skip_sheet(sheet_name) or '客户名称代号' in sheet_name:
            continue

        header_row = None
        customer_col = None
        customer_part_col = None

        for row_idx in range(min(10, sheet.nrows)):
            row_vals = [str(sheet.cell_value(row_idx, c)).strip()
                       for c in range(min(sheet.ncols, 20))]

            for col_idx, val in enumerate(row_vals):
                if '客户名称' in val or '客户简称' in val:
                    header_row = row_idx
                    customer_col = col_idx
                if '原图产品编号' in val or '客户产品编号' in val:
                    customer_part_col = col_idx

            if header_row is not None:
                break

        if header_row is not None and customer_col is not None:
            processed_sheets += 1
            sheet_customers = set()

            for row_idx in range(header_row + 1, sheet.nrows):
                try:
                    customer_val = str(sheet.cell_value(row_idx, customer_col)).strip()

                    if customer_val and len(customer_val) > 0:
                        if not any(x in customer_val for x in
                                 ['合计', '小计', '序号', '编号', '客户', '____']):
                            sheet_customers.add(customer_val)

                            if customer_part_col is not None:
                                part_no = str(sheet.cell_value(row_idx,
                                            customer_part_col)).strip()
                                if part_no:
                                    if customer_val not in customer_part_no_customers:
                                        customer_part_no_customers[customer_val] = []
                                    customer_part_no_customers[customer_val].append(
                                        (sheet_name, row_idx + 1, part_no))
                except:
                    pass

            for cust in sheet_customers:
                if cust not in customers_from_data_column:
                    customers_from_data_column[cust] = []
                customers_from_data_column[cust].append(
                    (sheet_name, len(sheet_customers)))

    print(f'    Processed sheets: {processed_sheets}')
    print(f'    Unique customers: {len(customers_from_data_column)}')

    # === STEP 4: Aggregate ===
    all_customers = set()
    all_customers.update(customers_from_code_sheet.values())
    all_customers.update(customers_from_sheets.keys())
    all_customers.update(customers_from_data_column.keys())

    print('\n' + '='*70)
    print('EXCEL SUMMARY')
    print('='*70)
    print(f'Total unique customers: {len(all_customers)}')
    print(f'  - Code sheet: {len(customers_from_code_sheet)}')
    print(f'  - Sheet names: {len(customers_from_sheets)}')
    print(f'  - Data columns: {len(customers_from_data_column)}')

    return all_customers

def audit_database():
    """Query database for current customers (read-only)"""
    print('\n' + '='*70)
    print('CUSTOMER AUDIT - DATABASE')
    print('='*70)

    try:
        # Import settings from backend
        import sys
        from pathlib import Path
        backend_path = Path(__file__).parent / 'backend'
        sys.path.insert(0, str(backend_path))

        from app.core.config import settings
        from urllib.parse import urlparse

        db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        parsed = urlparse(db_url)

        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password
        )

        print(f'Connected to: {parsed.hostname}:{parsed.port}/{parsed.path.lstrip("/")}')

        cur = conn.cursor()

        # Get all customers
        cur.execute("""
            SELECT id, name, short_name, customer_code, is_active
            FROM customers
            ORDER BY id
        """)

        db_customers = cur.fetchall()

        print(f'\nTotal customers in database: {len(db_customers)}')
        print(f'Active customers: {sum(1 for c in db_customers if c[4])}')

        # Show sample
        print('\nFirst 10 customers:')
        for i, (cid, name, short_name, code, active) in enumerate(db_customers[:10], 1):
            status = 'Active' if active else 'Inactive'
            print(f'  {i:2}. [{cid:3}] {name[:30]:30} code={code} ({status})')

        cur.close()
        conn.close()

        return {c[1] for c in db_customers}  # Set of names

    except Exception as e:
        print(f'\n[ERROR] Database connection failed: {e}')
        print('[INFO] Please ensure SSH tunnel is running:')
        print('       ssh -L 5432:localhost:5432 user@server')
        return set()

def main():
    excel_path = Path('excel/五金模具及产品清单表.xls')

    # Audit Excel
    excel_customers = audit_excel(excel_path)

    # Audit Database
    db_customers = audit_database()

    if db_customers:
        # Compare
        print('\n' + '='*70)
        print('COMPARISON')
        print('='*70)

        in_excel_not_db = excel_customers - db_customers
        in_db_not_excel = db_customers - excel_customers

        print(f'\nIn Excel but NOT in DB: {len(in_excel_not_db)}')
        if in_excel_not_db:
            for i, cust in enumerate(sorted(in_excel_not_db)[:20], 1):
                print(f'  {i:2}. {cust}')

        print(f'\nIn DB but NOT in Excel: {len(in_db_not_excel)}')
        if in_db_not_excel:
            for i, cust in enumerate(sorted(in_db_not_excel)[:20], 1):
                print(f'  {i:2}. {cust}')

    # Export results
    result = {
        'excel_total': len(excel_customers),
        'database_total': len(db_customers),
        'excel_customers': sorted(list(excel_customers)),
        'database_customers': sorted(list(db_customers)),
        'missing_from_db': sorted(list(excel_customers - db_customers)),
        'extra_in_db': sorted(list(db_customers - excel_customers))
    }

    with open('customer_audit_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'\n[INFO] Results exported to customer_audit_result.json')

if __name__ == '__main__':
    main()
