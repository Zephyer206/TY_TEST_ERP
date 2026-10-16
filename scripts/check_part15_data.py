# 精确模拟 get_part_pricing_summary 的 part['pricing_mode'] 设置逻辑
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\Cloud-Stamping")
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": __import__("os").environ.get("ZEPHYR_DB_PASSWORD", ""),
    "host": "localhost",
    "port": "5432"
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)
part_id = 182

# 1. get_part_by_id
cur.execute("SELECT * FROM parts WHERE id = %s;", (part_id,))
part = dict(cur.fetchone())

# 2. get_latest_quote_by_part
cur.execute("""
    SELECT q.*, p.part_number, p.internal_name, p.material_name
    FROM quotes q
    JOIN parts p ON q.part_id = p.id
    WHERE q.part_id = %s AND q.is_deleted = FALSE
    ORDER BY q.created_at DESC LIMIT 1;
""", (part_id,))
quote = dict(cur.fetchone())
conn.close()

# 3. 模拟 get_part_pricing_summary 的 pricing_mode 转换逻辑
_pm = quote.get('pricing_mode')
print(f"quotes.pricing_mode = '{_pm}'")
converted = 'Associated' if _pm == 'reference' else ('Independent' if _pm == 'independent' else _pm)
print(f"part['pricing_mode'] = '{converted}'")

# 4. 模拟 renderDrawerContent 的分支逻辑
mode = converted
print()
print(f"=== renderDrawerContent 分支判断 ===")
print(f"mode = '{mode}'")
print(f"!mode = {not mode}")
print(f"mode !== 'Associated' && mode !== 'Independent' => {mode not in ['Associated', 'Independent']}")
print(f"mode === 'Independent' => {mode == 'Independent'}")

# 5. 关键判断
print()
print(f"=== 结论 ===")
if not mode or mode not in ['Associated', 'Independent']:
    print(f"→ 进入'模式未指定'分支，显示 buildModeSelector")
else:
    print(f"→ 进入对应模式分支")
    if mode == 'Independent':
        print(f"→ 显示 buildWhiteboxPanel（核算明细）")
