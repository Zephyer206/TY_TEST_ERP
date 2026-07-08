#!/usr/bin/env python3
"""
T010: 删除旧表
删除已迁移的旧表：material_base_prices, treatment_dicts
以及空的占位符表：material_cost_history, treatment_cost_history
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database import engine


async def migrate():
    """Drop legacy tables after migration."""

    sql = """
    -- 删除旧表（如果存在）
    DROP TABLE IF EXISTS material_base_prices CASCADE;
    DROP TABLE IF EXISTS treatment_dicts CASCADE;
    DROP TABLE IF EXISTS material_cost_history CASCADE;
    DROP TABLE IF EXISTS treatment_cost_history CASCADE;

    -- 删除占位符表（已在 price.py 中定义但实际不使用）
    DROP TABLE IF EXISTS annual_price_records_placeholder CASCADE;
    DROP TABLE IF EXISTS price_adjustments_placeholder CASCADE;
    """

    async with engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ 旧表已删除：material_base_prices, treatment_dicts, material_cost_history, treatment_cost_history")
    print("✅ 占位符表已删除：annual_price_records_placeholder, price_adjustments_placeholder")


async def rollback():
    """Rollback: 无法恢复已删除的表."""
    print("⚠️  无法恢复已删除的表（需从备份恢复）")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
