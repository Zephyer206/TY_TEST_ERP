import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='thehaoshi5DE',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# 1. 添加 treatment_items JSONB 字段
print("1. 添加 treatment_items 列...")
try:
    cur.execute("""
        ALTER TABLE quotes ADD COLUMN treatment_items JSONB;
    """)
    print("   OK: treatment_items 已添加")
except psycopg2.errors.DuplicateColumn:
    print("   SKIP: treatment_items 已存在")

# 2. 迁移旧 surface_fee -> treatment_items（单个工序）
print("2. 迁移 surface_fee 到 treatment_items...")
cur.execute("""
    UPDATE quotes
    SET treatment_items = jsonb_build_array(
        jsonb_build_object('name', '表面处理', 'fee', surface_fee)
    )
    WHERE surface_fee IS NOT NULL
      AND surface_fee > 0
      AND (treatment_items IS NULL OR treatment_items = 'null'::jsonb OR jsonb_array_length(treatment_items) = 0);
""")
rows_updated = cur.rowcount
print(f"   迁移了 {rows_updated} 条记录")

# 3. 添加 mold_discount_mode
print("3. 添加 mold_discount_mode 列...")
try:
    cur.execute("""
        ALTER TABLE quotes ADD COLUMN mold_discount_mode VARCHAR(32) DEFAULT 'direct';
    """)
    print("   OK: mold_discount_mode 已添加")
except psycopg2.errors.DuplicateColumn:
    print("   SKIP: mold_discount_mode 已存在")

# 4. 添加 mold_discount_rate
print("4. 添加 mold_discount_rate 列...")
try:
    cur.execute("""
        ALTER TABLE quotes ADD COLUMN mold_discount_rate NUMERIC(5, 4) DEFAULT 1.0;
    """)
    print("   OK: mold_discount_rate 已添加")
except psycopg2.errors.DuplicateColumn:
    print("   SKIP: mold_discount_rate 已存在")

conn.commit()

# 验证
print("\n验证表结构：")
cur.execute("""
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_name = 'quotes'
      AND column_name IN ('treatment_items', 'mold_discount_mode', 'mold_discount_rate')
    ORDER BY ordinal_position;
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}, default={r[2]}")

print("\n验证数据：")
cur.execute("""
    SELECT id, treatment_items, mold_discount_mode, mold_discount_rate
    FROM quotes
    WHERE treatment_items IS NOT NULL OR surface_fee > 0
    LIMIT 5;
""")
for r in cur.fetchall():
    print(f"  id={r[0]}, treatment_items={r[1]}, mode={r[2]}, rate={r[3]}")

cur.close()
conn.close()
print("\nMigration 完成！")
