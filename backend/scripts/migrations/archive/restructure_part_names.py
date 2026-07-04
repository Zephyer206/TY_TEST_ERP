"""Restructure part_name_dict to three-level categorization."""

import asyncio
from sqlalchemy import text
from app.database import async_session_maker

async def restructure_part_names():
    async with async_session_maker() as session:
        print("开始重构 part_name_dict 表结构...")

        # 1. 添加新字段
        print("\n1. 添加新字段...")
        await session.execute(text("""
            ALTER TABLE part_name_dict
            ADD COLUMN IF NOT EXISTS primary_category VARCHAR(100),
            ADD COLUMN IF NOT EXISTS secondary_category VARCHAR(100),
            ADD COLUMN IF NOT EXISTS customer_part_name VARCHAR(200),
            ADD COLUMN IF NOT EXISTS remark TEXT
        """))
        await session.commit()
        print("   新字段添加完成")

        # 2. 迁移现有数据
        print("\n2. 迁移现有数据...")

        migrations = [
            (1, "弹簧片", "弹簧片", None, "标准件"),
            (2, "弹簧片", "弹簧片", "摩擦片保持(右)", None),
            (3, "弹簧片", "弹簧片", "摩擦片保持", None),
            (4, "报警器", "报警器", None, "标准件"),
        ]

        for item_id, primary, secondary, customer, remark in migrations:
            await session.execute(
                text("""
                    UPDATE part_name_dict
                    SET primary_category = :primary,
                        secondary_category = :secondary,
                        customer_part_name = :customer,
                        remark = :remark
                    WHERE id = :id
                """),
                {
                    "id": item_id,
                    "primary": primary,
                    "secondary": secondary,
                    "customer": customer,
                    "remark": remark
                }
            )
            print(f"   ID {item_id}: 一级={primary}, 二级={secondary}, 三级={customer or 'NULL'}")

        await session.commit()
        print("   数据迁移完成")

        # 3. 设置 primary_category 为 NOT NULL
        print("\n3. 设置约束...")
        await session.execute(text("""
            ALTER TABLE part_name_dict
            ALTER COLUMN primary_category SET NOT NULL
        """))
        await session.commit()
        print("   primary_category 已设置为 NOT NULL")

        # 4. 创建复合唯一索引
        print("\n4. 创建唯一索引...")
        try:
            await session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_part_name_unique
                ON part_name_dict (primary_category, secondary_category, customer_part_name)
            """))
            await session.commit()
            print("   唯一索引创建完成")
        except Exception as e:
            print(f"   索引创建警告: {e}")

        # 5. 验证结果
        print("\n5. 验证迁移结果...")
        result = await session.execute(
            text("""
                SELECT id, primary_category, secondary_category, customer_part_name, remark
                FROM part_name_dict
                ORDER BY id
            """)
        )

        print("\n" + "="*100)
        print(f"{'ID':<5} {'一级分类':<15} {'二级分类':<15} {'三级分类（客户）':<25} {'备注'}")
        print("="*100)
        for row in result.fetchall():
            print(f"{row[0]:<5} {row[1] or 'NULL':<15} {row[2] or 'NULL':<15} {row[3] or 'NULL':<25} {row[4] or '-'}")
        print("="*100)

        print("\n✓ 表结构重构完成！")

if __name__ == "__main__":
    asyncio.run(restructure_part_names())
