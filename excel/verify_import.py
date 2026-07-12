#!/usr/bin/env python3
"""
验证导入数据的质量和完整性
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from sqlalchemy import text
from app.database import engine


async def verify_data():
    """验证导入的数据"""
    async with engine.begin() as conn:
        print("=" * 80)
        print("数据导入验证报告")
        print("=" * 80)

        # 1. 材料统计
        result = await conn.execute(text("SELECT COUNT(*) FROM material_dict"))
        material_count = result.fetchone()[0]
        print(f"\n1. 材料字典: {material_count} 种")

        # 2. 客户统计
        result = await conn.execute(text("SELECT COUNT(*) FROM customers"))
        customer_count = result.fetchone()[0]
        print(f"\n2. 客户数量: {customer_count} 个")

        # 显示前5个客户
        result = await conn.execute(text("""
            SELECT id, name, sheet_key
            FROM customers
            ORDER BY id
            LIMIT 5
        """))
        print("   前5个客户:")
        for row in result:
            print(f"     - [{row[0]}] {row[1]} ({row[2]})")

        # 3. 模具统计
        result = await conn.execute(text("SELECT COUNT(*) FROM tooling"))
        tooling_count = result.fetchone()[0]
        print(f"\n3. 模具记录: {tooling_count} 条")

        # 左右件统计
        result = await conn.execute(text("""
            SELECT COUNT(*)
            FROM tooling
            WHERE is_multi_product = TRUE
        """))
        multi_count = result.fetchone()[0]
        print(f"   - 左右件模具: {multi_count} 组")

        # 模具类型分布
        result = await conn.execute(text("""
            SELECT mold_type, COUNT(*)
            FROM tooling
            WHERE mold_type IS NOT NULL
            GROUP BY mold_type
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """))
        print("   - 模具类型分布（前5）:")
        for row in result:
            print(f"     {row[0]}: {row[1]} 个")

        # 4. 零件统计
        result = await conn.execute(text("SELECT COUNT(*) FROM parts"))
        parts_count = result.fetchone()[0]
        print(f"\n4. 零件记录: {parts_count} 条")

        # 左右件零件统计
        result = await conn.execute(text("""
            SELECT part_position, COUNT(*)
            FROM parts
            WHERE part_position IS NOT NULL
            GROUP BY part_position
        """))
        print("   - 左右件分布:")
        for row in result:
            print(f"     {row[0]}: {row[1]} 个")

        # 5. 材料匹配率
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(material_id) as matched,
                COUNT(*) - COUNT(material_id) as unmatched
            FROM parts
        """))
        row = result.fetchone()
        match_rate = (row[1] / row[0] * 100) if row[0] > 0 else 0
        print(f"\n5. 材料匹配:")
        print(f"   - 总零件数: {row[0]}")
        print(f"   - 已匹配: {row[1]} ({match_rate:.1f}%)")
        print(f"   - 未匹配: {row[2]}")

        # 显示未匹配的材料
        if row[2] > 0:
            result = await conn.execute(text("""
                SELECT DISTINCT t.material
                FROM tooling t
                LEFT JOIN material_dict m ON t.material_id = m.id
                WHERE t.material IS NOT NULL
                  AND t.material_id IS NULL
                LIMIT 10
            """))
            print("   - 未匹配的材料（前10）:")
            for r in result:
                print(f"     {r[0]}")

        # 6. TWP解析统计
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(thickness) as has_thickness,
                COUNT(width) as has_width,
                COUNT(pitch) as has_pitch
            FROM parts
        """))
        row = result.fetchone()
        print(f"\n6. TWP解析:")
        print(f"   - 总零件: {row[0]}")
        print(f"   - 有厚度: {row[1]} ({row[1]/row[0]*100:.1f}%)")
        print(f"   - 有宽度: {row[2]} ({row[2]/row[0]*100:.1f}%)")
        print(f"   - 有节距: {row[3]} ({row[3]/row[0]*100:.1f}%)")

        # 7. 数据完整性检查
        print(f"\n7. 数据完整性:")

        # 检查零件编号重复
        result = await conn.execute(text("""
            SELECT part_number, COUNT(*)
            FROM parts
            WHERE part_number IS NOT NULL
            GROUP BY part_number
            HAVING COUNT(*) > 1
            LIMIT 5
        """))
        dup_parts = list(result)
        if dup_parts:
            print(f"   ⚠ 发现 {len(dup_parts)} 个重复的零件编号（前5）:")
            for row in dup_parts:
                print(f"     {row[0]}: {row[1]} 次")
        else:
            print("   ✓ 无重复零件编号")

        # 检查模具号重复
        result = await conn.execute(text("""
            SELECT tooling_no, COUNT(*)
            FROM tooling
            WHERE tooling_no IS NOT NULL
            GROUP BY tooling_no
            HAVING COUNT(*) > 1
            LIMIT 5
        """))
        dup_tooling = list(result)
        if dup_tooling:
            print(f"   ⚠ 发现 {len(dup_tooling)} 个重复的模具号（前5）:")
            for row in dup_tooling:
                print(f"     {row[0]}: {row[1]} 次")
        else:
            print("   ✓ 无重复模具号")

        # 8. 示例数据
        print(f"\n8. 示例数据:")
        result = await conn.execute(text("""
            SELECT
                c.name as customer,
                p.part_number,
                p.internal_name,
                p.spec_twph,
                p.part_position,
                t.mold_type,
                t.is_multi_product
            FROM parts p
            JOIN customers c ON p.customer_id = c.id
            JOIN tooling t ON p.tooling_id = t.id
            WHERE t.is_multi_product = TRUE
            LIMIT 3
        """))
        print("   左右件示例:")
        for row in result:
            pos = f"({row[4]})" if row[4] else ""
            print(f"     - {row[0]}: {row[1]} {pos} - {row[2]}")

        print("\n" + "=" * 80)
        print("验证完成")
        print("=" * 80)


if __name__ == '__main__':
    asyncio.run(verify_data())
