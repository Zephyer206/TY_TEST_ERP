#!/usr/bin/env python3
"""
T006: 创建 customer_treatment_prices 表
客户工序价格历史表
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database import async_engine


async def migrate():
    """Create customer_treatment_prices table."""

    sql = """
    -- 创建 customer_treatment_prices 表
    CREATE TABLE IF NOT EXISTS customer_treatment_prices (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES tooling_customers(id),
        treatment_id INTEGER NOT NULL REFERENCES treatment_dict(id),
        unit_price NUMERIC(10,4) NOT NULL,
        calc_mode_snapshot VARCHAR(20),
        unit_snapshot VARCHAR(20),
        quote_id INTEGER REFERENCES quotes(id),
        quoted_at TIMESTAMP DEFAULT NOW(),
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT NOW(),

        CONSTRAINT chk_unit_price CHECK (unit_price > 0)
    );

    -- 创建索引
    CREATE INDEX IF NOT EXISTS idx_ctp_customer_treatment
        ON customer_treatment_prices(customer_id, treatment_id, quoted_at DESC);

    CREATE INDEX IF NOT EXISTS idx_ctp_quote
        ON customer_treatment_prices(quote_id) WHERE quote_id IS NOT NULL;

    -- 添加注释
    COMMENT ON TABLE customer_treatment_prices IS '客户工序价格历史表 - 记录每个客户每次报价的工序费用';
    COMMENT ON COLUMN customer_treatment_prices.unit_price IS '工序价格';
    COMMENT ON COLUMN customer_treatment_prices.calc_mode_snapshot IS '快照：当时的计价方式';
    COMMENT ON COLUMN customer_treatment_prices.unit_snapshot IS '快照：当时的单位';
    """

    async with async_engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ customer_treatment_prices 表创建成功")


async def rollback():
    """Rollback: Drop customer_treatment_prices table."""

    sql = """
    DROP TABLE IF EXISTS customer_treatment_prices CASCADE;
    """

    async with async_engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ customer_treatment_prices 表已删除")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
