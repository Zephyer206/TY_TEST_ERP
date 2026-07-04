"""Fix part name data - split category from name."""

import asyncio
from sqlalchemy import text
from app.database import async_session_maker

async def fix_part_names():
    async with async_session_maker() as session:
        print("修复零件名称数据...")

        # 获取当前数据
        result = await session.execute(text("SELECT id, name FROM part_name_dict"))
        items = result.fetchall()

        for item_id, name in items:
            # 如果名称包含"-"，拆分为分类和名称
            if '-' in name:
                parts = name.split('-', 1)
                category = parts[0].strip()
                new_name = parts[1].strip()

                print(f"更新 ID {item_id}: '{name}' -> category='{category}', name='{new_name}'")

                await session.execute(
                    text("UPDATE part_name_dict SET category = :category, name = :name WHERE id = :id"),
                    {"id": item_id, "category": category, "name": new_name}
                )
            else:
                # 没有"-"的，设置为默认分类
                print(f"设置默认分类 ID {item_id}: '{name}' -> category='其他'")
                await session.execute(
                    text("UPDATE part_name_dict SET category = :category WHERE id = :id"),
                    {"id": item_id, "category": "其他"}
                )

        await session.commit()
        print("\n修复完成！")

        # 验证结果
        result = await session.execute(text("SELECT id, name, category FROM part_name_dict ORDER BY category, name"))
        print("\n修复后的数据：")
        print("-" * 60)
        for row in result.fetchall():
            print(f"ID: {row[0]:3} | 分类: {row[2] or 'None':10} | 名称: {row[1]}")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(fix_part_names())
