# -*- coding: utf-8 -*-
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()

# Check prices table columns
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'prices'
    ORDER BY ordinal_position;
""")
print("=== prices table columns ===")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]} null={r[2]}")

# Check all three customers
print("\n=== 客户列表 ===")
cur.execute("SELECT id, name FROM tooling_customers ORDER BY id;")
for r in cur.fetchall():
    print(f"  id={r[0]} {r[1]}")

# Check parts for 武汉万向 (customer 55)
print("\n=== 所有零件 (customer 55) ===")
cur.execute("""
    SELECT pt.id, pt.part_number, pt.internal_name, pt.status, p.id as price_id
    FROM parts pt
    LEFT JOIN prices p ON p.part_id = pt.id AND p.customer_id=55
    WHERE pt.id IN (SELECT DISTINCT part_id FROM prices WHERE customer_id=55)
       OR pt.part_number LIKE 'A00125983%'
    ORDER BY pt.part_number;
""")
for r in cur.fetchall():
    print(f"  id={r[0]} part={r[1]} name={r[2]} status={r[3]} price_id={r[4]}")

# Check all sheets in all Excel files
import openpyxl, os
for base in [r"C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices"]:
    if os.path.isdir(base):
        for name in os.listdir(base):
            subpath = os.path.join(base, name)
            if os.path.isdir(subpath):
                for fname in os.listdir(subpath):
                    if fname.endswith('.xlsx'):
                        fpath = os.path.join(subpath, fname)
                        wb = openpyxl.load_workbook(fpath, data_only=True)
                        for shname in wb.sheetnames:
                            ws = wb[shname]
                            print(f"\n=== {fname} / {shname} ({ws.max_row}行 {ws.max_column}列) ===")
                            for i, row in enumerate(ws.iter_rows(values_only=True)):
                                if i >= 15: break
                                print(f"  {list(row)}")

conn.close()
