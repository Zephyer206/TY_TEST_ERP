"""Reconcile batch 8 inventory using only verified IMPORTED rows."""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import text
from app.database import async_session_maker

BATCH_ID = 8
EXPECTED = {1421: -4900, 2611: 50600, 2734: 4000, 2764: 10600, 2765: 8400, 4853: 3900}
STALE = {2865: 3000, 2866: 4000, 4875: 32000, 4876: 29000, 4878: 0}

async def main() -> None:
    async with async_session_maker() as session:
        query = text("""
            WITH imp AS (
                SELECT resolved_part_id part_id,
                       sum((raw_data->>'closing_qty')::numeric) qty
                FROM excel_import_rows
                WHERE batch_id=:batch_id AND validation_status='IMPORTED'
                GROUP BY resolved_part_id
            ), tx AS (
                SELECT part_id, sum(quantity) qty
                FROM inventory_transactions
                WHERE reference_id=:batch_id
                GROUP BY part_id
            )
            SELECT imp.part_id, imp.qty imported, COALESCE(tx.qty, 0) tx_qty,
                   imp.qty - COALESCE(tx.qty, 0) delta
            FROM imp LEFT JOIN tx USING(part_id)
            WHERE imp.qty <> COALESCE(tx.qty, 0)
            ORDER BY imp.part_id
        """)
        diffs = [dict(row) for row in (await session.execute(query, {'batch_id': BATCH_ID})).mappings()]
        actual = {int(row['part_id']): int(row['delta']) for row in diffs}
        if actual != EXPECTED:
            raise RuntimeError(f'unexpected discrepancies: {actual}')

        now = datetime.utcnow()
        for part_id, quantity in STALE.items():
            if quantity == 0:
                continue
            inventory = (await session.execute(
                text('SELECT id, stock_qty FROM finished_goods_inventory WHERE part_id=:part_id FOR UPDATE'),
                {'part_id': part_id},
            )).one_or_none()
            if inventory is None:
                raise RuntimeError(f'missing inventory row for stale part {part_id}')
            before = int(inventory[1] or 0)
            after = before - quantity
            await session.execute(
                text('UPDATE finished_goods_inventory SET stock_qty=:after,last_update_at=:now WHERE id=:id'),
                {'after': after, 'now': now, 'id': inventory[0]},
            )
            await session.execute(text("""
                INSERT INTO inventory_transactions
                    (part_id, transaction_type, quantity, stock_before, stock_after,
                     reference_type, reference_id, reason, created_at)
                VALUES (:part_id, 'adjustment', :quantity, :before, :after,
                        'excel_snapshot_reconciliation', :batch_id, :reason, :now)
            """), {
                'part_id': part_id, 'quantity': -quantity, 'before': before, 'after': after,
                'batch_id': BATCH_ID, 'reason': '撤销批次8中已退回待审理记录的旧库存流水；不代表新的可用库存', 'now': now,
            })

        for part_id, delta in EXPECTED.items():
            if delta <= 0:
                continue
            inventory = (await session.execute(
                text('SELECT id, stock_qty FROM finished_goods_inventory WHERE part_id=:part_id FOR UPDATE'),
                {'part_id': part_id},
            )).one_or_none()
            if inventory is None:
                raise RuntimeError(f'missing inventory row for part {part_id}')
            before = int(inventory[1] or 0)
            after = before + delta
            await session.execute(
                text('UPDATE finished_goods_inventory SET stock_qty=:after,last_update_at=:now WHERE id=:id'),
                {'after': after, 'now': now, 'id': inventory[0]},
            )
            await session.execute(text("""
                INSERT INTO inventory_transactions
                    (part_id, transaction_type, quantity, stock_before, stock_after,
                     reference_type, reference_id, reason, created_at)
                VALUES (:part_id, 'opening_balance_increment', :quantity, :before, :after,
                        'excel_snapshot_reconciliation', :batch_id, :reason, :now)
            """), {
                'part_id': part_id, 'quantity': delta, 'before': before, 'after': after,
                'batch_id': BATCH_ID, 'reason': '补齐批次8已核验记录与库存流水差额；仅纳入IMPORTED记录，库位保持原值', 'now': now,
            })

        await session.execute(text("""
            INSERT INTO inventory_transactions
                (part_id, transaction_type, quantity, stock_before, stock_after,
                 reference_type, reference_id, reason, created_at)
            VALUES (1421, 'opening_balance_rejected', 0, 0, 0,
                    'excel_snapshot_reconciliation', :batch_id,
                    '批次8已核验记录出现负结存 -4900，按规则不转为可用库存，待仓库核查', :now)
        """), {'batch_id': BATCH_ID, 'now': now})

        await session.execute(text("""
            UPDATE parts p
            SET stock_pcs=i.stock_qty, updated_at=NOW()
            FROM (
                SELECT part_id, SUM(stock_qty)::integer stock_qty
                FROM finished_goods_inventory
                WHERE part_id IN (
                    SELECT DISTINCT resolved_part_id
                    FROM excel_import_rows
                    WHERE batch_id=:batch_id AND validation_status='IMPORTED'
                ) OR part_id IN (2865,2866,4875,4876,4878)
                GROUP BY part_id
            ) i
            WHERE p.id=i.part_id
        """), {'batch_id': BATCH_ID})
        await session.commit()
        print({'stale_reversed': STALE, 'positive_deltas': {k: v for k, v in EXPECTED.items() if v > 0}, 'negative_rejected': 1421})

if __name__ == '__main__':
    asyncio.run(main())
