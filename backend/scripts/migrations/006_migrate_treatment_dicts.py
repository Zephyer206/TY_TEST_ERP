#!/usr/bin/env python3
"""
T009: 迁移 treatment_dicts 数据到 treatment_dict
白名单机制，只迁移10条真实工序，过滤测试数据
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database import async_engine


async def migrate():
    """Migrate data from treatment_dicts to treatment_dict (whitelist only)."""

    sql = """
    -- 检查 treatment_dicts 表是否存在
    DO $$
    BEGIN
        IF EXISTS (SELECT FROM information_schema.tables
                   WHERE table_name = 'treatment_dicts') THEN

            -- 白名单迁移：只迁移10条真实工序，过滤测试数据
            INSERT INTO treatment_dict (name, calc_mode, default_rate, unit, is_active)
            SELECT name, calc_mode, rate, unit, TRUE
            FROM treatment_dicts
            WHERE name IN (
                '热处理','电镀锌','发黑','喷涂','贴胶',
                '阳极氧化','磷化','压铸镀层','电镀镍','达克罗涂装'
            )
            ON CONFLICT (name) DO NOTHING;

            RAISE NOTICE '✅ treatment_dicts 数据迁移完成（白名单10条）';
        ELSE
            RAISE NOTICE 'ℹ️  treatment_dicts 表不存在，跳过迁移';
        END IF;
    END $$;
    """

    async with async_engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ 工序字典数据迁移完成（白名单10条，测试数据已过滤）")


async def rollback():
    """Rollback: 无法回滚数据迁移."""
    print("⚠️  数据迁移无法回滚（treatment_dict 中的数据需手动清理）")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
