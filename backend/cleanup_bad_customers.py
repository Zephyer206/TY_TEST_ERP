"""
清理错误导入的客户数据

问题分析：
1. "60T 连续模" 被作为客户导入 - 这应该是Excel表格的分类标签
2. 所有客户名称显示乱码 - 字符编码问题

解决方案：
1. 删除明显的表头/分类标签记录
2. 建议重新导入客户数据，确保：
   - 跳过表头行
   - 使用正确的字符编码（UTF-8）
   - 识别并跳过分类标签行
"""

import asyncio
import asyncpg

DATABASE_URL = 'postgresql://postgres:w981122@124.222.29.229:5432/zephyr_erp_test'


async def analyze_customers():
    """分析客户数据中的问题"""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        print("=" * 60)
        print("客户数据分析报告")
        print("=" * 60)

        # 1. 总客户数
        total = await conn.fetchval("SELECT COUNT(*) FROM customers")
        print(f"\n📊 总客户数: {total}")

        # 2. 查找可疑的客户记录
        print("\n🔍 可疑的客户记录（可能是表头或分类标签）:")
        suspicious = await conn.fetch("""
            SELECT id, name, sheet_key, created_at
            FROM customers
            WHERE name LIKE '%连续模%'
               OR name LIKE '%T 模%'
               OR name LIKE '%吨%'
               OR name LIKE '%模具%'
               OR sheet_key ~ '^[0-9]+T$'
            ORDER BY id
            LIMIT 10
        """)

        if suspicious:
            for row in suspicious:
                print(f"  ID={row['id']:3d} | name={row['name']!r:40s} | sheet_key={row['sheet_key']}")
        else:
            print("  ✅ 未发现明显的表头/分类标签记录")

        # 3. 检查最近创建的客户
        print(f"\n📅 最近创建的10个客户:")
        recent = await conn.fetch("""
            SELECT id, name, sheet_key, created_at
            FROM customers
            ORDER BY created_at DESC
            LIMIT 10
        """)

        for row in recent:
            created_at = row['created_at'].strftime('%Y-%m-%d %H:%M')
            print(f"  ID={row['id']:3d} | {created_at} | {row['name']!r}")

        # 4. 检查sheet_key分布
        print(f"\n🔑 Sheet Key 分布:")
        sheet_keys = await conn.fetch("""
            SELECT sheet_key, COUNT(*) as count
            FROM customers
            WHERE sheet_key IS NOT NULL
            GROUP BY sheet_key
            ORDER BY count DESC
            LIMIT 10
        """)

        for row in sheet_keys:
            print(f"  {row['sheet_key']:10s} : {row['count']} 个客户")

    finally:
        await conn.close()


async def cleanup_bad_customers(dry_run=True):
    """清理错误的客户记录

    Args:
        dry_run: True=仅显示将要删除的记录，False=实际删除
    """
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        print("\n" + "=" * 60)
        if dry_run:
            print("🧪 模拟删除模式（不会实际删除）")
        else:
            print("⚠️  实际删除模式")
        print("=" * 60)

        # 查找要删除的记录
        to_delete = await conn.fetch("""
            SELECT id, name, sheet_key
            FROM customers
            WHERE name LIKE '%连续模%'
               OR name LIKE '%T 模%'
               OR name LIKE '%吨%模%'
               OR sheet_key ~ '^[0-9]+T$'
            ORDER BY id
        """)

        if not to_delete:
            print("✅ 没有找到需要删除的记录")
            return

        print(f"\n找到 {len(to_delete)} 条需要删除的记录:")
        for row in to_delete:
            print(f"  ID={row['id']:3d} | {row['name']!r:40s} | sheet_key={row['sheet_key']}")

        if not dry_run:
            # 实际删除
            deleted = await conn.execute("""
                DELETE FROM customers
                WHERE name LIKE '%连续模%'
                   OR name LIKE '%T 模%'
                   OR name LIKE '%吨%模%'
                   OR sheet_key ~ '^[0-9]+T$'
            """)
            print(f"\n✅ 已删除 {len(to_delete)} 条记录")
        else:
            print(f"\n💡 要实际删除这些记录，请运行: python cleanup_bad_customers.py --delete")

    finally:
        await conn.close()


async def main():
    """主函数"""
    import sys

    # 1. 分析数据
    await analyze_customers()

    # 2. 清理数据
    dry_run = '--delete' not in sys.argv
    await cleanup_bad_customers(dry_run=dry_run)

    print("\n" + "=" * 60)
    print("建议:")
    print("=" * 60)
    print("1. 检查原始Excel文件，确认数据格式")
    print("2. 重新导入时：")
    print("   - 跳过表头行（通常是第1行）")
    print("   - 识别并跳过分类标签行（如'60T 连续模'）")
    print("   - 使用UTF-8编码读取")
    print("3. 修复字符编码问题")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
