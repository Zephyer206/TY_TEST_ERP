"""Update part name data with correct structure."""

import asyncio
from sqlalchemy import text
from app.database import async_session_maker

async def update_part_names():
    async with async_session_maker() as session:
        print("更新零件名称数据...")

        # 获取当前数据
        result = await session.execute(text("SELECT id, name, category FROM part_name_dict"))
        current = result.fetchall()
        print(f"\n当前有 {len(current)} 条记录")

        # 更新策略：
        # ID 1: "弹簧片" -> category="弹簧片类", name="弹簧片"
        # ID 2: "摩擦片保持(右)" -> category="弹簧片类", name="摩擦片保持(右)"
        # ID 3: "摩擦片保持" -> category="弹簧片类", name="摩擦片保持"
        # ID 4: "报警器" -> category="报警器类", name="报警器"

        updates = [
            (1, "弹簧片类", "弹簧片"),
            (2, "弹簧片类", "摩擦片保持(右)"),
            (3, "弹簧片类", "摩擦片保持"),
            (4, "报警器类", "报警器"),
        ]

        for item_id, category, name in updates:
            await session.execute(
                text("UPDATE part_name_dict SET category = :category, name = :name WHERE id = :id"),
                {"id": item_id, "category": category, "name": name}
            )
            print(f"更新 ID {item_id}: category='{category}', name='{name}'")

        await session.commit()
        print("\n更新完成！")

        # 验证结果
        result = await session.execute(
            text("SELECT id, category, name, sub_category FROM part_name_dict ORDER BY category, name")
        )
        print("\n更新后的数据：")
        print("-" * 80)
        print(f"{'ID':<5} {'大类（category）':<20} {'零件名称（name）':<25} {'客户零件名'}")
        print("-" * 80)
        for row in result.fetchall():
            print(f"{row[0]:<5} {row[1] or 'None':<20} {row[2]:<25} {row[3] or '-'}")
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(update_part_names())
