"""Migration API endpoints for running database migrations."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.core.config import settings

router = APIRouter(prefix="/migrations", tags=["Migrations"])


def _require_legacy_migration_api(current_user: CurrentUser) -> None:
    """Protect the legacy migration endpoints during the transition period."""
    if not settings.ENABLE_LEGACY_MIGRATION_API:
        raise HTTPException(
            status_code=404,
            detail="Legacy migration API is disabled; use Alembic from the deployment environment",
        )
    require_role(current_user, min_level=4)


@router.post("/run-all")
async def run_all_migrations(db: DbSession, current_user: CurrentUser) -> dict:
    """Run all price management migrations."""

    _require_legacy_migration_api(current_user)

    results = []

    try:
        # Migration 1: Create treatment_dict table
        sql1 = """
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

        CREATE INDEX IF NOT EXISTS idx_treatment_dict_active ON treatment_dict(is_active);

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
        """
        await db.execute(text(sql1))
        results.append("✅ treatment_dict table created")

        # Migration 2: Create customer_material_prices table
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
        await db.execute(text(sql2))
        results.append("✅ customer_material_prices table created")

        # Migration 3: Create customer_treatment_prices table
        sql3 = """
        CREATE TABLE IF NOT EXISTS customer_treatment_prices (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            treatment_name VARCHAR(100) NOT NULL,
            rate NUMERIC(10,4) NOT NULL,
            calc_mode VARCHAR(20) NOT NULL DEFAULT 'manual',
            unit VARCHAR(20) NOT NULL DEFAULT '元/件',
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
        await db.execute(text(sql3))
        results.append("✅ customer_treatment_prices table created")

        # Migration 4: Create price_adjustments table
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
        await db.execute(text(sql4))
        results.append("✅ price_adjustments table created")

        # Migration 5: Migrate material_base_prices data (if table exists)
        sql5_check = "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'material_base_prices')"
        result = await db.execute(text(sql5_check))
        table_exists = result.scalar()

        if table_exists:
            sql5 = """
            INSERT INTO customer_material_prices (customer_id, material_id, unit_price, scrap_price, effective_date, created_at)
            SELECT
                1 as customer_id,
                material_id,
                base_price as unit_price,
                scrap_price,
                '2024-01-01'::date as effective_date,
                NOW() as created_at
            FROM material_base_prices
            WHERE base_price > 0
            ON CONFLICT (customer_id, material_id, effective_date) DO NOTHING;
            """
            await db.execute(text(sql5))
            results.append("✅ Migrated material_base_prices data")
        else:
            results.append("⚠️ material_base_prices table not found, skipped")

        # Migration 6: Migrate treatment_dicts data (if table exists)
        sql6_check = "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'treatment_dicts')"
        result = await db.execute(text(sql6_check))
        table_exists = result.scalar()

        if table_exists:
            sql6 = """
            INSERT INTO treatment_dict (name, calc_mode, default_rate, unit, is_active, sort_order, created_at)
            SELECT
                name,
                'manual' as calc_mode,
                COALESCE(default_cost, 0) as default_rate,
                '元/件' as unit,
                TRUE as is_active,
                COALESCE(display_order, 0) as sort_order,
                NOW() as created_at
            FROM treatment_dicts
            ON CONFLICT (name) DO NOTHING;
            """
            await db.execute(text(sql6))
            results.append("✅ Migrated treatment_dicts data")
        else:
            results.append("⚠️ treatment_dicts table not found, skipped")

        await db.commit()

        return {
            "success": True,
            "message": "All migrations completed successfully",
            "results": results
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@router.get("/status")
async def check_migration_status(db: DbSession, current_user: CurrentUser) -> dict:
    """Check if price management tables exist."""

    _require_legacy_migration_api(current_user)

    tables = ['treatment_dict', 'customer_material_prices',
              'customer_treatment_prices', 'price_adjustments']

    status = {}
    for table in tables:
        sql = f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')"
        result = await db.execute(text(sql))
        status[table] = result.scalar()

    return {
        "tables": status,
        "all_exist": all(status.values())
    }
