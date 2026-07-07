#!/usr/bin/env python3
"""
T008: 迁移 material_base_prices 数据到 material_dict
将旧表中的材料价格数据迁移到 material_dict 表
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database import async_engine


async def migrate():
    """Migrate data from material_base_prices to material_dict."""

    sql = """
    -- 检查 material_base_prices 表是否存在
    DO $$
    BEGIN
        IF EXISTS (SELECT FROM information_schema.tables
                   WHERE table_name = 'material_base_prices') THEN

            -- 迁移数据：按 material_name 匹配，避免重复
            INSERT INTO material_dict (code, name, density, default_price, scrap_price, is_active, created_at)
            SELECT
                mbp.material_name,
                mbp.material_name,
                mbp.default_density,
                mbp.default_price,
                mbp.scrap_price,
                TRUE,
                COALESCE(mbp.updated_at, NOW())
            FROM material_base_prices mbp
            WHERE NOT EXISTS (
                SELECT 1 FROM material_dict md WHERE md.name = mbp.material_name
            );

            RAISE NOTICE '✅ material_base_prices 数据迁移完成';
        ELSE
            RAISE NOTICE 'ℹ️  material_base_prices 表不存在，跳过迁移';
        END IF;
    END $$;
    """

    async with async_engine.begin() as conn:
        result = await conn.execute(text(sql))
        # asyncpg 会自动打印 RAISE NOTICE 的消息

    print("✅ 材料价格数据迁移完成")


async def rollback():
    """Rollback: 无法回滚数据迁移（已插入 material_dict）."""
    print("⚠️  数据迁移无法回滚（material_dict 中的数据需手动清理）")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
