import asyncio
import sys
sys.path.insert(0, './backend')

from sqlalchemy import text
from app.database import get_db_context

async def main():
    async with get_db_context() as db:
        print("=" * 80)
        print("TWP 数据审计报告 - Phase 1 (只读)")
        print("=" * 80)
        print()
        
        # 1. Parts 表 TWP 统计
        print("【1】Parts 表 TWP 字段统计")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                COUNT(*) as total_parts,
                COUNT(thickness) as has_thickness,
                COUNT(width) as has_width,
                COUNT(pitch) as has_pitch,
                COUNT(spec_twph) as has_spec_twph,
                COUNT(CASE WHEN thickness IS NOT NULL AND width IS NOT NULL AND pitch IS NOT NULL THEN 1 END) as has_complete_twp
            FROM parts
            WHERE is_deleted = FALSE
        """))
        stats = result.fetchone()
        total = stats[0]
        print(f"  总零件数: {total}")
        print(f"  有 thickness: {stats[1]} ({stats[1]*100/total:.1f}%)")
        print(f"  有 width: {stats[2]} ({stats[2]*100/total:.1f}%)")
        print(f"  有 pitch: {stats[3]} ({stats[3]*100/total:.1f}%)")
        print(f"  有 spec_twph: {stats[4]} ({stats[4]*100/total:.1f}%)")
        print(f"  有完整 TWP: {stats[5]} ({stats[5]*100/total:.1f}%)")
        print()
        
        # 2. Part_Tooling_Specs 表统计
        print("【2】Part_Tooling_Specs 表统计")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                COUNT(*) as total_specs,
                COUNT(DISTINCT part_id) as distinct_parts,
                COUNT(DISTINCT tooling_id) as distinct_toolings,
                COUNT(CASE WHEN is_primary THEN 1 END) as primary_specs,
                COUNT(thickness) as has_thickness,
                COUNT(width) as has_width,
                COUNT(pitch) as has_pitch,
                COUNT(spec_twph) as has_spec_twph,
                COUNT(source_sheet) as has_source_sheet
            FROM part_tooling_specs
        """))
        stats = result.fetchone()
        total_specs = stats[0]
        
        if total_specs > 0:
            print(f"  总规格记录数: {total_specs}")
            print(f"  涉及零件数: {stats[1]}")
            print(f"  涉及工装数: {stats[2]}")
            print(f"  主规格数: {stats[3]}")
            print(f"  有 thickness: {stats[4]} ({stats[4]*100/total_specs:.1f}%)")
            print(f"  有 width: {stats[5]} ({stats[5]*100/total_specs:.1f}%)")
            print(f"  有 pitch: {stats[6]} ({stats[6]*100/total_specs:.1f}%)")
            print(f"  有 spec_twph: {stats[7]} ({stats[7]*100/total_specs:.1f}%)")
            print(f"  有 source_sheet: {stats[8]} ({stats[8]*100/total_specs:.1f}%)")
        else:
            print("  表为空")
        print()
        
        # 3. 数据一致性检查
        print("【3】数据一致性检查")
        print("-" * 80)
        
        # 3.1 is_primary 约束检查
        result = await db.execute(text("""
            SELECT part_id, tooling_id, COUNT(*) as cnt
            FROM part_tooling_specs
            WHERE is_primary = TRUE
            GROUP BY part_id, tooling_id
            HAVING COUNT(*) > 1
        """))
        rows = result.fetchall()
        if rows:
            print(f"  错误: {len(rows)} 个组合有多个 is_primary")
        else:
            print("  OK: is_primary 约束正确")
        
        # 3.2 零件关联多工装
        result = await db.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT part_id
                FROM part_tooling_specs
                GROUP BY part_id
                HAVING COUNT(DISTINCT tooling_id) > 1
            ) sub
        """))
        count = result.scalar()
        print(f"  信息: {count} 个零件关联多个工装")
        
        # 3.3 parts 有 TWP 但无 specs
        result = await db.execute(text("""
            SELECT COUNT(*) FROM parts p
            LEFT JOIN part_tooling_specs pts ON pts.part_id = p.id
            WHERE p.is_deleted = FALSE
              AND (p.thickness IS NOT NULL OR p.width IS NOT NULL OR p.pitch IS NOT NULL)
              AND pts.id IS NULL
        """))
        count = result.scalar()
        if count > 0:
            print(f"  警告: {count} 个零件有 TWP 但无 part_tooling_specs")
        else:
            print(f"  OK: 所有有 TWP 的零件都有 specs")
        
        print()
        
        # 4. 采样数据
        print("【4】Part_Tooling_Specs 采样 (最新5条)")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                pts.id, pts.part_id, pts.tooling_id,
                pts.thickness, pts.width, pts.pitch,
                pts.is_primary, pts.source_sheet,
                p.part_number
            FROM part_tooling_specs pts
            LEFT JOIN parts p ON p.id = pts.part_id
            ORDER BY pts.id DESC
            LIMIT 5
        """))
        
        for row in result:
            print(f"  ID={row[0]}, Part={row[1]}({row[8]}), Tooling={row[2]}")
            print(f"    T={row[3]}, W={row[4]}, P={row[5]}, Primary={row[6]}")
        print()
        
        print("=" * 80)
        print("审计完成")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
