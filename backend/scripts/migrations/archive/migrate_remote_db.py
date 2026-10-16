"""Migrate remote PostgreSQL database to three-level structure."""

import asyncio
import asyncpg

async def migrate():
    conn = await asyncpg.connect(
        host='124.222.29.229',
        port=5432,
        user='postgres',
        password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")',
        database='stamping_system'
    )

    try:
        print('连接到远程数据库成功')

        # 1. 检查当前表结构
        print('\n1. 检查当前表结构...')
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'part_name_dict'
            ORDER BY ordinal_position
        """)
        print('当前字段:')
        for col in columns:
            print(f"  {col['column_name']}: {col['data_type']} {'NULL' if col['is_nullable']=='YES' else 'NOT NULL'}")

        # 2. 检查是否已有新字段
        col_names = [col['column_name'] for col in columns]
        has_primary = 'primary_category' in col_names
        has_secondary = 'secondary_category' in col_names
        has_customer = 'customer_part_name' in col_names
        has_remark = 'remark' in col_names

        if has_primary and has_secondary and has_customer and has_remark:
            print('\n✓ 新字段已存在，检查数据...')
            data = await conn.fetch('SELECT id, primary_category, secondary_category, customer_part_name FROM part_name_dict LIMIT 3')
            for row in data:
                print(f"  ID={row['id']}, primary={row['primary_category']}, secondary={row['secondary_category']}, customer={row['customer_part_name']}")
            return

        # 3. 添加新字段
        print('\n2. 添加新字段...')
        if not has_primary:
            await conn.execute('ALTER TABLE part_name_dict ADD COLUMN primary_category VARCHAR(100)')
            print('  ✓ primary_category')
        if not has_secondary:
            await conn.execute('ALTER TABLE part_name_dict ADD COLUMN secondary_category VARCHAR(100)')
            print('  ✓ secondary_category')
        if not has_customer:
            await conn.execute('ALTER TABLE part_name_dict ADD COLUMN customer_part_name VARCHAR(200)')
            print('  ✓ customer_part_name')
        if not has_remark:
            await conn.execute('ALTER TABLE part_name_dict ADD COLUMN remark TEXT')
            print('  ✓ remark')

        # 4. 迁移数据
        print('\n3. 迁移现有数据...')
        rows = await conn.fetch('SELECT id, name, category, sub_category FROM part_name_dict')
        print(f'  共 {len(rows)} 条记录')

        for row in rows:
            name = row['name'] or ''
            category = row['category'] or ''
            sub_category = row['sub_category'] or ''

            # 提取一级分类（category中的主类型）
            primary = category.replace('类', '').replace('型', '') if category else name

            # 二级分类：原category
            secondary = category.replace('类', '').replace('型', '') if category else None

            # 客户零件名称：原name（如果与primary不同）
            customer = name if name != primary else None

            await conn.execute('''
                UPDATE part_name_dict
                SET primary_category = $1,
                    secondary_category = $2,
                    customer_part_name = $3
                WHERE id = $4
            ''', primary, secondary, customer, row['id'])
            print(f"  ID={row['id']}: {primary} | {secondary} | {customer}")

        # 5. 设置primary_category为NOT NULL
        print('\n4. 设置约束...')
        await conn.execute('ALTER TABLE part_name_dict ALTER COLUMN primary_category SET NOT NULL')
        print('  ✓ primary_category NOT NULL')

        # 6. 创建复合唯一索引
        print('\n5. 创建索引...')
        try:
            await conn.execute('''
                CREATE UNIQUE INDEX idx_part_name_unique
                ON part_name_dict(primary_category, secondary_category, customer_part_name)
            ''')
            print('  ✓ 复合唯一索引')
        except Exception as e:
            print(f'  索引已存在或创建失败: {e}')

        print('\n✅ 迁移完成！')

    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(migrate())
