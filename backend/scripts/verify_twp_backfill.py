"""Verify TWP backfill results and traceability to Excel."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from app.database import get_db_context


async def verify_backfill():
    async with get_db_context() as db:
        # Query 1: Check TWP coverage
        print('=' * 60)
        print('TWP Coverage Analysis')
        print('=' * 60)

        result = await db.execute(text('''
            SELECT
                COUNT(*) as total_parts,
                COUNT(thickness) as has_thickness,
                COUNT(width) as has_width,
                COUNT(pitch) as has_pitch,
                COUNT(CASE WHEN thickness IS NOT NULL AND width IS NOT NULL AND pitch IS NOT NULL THEN 1 END) as complete_twp
            FROM parts
            WHERE is_deleted = false
        '''))
        row = result.fetchone()
        print(f'\nTotal parts: {row[0]}')
        print(f'Has thickness: {row[1]} ({row[1]*100.0/row[0]:.1f}%)')
        print(f'Has width: {row[2]} ({row[2]*100.0/row[0]:.1f}%)')
        print(f'Has pitch: {row[3]} ({row[3]*100.0/row[0]:.1f}%)')
        print(f'Complete TWP (all 3): {row[4]} ({row[4]*100.0/row[0]:.1f}%)')

        # Query 2: Verify backfilled data matches Excel
        print(f'\n' + '=' * 60)
        print('Backfill Traceability Verification')
        print('=' * 60)

        result = await db.execute(text('''
            SELECT
                p.id,
                p.internal_name,
                p.thickness,
                p.width,
                p.pitch,
                COUNT(eir.id) as excel_row_count,
                STRING_AGG(DISTINCT CONCAT(
                    'T=', eir.parsed_thickness::text,
                    ' W=', eir.parsed_width::text,
                    ' P=', eir.parsed_pitch::text
                ), ' | ') as excel_values
            FROM parts p
            JOIN excel_import_rows eir ON eir.resolved_part_id = p.id
            WHERE p.id IN (1, 13, 21, 22, 24, 26, 27, 28)
            AND p.thickness IS NOT NULL
            AND p.width IS NOT NULL
            AND p.pitch IS NOT NULL
            AND eir.validation_status = 'IMPORTED'
            AND eir.parsed_thickness IS NOT NULL
            AND eir.parsed_width IS NOT NULL
            AND eir.parsed_pitch IS NOT NULL
            GROUP BY p.id, p.internal_name, p.thickness, p.width, p.pitch
            ORDER BY p.id
        '''))

        print(f'\nSample backfilled parts (first 8):')
        for row in result:
            match = 'MATCH' if f'T={row[2]}' in row[6] else 'MISMATCH'
            print(f'  Part {row[0]} ({row[1]}):')
            print(f'    Parts table: T={row[2]} W={row[3]} P={row[4]}')
            print(f'    Excel source: {row[6]} [{match}]')

        # Query 3: Check for any impossible values
        print(f'\n' + '=' * 60)
        print('Data Quality Check')
        print('=' * 60)

        result = await db.execute(text('''
            SELECT
                COUNT(*) as out_of_range
            FROM parts
            WHERE is_deleted = false
            AND (
                thickness < 0.1 OR thickness > 10 OR
                width < 1 OR width > 1000 OR
                pitch < 1 OR pitch > 1000
            )
        '''))
        row = result.fetchone()
        print(f'\nParts with out-of-range TWP values: {row[0]}')

        if row[0] > 0:
            result = await db.execute(text('''
                SELECT id, internal_name, thickness, width, pitch
                FROM parts
                WHERE is_deleted = false
                AND (
                    thickness < 0.1 OR thickness > 10 OR
                    width < 1 OR width > 1000 OR
                    pitch < 1 OR pitch > 1000
                )
                LIMIT 5
            '''))
            print('  Examples:')
            for row in result:
                print(f'    Part {row[0]} ({row[1]}): T={row[2]} W={row[3]} P={row[4]}')
        else:
            print('  All TWP values are within expected ranges.')

        # Query 4: Summary of backfill operation
        print(f'\n' + '=' * 60)
        print('Backfill Operation Summary')
        print('=' * 60)

        result = await db.execute(text('''
            SELECT
                COUNT(*) as backfilled_count
            FROM parts
            WHERE updated_at > NOW() - INTERVAL '10 minutes'
            AND thickness IS NOT NULL
            AND width IS NOT NULL
            AND pitch IS NOT NULL
        '''))
        row = result.fetchone()
        print(f'\nParts updated in last 10 minutes: {row[0]}')


if __name__ == "__main__":
    asyncio.run(verify_backfill())
