import asyncio
import sys
sys.path.insert(0, './backend')

from sqlalchemy import text
from app.database import get_db_context

async def main():
    async with get_db_context() as db:
        print("=" * 80)
        print("TWP 数据详细审计报告 - Phase 1")
        print("=" * 80)
        print()
        
        # 1. 发现的问题：24个零件有 TWP 但无 part_tooling_specs
        print("【问题1】24个零件 parts 表有 TWP 但无 part_tooling_specs")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                p.id,
                p.part_number,
                p.internal_name,
                p.thickness,
                p.width,
                p.pitch,
                p.spec_twph
            FROM parts p
            LEFT JOIN part_tooling_specs pts ON pts.part_id = p.id
            WHERE p.is_deleted = FALSE
              AND (p.thickness IS NOT NULL OR p.width IS NOT NULL OR p.pitch IS NOT NULL)
              AND pts.id IS NULL
            ORDER BY p.id
        """))
        
        orphan_parts = result.fetchall()
        print(f"共 {len(orphan_parts)} 个零件:")
        for i, row in enumerate(orphan_parts, 1):
            print(f"  {i}. Part ID={row[0]}, 编号={row[1]}, 名称={row[2]}")
            print(f"     T={row[3]}, W={row[4]}, P={row[5]}, TWPH={row[6]}")
        print()
        
        # 2. 检查这些零件是否关联了 tooling
        print("【分析】检查这24个零件是否有关联的工装")
        print("-" * 80)
        
        orphan_ids = [str(row[0]) for row in orphan_parts]
        if orphan_ids:
            result = await db.execute(text(f"""
                SELECT 
                    tp.part_id,
                    tp.tooling_id,
                    t.tooling_number,
                    t.tooling_name,
                    t.spec_twph
                FROM tooling_parts tp
                LEFT JOIN tooling t ON t.id = tp.tooling_id
                WHERE tp.part_id IN ({','.join(orphan_ids)})
                ORDER BY tp.part_id
            """))
            
            tooling_relations = result.fetchall()
            if tooling_relations:
                print(f"  发现 {len(tooling_relations)} 个工装关联:")
                for row in tooling_relations:
                    print(f"    Part {row[0]} -> Tooling {row[1]} ({row[2]}, {row[3]})")
                    print(f"      Tooling.spec_twph = {row[4]}")
            else:
                print("  这些零件都没有关联工装 (tooling_parts 表)")
        print()
        
        # 3. 检查 part_tooling_specs 中 is_primary=False 的记录
        print("【分析】Part_Tooling_Specs 中 is_primary 分布")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                is_primary,
                COUNT(*) as count
            FROM part_tooling_specs
            GROUP BY is_primary
        """))
        
        for row in result:
            primary_status = "TRUE (主规格)" if row[0] else "FALSE (非主规格)"
            print(f"  {primary_status}: {row[1]} 条")
        print()
        
        # 4. 检查 is_primary=False 的详细情况
        print("【分析】is_primary=FALSE 的规格记录 (采样10条)")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                pts.id,
                pts.part_id,
                pts.tooling_id,
                pts.thickness,
                pts.width,
                pts.pitch,
                pts.source_sheet,
                p.part_number
            FROM part_tooling_specs pts
            LEFT JOIN parts p ON p.id = pts.part_id
            WHERE pts.is_primary = FALSE
            ORDER BY pts.id DESC
            LIMIT 10
        """))
        
        for row in result:
            print(f"  ID={row[0]}, Part={row[1]}({row[7]}), Tooling={row[2]}")
            print(f"    T={row[3]}, W={row[4]}, P={row[5]}, Sheet={row[6]}")
        print()
        
        # 5. 检查每个零件有多少个 spec 记录
        print("【分析】零件的 spec 记录数量分布")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                spec_count,
                COUNT(*) as part_count
            FROM (
                SELECT part_id, COUNT(*) as spec_count
                FROM part_tooling_specs
                GROUP BY part_id
            ) sub
            GROUP BY spec_count
            ORDER BY spec_count
        """))
        
        for row in result:
            print(f"  有 {row[0]} 个 spec 的零件: {row[1]} 个")
        print()
        
        # 6. 检查有多个 spec 但都是 is_primary=False 的零件
        print("【分析】有多个 spec 但无主规格的零件")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                part_id,
                COUNT(*) as total_specs,
                COUNT(CASE WHEN is_primary THEN 1 END) as primary_count
            FROM part_tooling_specs
            GROUP BY part_id
            HAVING COUNT(*) > 1 AND COUNT(CASE WHEN is_primary THEN 1 END) = 0
            LIMIT 10
        """))
        
        no_primary_parts = result.fetchall()
        if no_primary_parts:
            print(f"  发现 {len(no_primary_parts)} 个零件有多个 spec 但无主规格:")
            for row in no_primary_parts:
                print(f"    Part ID={row[0]}, total_specs={row[1]}")
        else:
            print("  未发现此类情况")
        print()
        
        # 7. TWP 数值统计
        print("【统计】TWP 数值范围")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                'part_tooling_specs' as source,
                MIN(thickness) as min_t, MAX(thickness) as max_t, AVG(thickness) as avg_t,
                MIN(width) as min_w, MAX(width) as max_w, AVG(width) as avg_w,
                MIN(pitch) as min_p, MAX(pitch) as max_p, AVG(pitch) as avg_p
            FROM part_tooling_specs
            WHERE thickness IS NOT NULL
            UNION ALL
            SELECT 
                'parts' as source,
                MIN(thickness), MAX(thickness), AVG(thickness),
                MIN(width), MAX(width), AVG(width),
                MIN(pitch), MAX(pitch), AVG(pitch)
            FROM parts
            WHERE is_deleted = FALSE AND thickness IS NOT NULL
        """))
        
        for row in result:
            print(f"  {row[0]}:")
            if row[1]:
                print(f"    Thickness: {row[1]:.3f} ~ {row[2]:.3f} (avg: {row[3]:.3f})")
            if row[4]:
                print(f"    Width:     {row[4]:.3f} ~ {row[5]:.3f} (avg: {row[6]:.3f})")
            if row[7]:
                print(f"    Pitch:     {row[7]:.3f} ~ {row[8]:.3f} (avg: {row[9]:.3f})")
        print()
        
        # 8. 检查 source_sheet 分布
        print("【统计】source_sheet 分布 (前10个)")
        print("-" * 80)
        
        result = await db.execute(text("""
            SELECT 
                source_sheet,
                COUNT(*) as count
            FROM part_tooling_specs
            WHERE source_sheet IS NOT NULL
            GROUP BY source_sheet
            ORDER BY count DESC
            LIMIT 10
        """))
        
        for row in result:
            print(f"  {row[0]}: {row[1]} 条记录")
        print()
        
        print("=" * 80)
        print("详细审计完成")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
