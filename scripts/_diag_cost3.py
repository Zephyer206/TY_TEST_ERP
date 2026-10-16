# -*- coding: utf-8 -*-
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', port='5432')
cur = conn.cursor()

# Check parts table dimensions for these parts
cur.execute("""
    SELECT p.part_number, p.thickness, p.width, p.press_stroke,
           p.material_name, p.material_utilization
    FROM parts p
    WHERE p.part_number IN ('3502114XKV86A','3502414AKY00A','3502314AKY00A',
                              '3502637XGW04A','A00125979-5')
    ORDER BY p.part_number;
""")
print("=== Parts table dimensions ===")
for r in cur.fetchall():
    print(f"  {r}")

# Also check how cost is calculated in quotes
cur.execute("""
    SELECT q.part_id, q.unit_price, q.stamping_fee, q.surface_fee,
           q.treatment_fee, q.profit_margin, q.final_price_override,
           pt.part_number
    FROM quotes q JOIN parts pt ON pt.id=q.part_id
    WHERE pt.part_number IN ('3502114XKV86A','3502637XGW04A')
    LIMIT 3;
""")
print("\n=== Quote calculations ===")
for r in cur.fetchall():
    print(f"  {r}")

# And check the actual price_years data
cur.execute("""
    SELECT py.price_id, py.year, py.unit_price, py.annual_sales,
           pt.part_number
    FROM price_years py
    JOIN prices p ON p.id = py.price_id
    JOIN parts pt ON pt.id = p.part_id
    WHERE p.customer_id = 55
    ORDER BY pt.part_number, py.year;
""")
print("\n=== price_years data ===")
for r in cur.fetchall():
    print(f"  {r}")

conn.close()
