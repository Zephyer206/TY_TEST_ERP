"""Database migration script for dictionary tables.

This script:
1. Creates 4 dictionary tables
2. Inserts initial standard data
3. Extracts and inserts data from existing tables
4. Updates foreign key relationships
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, async_session_maker
from app.models import (
    PartNameDict,
    MaterialDict,
    MachineTonnageDict,
    MoldTypeDict,
)


async def create_tables(session: AsyncSession):
    """Step 1: Create dictionary tables."""
    print("Step 1: Creating dictionary tables...")

    # Import Base to create tables
    from app.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("OK Dictionary tables created")


async def insert_standard_data(session: AsyncSession):
    """Step 2: Insert standard data (machine tonnages, mold types)."""
    print("\nStep 2: Inserting standard data...")

    # Machine tonnages - 冲床系列
    machine_tonnages = [
        (25, 'punch_press', '25吨冲床', '小型', '冲床', 1),
        (40, 'punch_press', '40吨冲床', '小型', '冲床', 2),
        (63, 'punch_press', '63吨冲床', '小型', '冲床', 3),
        (80, 'punch_press', '80吨冲床', '中型', '冲床', 4),
        (110, 'punch_press', '110吨冲床', '中型', '冲床', 5),
        (160, 'punch_press', '160吨冲床', '中型', '冲床', 6),
        (200, 'punch_press', '200吨冲床', '中型', '冲床', 7),
        (250, 'punch_press', '250吨冲床', '大型', '冲床', 8),
        (315, 'punch_press', '315吨冲床', '大型', '冲床', 9),
        (400, 'punch_press', '400吨冲床', '大型', '冲床', 10),
        (500, 'punch_press', '500吨冲床', '大型', '冲床', 11),
        (630, 'punch_press', '630吨冲床', '特大型', '冲床', 12),
        (800, 'punch_press', '800吨冲床', '特大型', '冲床', 13),
        (1000, 'punch_press', '1000吨冲床', '特大型', '冲床', 14),
        (1250, 'punch_press', '1250吨冲床', '特大型', '冲床', 15),
        # 液压机系列
        (100, 'hydraulic_press', '100吨液压机', '中型', '液压机', 20),
        (200, 'hydraulic_press', '200吨液压机', '中型', '液压机', 21),
        (315, 'hydraulic_press', '315吨液压机', '大型', '液压机', 22),
        (500, 'hydraulic_press', '500吨液压机', '大型', '液压机', 23),
        (630, 'hydraulic_press', '630吨液压机', '特大型', '液压机', 24),
        # 伺服压力机系列
        (80, 'servo_press', '80吨伺服压力机', '中型', '伺服压力机', 30),
        (110, 'servo_press', '110吨伺服压力机', '中型', '伺服压力机', 31),
        (160, 'servo_press', '160吨伺服压力机', '中型', '伺服压力机', 32),
        (200, 'servo_press', '200吨伺服压力机', '中型', '伺服压力机', 33),
    ]

    await session.execute(
        text("""
            INSERT INTO machine_tonnage_dict
            (tonnage, machine_type, display_name, size_category, type_category, sort_order, is_active)
            VALUES (:tonnage, :machine_type, :display_name, :size_category, :type_category, :sort_order, TRUE)
            ON CONFLICT ON CONSTRAINT uq_tonnage_machine_type DO NOTHING
        """),
        [
            {
                "tonnage": t[0],
                "machine_type": t[1],
                "display_name": t[2],
                "size_category": t[3],
                "type_category": t[4],
                "sort_order": t[5]
            }
            for t in machine_tonnages
        ]
    )
    print(f"OK Inserted {len(machine_tonnages)} machine tonnage records")

    # Mold types
    mold_types = [
        ('progressive', '连续模', 'Progressive Die', 1000000, '复杂', 1),
        ('transfer', '传递模', 'Transfer Die', 800000, '复杂', 2),
        ('single', '单工序模', 'Single Stage Die', 500000, '简单', 3),
        ('compound', '复合模', 'Compound Die', 600000, '中等', 4),
        ('drawing', '拉伸模', 'Drawing Die', 500000, '中等', 5),
        ('bending', '弯曲模', 'Bending Die', 600000, '简单', 6),
        ('blanking', '冲裁模', 'Blanking Die', 800000, '简单', 7),
        ('trimming', '修边模', 'Trimming Die', 500000, '简单', 8),
        ('forming', '成型模', 'Forming Die', 600000, '中等', 9),
        ('fine_blanking', '精冲模', 'Fine Blanking Die', 1200000, '复杂', 10),
    ]

    await session.execute(
        text("""
            INSERT INTO mold_type_dict
            (code, name, name_en, typical_lifecycle, complexity_level, sort_order, is_active)
            VALUES (:code, :name, :name_en, :typical_lifecycle, :complexity_level, :sort_order, TRUE)
            ON CONFLICT (code) DO NOTHING
        """),
        [
            {
                "code": m[0],
                "name": m[1],
                "name_en": m[2],
                "typical_lifecycle": m[3],
                "complexity_level": m[4],
                "sort_order": m[5]
            }
            for m in mold_types
        ]
    )
    print(f"OK Inserted {len(mold_types)} mold type records")

    await session.commit()


async def extract_existing_data(session: AsyncSession):
    """Step 3: Extract data from existing tables and insert into dictionaries."""
    print("\nStep 3: Extracting existing data...")

    # Extract part names from parts table
    result = await session.execute(
        text("""
            INSERT INTO part_name_dict (name, usage_count, is_active, sort_order)
            SELECT internal_name, COUNT(*) as cnt, TRUE, 0
            FROM parts
            WHERE internal_name IS NOT NULL AND internal_name != ''
            GROUP BY internal_name
            ON CONFLICT (name) DO NOTHING
            RETURNING id
        """)
    )
    part_name_count = len(result.fetchall())
    print(f"OK Extracted {part_name_count} unique part names")

    # Extract materials from parts table
    result = await session.execute(
        text("""
            INSERT INTO material_dict (code, name, is_active, sort_order)
            SELECT DISTINCT
                material_name as code,
                material_name as name,
                TRUE,
                0
            FROM parts
            WHERE material_name IS NOT NULL AND material_name != ''
            ON CONFLICT (code) DO NOTHING
            RETURNING id
        """)
    )
    material_count = len(result.fetchall())
    print(f"OK Extracted {material_count} unique materials")

    await session.commit()


async def add_foreign_key_columns(session: AsyncSession):
    """Step 4: Add foreign key columns to parts and quotes tables."""
    print("\nStep 4: Adding foreign key columns...")

    # Add columns to parts table
    await session.execute(text("""
        ALTER TABLE parts
        ADD COLUMN IF NOT EXISTS part_name_id INTEGER REFERENCES part_name_dict(id),
        ADD COLUMN IF NOT EXISTS material_id INTEGER REFERENCES material_dict(id),
        ADD COLUMN IF NOT EXISTS machine_tonnage_id INTEGER REFERENCES machine_tonnage_dict(id),
        ADD COLUMN IF NOT EXISTS mold_type_id INTEGER REFERENCES mold_type_dict(id)
    """))

    # Add columns to quotes table
    await session.execute(text("""
        ALTER TABLE quotes
        ADD COLUMN IF NOT EXISTS material_id INTEGER REFERENCES material_dict(id),
        ADD COLUMN IF NOT EXISTS machine_tonnage_id INTEGER REFERENCES machine_tonnage_dict(id),
        ADD COLUMN IF NOT EXISTS mold_type_id INTEGER REFERENCES mold_type_dict(id)
    """))

    await session.commit()
    print("OK Foreign key columns added")


async def migrate_data_relationships(session: AsyncSession):
    """Step 5: Update foreign key relationships."""
    print("\nStep 5: Migrating data relationships...")

    # Link parts to part names
    result = await session.execute(
        text("""
            UPDATE parts p
            SET part_name_id = (
                SELECT id FROM part_name_dict d
                WHERE d.name = p.internal_name
            )
            WHERE p.internal_name IS NOT NULL AND p.internal_name != ''
            AND p.part_name_id IS NULL
        """)
    )
    print(f"OK Linked {result.rowcount} parts to part names")

    # Link parts to materials
    result = await session.execute(
        text("""
            UPDATE parts p
            SET material_id = (
                SELECT id FROM material_dict d
                WHERE d.code = p.material_name OR d.name = p.material_name
            )
            WHERE p.material_name IS NOT NULL AND p.material_name != ''
            AND p.material_id IS NULL
        """)
    )
    print(f"OK Linked {result.rowcount} parts to materials")

    # Link parts to mold types
    result = await session.execute(
        text("""
            UPDATE parts p
            SET mold_type_id = (
                SELECT id FROM mold_type_dict d
                WHERE d.name = p.mold_type OR d.code = p.mold_type
            )
            WHERE p.mold_type IS NOT NULL AND p.mold_type != ''
            AND p.mold_type_id IS NULL
        """)
    )
    print(f"OK Linked {result.rowcount} parts to mold types")

    # Link quotes to materials (from snapshot_mat_name)
    result = await session.execute(
        text("""
            UPDATE quotes q
            SET material_id = (
                SELECT id FROM material_dict d
                WHERE d.code = q.snapshot_mat_name OR d.name = q.snapshot_mat_name
            )
            WHERE q.snapshot_mat_name IS NOT NULL AND q.snapshot_mat_name != ''
            AND q.material_id IS NULL
        """)
    )
    print(f"OK Linked {result.rowcount} quotes to materials")

    # Link quotes to mold types
    result = await session.execute(
        text("""
            UPDATE quotes q
            SET mold_type_id = (
                SELECT id FROM mold_type_dict d
                WHERE d.name = q.mold_type OR d.code = q.mold_type
            )
            WHERE q.mold_type IS NOT NULL AND q.mold_type != ''
            AND q.mold_type_id IS NULL
        """)
    )
    print(f"OK Linked {result.rowcount} quotes to mold types")

    await session.commit()


async def create_indexes(session: AsyncSession):
    """Step 6: Create indexes for better query performance."""
    print("\nStep 6: Creating indexes...")

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_parts_part_name_id ON parts(part_name_id)",
        "CREATE INDEX IF NOT EXISTS idx_parts_material_id ON parts(material_id)",
        "CREATE INDEX IF NOT EXISTS idx_parts_machine_tonnage_id ON parts(machine_tonnage_id)",
        "CREATE INDEX IF NOT EXISTS idx_parts_mold_type_id ON parts(mold_type_id)",
        "CREATE INDEX IF NOT EXISTS idx_quotes_material_id ON quotes(material_id)",
        "CREATE INDEX IF NOT EXISTS idx_quotes_machine_tonnage_id ON quotes(machine_tonnage_id)",
        "CREATE INDEX IF NOT EXISTS idx_quotes_mold_type_id ON quotes(mold_type_id)",
        "CREATE INDEX IF NOT EXISTS idx_part_name_dict_name ON part_name_dict(name)",
        "CREATE INDEX IF NOT EXISTS idx_material_dict_code ON material_dict(code)",
        "CREATE INDEX IF NOT EXISTS idx_machine_tonnage_dict_tonnage ON machine_tonnage_dict(tonnage)",
        "CREATE INDEX IF NOT EXISTS idx_mold_type_dict_code ON mold_type_dict(code)",
    ]

    for idx_sql in indexes:
        await session.execute(text(idx_sql))

    await session.commit()
    print(f"OK Created {len(indexes)} indexes")


async def verify_migration(session: AsyncSession):
    """Step 7: Verify migration results."""
    print("\nStep 7: Verifying migration...")

    # Count dictionary records
    result = await session.execute(text("SELECT COUNT(*) FROM part_name_dict"))
    part_name_count = result.scalar()
    print(f"  - Part names: {part_name_count}")

    result = await session.execute(text("SELECT COUNT(*) FROM material_dict"))
    material_count = result.scalar()
    print(f"  - Materials: {material_count}")

    result = await session.execute(text("SELECT COUNT(*) FROM machine_tonnage_dict"))
    tonnage_count = result.scalar()
    print(f"  - Machine tonnages: {tonnage_count}")

    result = await session.execute(text("SELECT COUNT(*) FROM mold_type_dict"))
    mold_count = result.scalar()
    print(f"  - Mold types: {mold_count}")

    # Count linked records
    result = await session.execute(text("SELECT COUNT(*) FROM parts WHERE part_name_id IS NOT NULL"))
    parts_linked = result.scalar()
    print(f"  - Parts linked to part names: {parts_linked}")

    result = await session.execute(text("SELECT COUNT(*) FROM parts WHERE material_id IS NOT NULL"))
    parts_material_linked = result.scalar()
    print(f"  - Parts linked to materials: {parts_material_linked}")

    print("\nOK Migration verification complete")


async def run_migration():
    """Run the complete migration."""
    print("=" * 60)
    print("DATABASE MIGRATION: Dictionary Tables")
    print("=" * 60)

    async with async_session_maker() as session:
        try:
            await create_tables(session)
            await insert_standard_data(session)
            await extract_existing_data(session)
            await add_foreign_key_columns(session)
            await migrate_data_relationships(session)
            await create_indexes(session)
            await verify_migration(session)

            print("\n" + "=" * 60)
            print("OK MIGRATION COMPLETED SUCCESSFULLY")
            print("=" * 60)

        except Exception as e:
            print(f"\nERROR Migration failed: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
