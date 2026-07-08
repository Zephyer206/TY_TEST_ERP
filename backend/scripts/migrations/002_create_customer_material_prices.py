#!/usr/bin/env python3
"""
T005: 创建 customer_material_prices 表
客户材料价格历史表
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database import engine


async def migrate():
    """Create customer_material_prices table."""

    sql = """
    -- 创建 customer_material_prices 表（使用 INTEGER 主键匹配现有数据库）
    CREATE TABLE IF NOT EXISTS customer_material_prices (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES tooling_customers(id),
        material_id INTEGER NOT NULL REFERENCES material_dict(id),
        unit_price NUMERIC(10,4) NOT NULL,
        scrap_price NUMERIC(10,4),
        quote_id INTEGER REFERENCES quotes(id),
        quoted_at TIMESTAMP DEFAULT NOW(),
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT NOW(),

        CONSTRAINT chk_unit_price CHECK (unit_price > 0),
        CONSTRAINT chk_scrap_price CHECK (scrap_price IS NULL OR scrap_price >= 0)
    );

    -- 创建索引
    CREATE INDEX IF NOT EXISTS idx_cmp_customer_material
        ON customer_material_prices(customer_id, material_id, quoted_at DESC);

    CREATE INDEX IF NOT EXISTS idx_cmp_quote
        ON customer_material_prices(quote_id) WHERE quote_id IS NOT NULL;

    -- 添加注释
    COMMENT ON TABLE customer_material_prices IS '客户材料价格历史表 - 记录每个客户每次报价的材料单价';
    COMMENT ON COLUMN customer_material_prices.unit_price IS '材料单价（元/kg）';
    COMMENT ON COLUMN customer_material_prices.scrap_price IS '废料回收价（元/kg）';
    COMMENT ON COLUMN customer_material_prices.quote_id IS '关联报价单ID（可追溯定价来源）';
    """

    async with engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ customer_material_prices 表创建成功")


async def rollback():
    """Rollback: Drop customer_material_prices table."""

    sql = """
    DROP TABLE IF EXISTS customer_material_prices CASCADE;
    """

    async with engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ customer_material_prices 表已删除")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
