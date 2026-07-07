#!/usr/bin/env python3
"""
T007: 创建 price_adjustments 表
价格调整审批表
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database import async_engine


async def migrate():
    """Create price_adjustments table."""

    sql = """
    -- 创建 price_adjustments 表
    CREATE TABLE IF NOT EXISTS price_adjustments (
        id SERIAL PRIMARY KEY,
        price_account_id INTEGER NOT NULL REFERENCES prices(id),
        old_price NUMERIC(10,4) NOT NULL,
        new_price NUMERIC(10,4) NOT NULL,
        adjustment_type VARCHAR(20) NOT NULL,
        reason TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        created_by INTEGER NOT NULL REFERENCES users(id),
        created_at TIMESTAMP DEFAULT NOW(),
        approved_by INTEGER REFERENCES users(id),
        approved_at TIMESTAMP,
        rejection_reason TEXT,

        CONSTRAINT chk_price_different CHECK (old_price != new_price),
        CONSTRAINT chk_adjustment_type CHECK (
            (adjustment_type = 'increase' AND new_price > old_price) OR
            (adjustment_type = 'decrease' AND new_price < old_price)
        ),
        CONSTRAINT chk_status CHECK (status IN ('pending', 'approved', 'rejected'))
    );

    -- 创建索引
    CREATE INDEX IF NOT EXISTS idx_pa_status_created
        ON price_adjustments(status, created_at DESC);

    CREATE INDEX IF NOT EXISTS idx_pa_price_account
        ON price_adjustments(price_account_id);

    -- 添加注释
    COMMENT ON TABLE price_adjustments IS '价格调整审批表 - 实现调价申请→审批流程';
    COMMENT ON COLUMN price_adjustments.adjustment_type IS '调价类型: increase(上涨) / decrease(下降)';
    COMMENT ON COLUMN price_adjustments.status IS '审批状态: pending / approved / rejected';
    COMMENT ON COLUMN price_adjustments.reason IS '调价原因';
    COMMENT ON COLUMN price_adjustments.rejection_reason IS '驳回原因';
    """

    async with async_engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ price_adjustments 表创建成功")


async def rollback():
    """Rollback: Drop price_adjustments table."""

    sql = """
    DROP TABLE IF EXISTS price_adjustments CASCADE;
    """

    async with async_engine.begin() as conn:
        await conn.execute(text(sql))

    print("✅ price_adjustments 表已删除")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
