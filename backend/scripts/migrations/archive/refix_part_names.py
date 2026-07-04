"""Re-fix part name data with correct structure."""

import asyncio
from sqlalchemy import text
from app.database import async_session_maker

async def refix_part_names():
    async with async_session_maker() as session:
        print("重新整理零件名称数据...")

        # 清空现有数据
        await session.execute(text("DELETE FROM part_name_dict"))

        # 插入正确的数据结构
        data = [
            # category（大类）, name（零件名称）, sub_category（客户零件名称）
            ("弹簧片类", "摩擦片保持", None),
            ("弹簧片类", "摩擦片保持(右)", None),
            ("弹簧片类", "弹簧片", None),
            ("报警器类", "报警器", None),
        ]

        for category, name, sub_category in data:
            await session.execute(
                text("""
                    INSERT INTO part_name_dict (name, category, sub_category, usage_count, is_active, sort_order)
                    VALUES (:name, :category, :sub_category, 0, TRUE, 0)
                """),
                {"name": name, "category": category, "sub_category": sub_category}
            )
            print(f"插入: 大类={category}, 零件名称={name}")

        await session.commit()
        print("\n数据整理完成！")

        # 验证结果
        result = await session.execute(
            text("SELECT id, category, name, sub_category FROM part_name_dict ORDER BY category, name")
        )
        print("\n整理后的数据：")
        print("-" * 80)
        print(f"{'ID':<5} {'大类（category）':<20} {'零件名称（name）':<25} {'客户零件名（sub_category）'}")
        print("-" * 80)
        for row in result.fetchall():
            print(f"{row[0]:<5} {row[1] or 'None':<20} {row[2]:<25} {row[3] or '-'}")
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(refix_part_names())
