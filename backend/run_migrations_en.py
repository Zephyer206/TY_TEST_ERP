"""Run migrations - English SQL only to avoid encoding issues."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from sqlalchemy import text
from app.database import engine


async def run_migrations():
    """Run all price management migrations."""

    try:
        async with engine.begin() as conn:
            # Migration 1: Create treatment_dict table
            print("Running migration 1: treatment_dict...")
            sql1 = """
            CREATE TABLE IF NOT EXISTS treatment_dict (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                calc_mode VARCHAR(20) NOT NULL DEFAULT 'manual',
                default_rate NUMERIC(10,4) NOT NULL DEFAULT 0,
                unit VARCHAR(20) NOT NULL DEFAULT 'yuan/piece',
                is_active BOOLEAN DEFAULT TRUE,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                CONSTRAINT chk_calc_mode CHECK (calc_mode IN ('manual', 'net_weight')),
                CONSTRAINT chk_default_rate CHECK (default_rate >= 0)
            );

            CREATE INDEX IF NOT EXISTS idx_treatment_dict_active ON treatment_dict(is_active);
            """
            await conn.execute(text(sql1))
            print("OK: treatment_dict table created")

            # Migration 2: Create customer_material_prices table
            print("\nRunning migration 2: customer_material_prices...")
            sql2 = """
            CREATE TABLE IF NOT EXISTS customer_material_prices (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                material_id INTEGER NOT NULL,
                unit_price NUMERIC(10,4) NOT NULL,
                scrap_price NUMERIC(10,4),
                effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                CONSTRAINT chk_unit_price CHECK (unit_price >= 0),
                CONSTRAINT chk_scrap_price CHECK (scrap_price IS NULL OR scrap_price >= 0),
                CONSTRAINT uq_customer_material_date UNIQUE (customer_id, material_id, effective_date)
            );

            CREATE INDEX IF NOT EXISTS idx_cmp_customer ON customer_material_prices(customer_id);
            CREATE INDEX IF NOT EXISTS idx_cmp_material ON customer_material_prices(material_id);
            CREATE INDEX IF NOT EXISTS idx_cmp_date ON customer_material_prices(effective_date DESC);
            """
            await conn.execute(text(sql2))
            print("OK: customer_material_prices table created")

            # Migration 3: Create customer_treatment_prices table
            print("\nRunning migration 3: customer_treatment_prices...")
            sql3 = """
            CREATE TABLE IF NOT EXISTS customer_treatment_prices (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                treatment_name VARCHAR(100) NOT NULL,
                rate NUMERIC(10,4) NOT NULL,
                calc_mode VARCHAR(20) NOT NULL DEFAULT 'manual',
                unit VARCHAR(20) NOT NULL DEFAULT 'yuan/piece',
                effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                CONSTRAINT chk_ctp_rate CHECK (rate >= 0),
                CONSTRAINT chk_ctp_calc_mode CHECK (calc_mode IN ('manual', 'net_weight')),
                CONSTRAINT uq_customer_treatment_date UNIQUE (customer_id, treatment_name, effective_date)
            );

            CREATE INDEX IF NOT EXISTS idx_ctp_customer ON customer_treatment_prices(customer_id);
            CREATE INDEX IF NOT EXISTS idx_ctp_treatment ON customer_treatment_prices(treatment_name);
            CREATE INDEX IF NOT EXISTS idx_ctp_date ON customer_treatment_prices(effective_date DESC);
            """
            await conn.execute(text(sql3))
            print("OK: customer_treatment_prices table created")

            # Migration 4: Create price_adjustments table
            print("\nRunning migration 4: price_adjustments...")
            sql4 = """
            CREATE TABLE IF NOT EXISTS price_adjustments (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                part_id INTEGER,
                material_id INTEGER,
                treatment_name VARCHAR(100),
                adjustment_type VARCHAR(20) NOT NULL,
                old_price NUMERIC(10,4),
                new_price NUMERIC(10,4) NOT NULL,
                reason TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                requested_by INTEGER NOT NULL,
                requested_at TIMESTAMP DEFAULT NOW(),
                reviewed_by INTEGER,
                reviewed_at TIMESTAMP,
                review_notes TEXT,
                effective_date DATE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                CONSTRAINT chk_adjustment_type CHECK (adjustment_type IN ('material', 'treatment', 'part')),
                CONSTRAINT chk_status CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
                CONSTRAINT chk_prices CHECK (old_price IS NULL OR old_price >= 0),
                CONSTRAINT chk_new_price CHECK (new_price >= 0)
            );

            CREATE INDEX IF NOT EXISTS idx_pa_customer ON price_adjustments(customer_id);
            CREATE INDEX IF NOT EXISTS idx_pa_status ON price_adjustments(status);
            CREATE INDEX IF NOT EXISTS idx_pa_requested ON price_adjustments(requested_at DESC);
            """
            await conn.execute(text(sql4))
            print("OK: price_adjustments table created")

            # Insert seed data for treatment_dict
            print("\nInserting seed data...")
            seed_sql = """
            INSERT INTO treatment_dict (name, calc_mode, default_rate, unit, is_active, sort_order) VALUES
            ('Heat Treatment', 'manual', 1.50, 'yuan/piece', TRUE, 1),
            ('Zinc Plating', 'manual', 2.00, 'yuan/piece', TRUE, 2),
            ('Blackening', 'manual', 1.20, 'yuan/piece', TRUE, 3),
            ('Painting', 'manual', 2.50, 'yuan/piece', TRUE, 4),
            ('Tape Application', 'manual', 0.80, 'yuan/piece', TRUE, 5),
            ('Anodizing', 'manual', 3.00, 'yuan/piece', TRUE, 6),
            ('Phosphating', 'manual', 1.80, 'yuan/piece', TRUE, 7),
            ('Die Cast Coating', 'net_weight', 15.00, 'yuan/kg', TRUE, 8),
            ('Nickel Plating', 'manual', 3.50, 'yuan/piece', TRUE, 9),
            ('Dacromet Coating', 'manual', 4.00, 'yuan/piece', TRUE, 10)
            ON CONFLICT (name) DO NOTHING;
            """
            await conn.execute(text(seed_sql))
            print("OK: Seed data inserted")

        print("\nAll migrations completed successfully!")
        return True

    except Exception as e:
        print(f"\nMigration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_migrations())
    sys.exit(0 if success else 1)
