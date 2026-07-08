#!/usr/bin/env python3
"""
T004: 创建 treatment_dict 表
工序字典表，存储全局工序参考信息和默认费率
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database import engine


async def migrate():
    """Create treatment_dict table."""

    sql = """
    -- 创建 treatment_dict 表
    CREATE TABLE IF NOT EXISTS treatment_dict (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) UNIQUE NOT NULL,
        calc_mode VARCHAR(20) NOT NULL DEFAULT 'manual',
        default_rate NUMERIC(10,4) NOT NULL DEFAULT 0,
        unit VARCHAR(20) NOT NULL DEFAULT '元/件',
        is_active BOOLEAN DEFAULT TRUE,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),

        CONSTRAINT chk_calc_mode CHECK (calc_mode IN ('manual', 'net_weight')),
        CONSTRAINT chk_default_rate CHECK (default_rate >= 0)
    );

    -- 创建索引
    CREATE INDEX IF NOT EXISTS idx_treatment_dict_active ON treatment_dict(is_active);

    -- 插入种子数据（10条真实工序）
    INSERT INTO treatment_dict (name, calc_mode, default_rate, unit, is_active, sort_order) VALUES
    ('热处理', 'manual', 1.50, '元/件', TRUE, 1),
    ('电镀锌', 'manual', 2.00, '元/件', TRUE, 2),
    ('发黑', 'manual', 1.20, '元/件', TRUE, 3),
    ('喷涂', 'manual', 2.50, '元/件', TRUE, 4),
    ('贴胶', 'manual', 0.80, '元/件', TRUE, 5),
    ('阳极氧化', 'manual', 3.00, '元/件', TRUE, 6),
    ('磷化', 'manual', 1.80, '元/件', TRUE, 7),
    ('压铸镀层', 'net_weight', 15.00, '元/kg', TRUE, 8),
    ('电镀镍', 'manual', 3.50, '元/件', TRUE, 9),
    ('达克罗涂装', 'manual', 4.00, '元/件', TRUE, 10)
    ON CONFLICT (name) DO NOTHING;

    -- 添加注释
    COMMENT ON TABLE treatment_dict IS '工序字典表 - 全局工序参考和默认费率';
    COMMENT ON COLUMN treatment_dict.calc_mode IS '计价方式: manual(按件) / net_weight(按重量)';
    COMMENT ON COLUMN treatment_dict.default_rate IS '默认费率（兜底值）';
    COMMENT ON COLUMN treatment_dict.unit IS '单位: 元/件 或 元/kg';
    """

    async with engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ treatment_dict 表创建成功，已插入10条种子数据")


async def rollback():
    """Rollback: Drop treatment_dict table."""

    sql = """
    DROP TABLE IF EXISTS treatment_dict CASCADE;
    """

    async with engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ treatment_dict 表已删除")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
