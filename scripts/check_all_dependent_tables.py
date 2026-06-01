"""
全面诊断 TEST 零件的所有关联数据，找出所有有数据的依赖表
"""
import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='thehaoshi5DE',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# 有 FK 引用 parts.id 的所有表
dependent_tables = [
    'assignments',
    'production_logs',
    'die_parts',
    'packaging_logs',
    'shipping_logs',
    'qc_logs',
    'qc_inspection_logs',
    'pkg_packaging_logs',
    'pkg_shipping_logs',
    'oqc_reports',
    'pkg_error_logs',
    'quotes',
    'production_plans',
    'sample_inventory',
    'part_customer_alias',
    'spraying_recipes',
    'spraying_logs',
    'spraying_material_consumption',
    'dies',
    'bom_routings',
    'sample_tasks',
    'work_orders',
    'part_customer_aliases',
    'delivery_items',
    'remnant_inventory',
    'finished_inventory',
]

for part_id in [157, 158]:
    print(f'\n=== 检查零件 id={part_id} 的所有关联数据 ===')
    for tbl in dependent_tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE part_id = %s;", (part_id,))
            cnt = cur.fetchone()[0]
            if cnt > 0:
                print(f'  {tbl}: {cnt} 条')
        except Exception as e:
            print(f'  {tbl}: 错误 - {e}')

conn.close()
