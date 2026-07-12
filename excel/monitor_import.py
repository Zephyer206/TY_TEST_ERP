#!/usr/bin/env python3
"""
监控导入进度
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from sqlalchemy import text
from app.database import engine


async def monitor_progress():
    """监控导入进度"""
    print("正在监控导入进度...")

    while True:
        try:
            async with engine.begin() as conn:
                # 统计数据
                result = await conn.execute(text("SELECT COUNT(*) FROM tooling"))
                tooling_count = result.fetchone()[0]

                result = await conn.execute(text("SELECT COUNT(*) FROM parts"))
                parts_count = result.fetchone()[0]

                result = await conn.execute(text("""
                    SELECT COUNT(*) FROM tooling WHERE is_multi_product = TRUE
                """))
                multi_count = result.fetchone()[0]

                print(f"\r模具: {tooling_count} | 零件: {parts_count} | 左右件: {multi_count}", end='', flush=True)

        except Exception as e:
            print(f"\n错误: {e}")
            break

        await asyncio.sleep(5)


if __name__ == '__main__':
    try:
        asyncio.run(monitor_progress())
    except KeyboardInterrupt:
        print("\n\n监控停止")
