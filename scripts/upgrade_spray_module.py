"""
Spray module database migration.
Run: py upgrade_spray_module.py
Rollback: py upgrade_spray_module.py --rollback
"""

import sys
import psycopg2

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432"
}

UP_SQL = """
-- ==============================================================
-- 1. spraying_recipes
-- ==============================================================
CREATE TABLE IF NOT EXISTS spraying_recipes (
    id                  SERIAL PRIMARY KEY,
    part_id             INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    sand_material       VARCHAR(200) NOT NULL DEFAULT '',
    sand_dosage         NUMERIC(10,4) NOT NULL DEFAULT 0,
    coating_material    VARCHAR(200) NOT NULL DEFAULT '',
    coating_dosage      NUMERIC(10,4) NOT NULL DEFAULT 0,
    surface_type        VARCHAR(30) NOT NULL DEFAULT 'single',
    coating_color       VARCHAR(100) DEFAULT '',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_by          INTEGER REFERENCES users(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_recipe_part_id ON spraying_recipes(part_id);

-- ==============================================================
-- 2. spraying_logs
-- ==============================================================
CREATE TABLE IF NOT EXISTS spraying_logs (
    id                  SERIAL PRIMARY KEY,
    part_id             INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    quantity            INTEGER NOT NULL DEFAULT 0,
    operator_id         INTEGER REFERENCES users(id),
    manager_id          INTEGER REFERENCES users(id),
    actual_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    is_calculated       BOOLEAN NOT NULL DEFAULT FALSE,
    remark              TEXT DEFAULT '',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_spray_log_part_id    ON spraying_logs(part_id);
CREATE INDEX IF NOT EXISTS idx_spray_log_actual_date ON spraying_logs(actual_date);
CREATE INDEX IF NOT EXISTS idx_spray_log_uncalc     ON spraying_logs(is_calculated) WHERE is_calculated = FALSE;

-- ==============================================================
-- 3. spraying_material_consumption
-- ==============================================================
CREATE TABLE IF NOT EXISTS spraying_material_consumption (
    id                  SERIAL PRIMARY KEY,
    part_id             INTEGER NOT NULL REFERENCES parts(id),
    recipe_id           INTEGER REFERENCES spraying_recipes(id),
    log_id              INTEGER REFERENCES spraying_logs(id) ON DELETE CASCADE,
    material_name       VARCHAR(200) NOT NULL,
    material_type       VARCHAR(30) NOT NULL,
    consumed_qty        NUMERIC(12,4) NOT NULL DEFAULT 0,
    unit_cost           NUMERIC(10,4) NOT NULL DEFAULT 0,
    total_cost          NUMERIC(12,4) NOT NULL DEFAULT 0,
    calculated_at       TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_consumption_part_id  ON spraying_material_consumption(part_id);
CREATE INDEX IF NOT EXISTS idx_consumption_mat_name ON spraying_material_consumption(material_name);

-- ==============================================================
-- 4. parts columns: spray_status, spray_stamped_at
-- ==============================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'spray_status'
    ) THEN
        ALTER TABLE parts ADD COLUMN spray_status VARCHAR(30) NOT NULL DEFAULT 'pending';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'spray_stamped_at'
    ) THEN
        ALTER TABLE parts ADD COLUMN spray_stamped_at TIMESTAMP;
    END IF;
END $$;

-- ==============================================================
-- 5. spray_status CHECK constraint
-- ==============================================================
ALTER TABLE parts DROP CONSTRAINT IF EXISTS chk_spray_status;
ALTER TABLE parts ADD CONSTRAINT chk_spray_status
CHECK (spray_status IN ('pending', 'stamped', 'qc_passed', 'pkg_ready', 'shipped'));
"""

DOWN_SQL = """
ALTER TABLE parts DROP CONSTRAINT IF EXISTS chk_spray_status;
ALTER TABLE parts DROP COLUMN IF EXISTS spray_status;
ALTER TABLE parts DROP COLUMN IF EXISTS spray_stamped_at;
DROP TABLE IF EXISTS spraying_material_consumption;
DROP TABLE IF EXISTS spraying_logs;
DROP TABLE IF EXISTS spraying_recipes;
"""


def run_sql(sql, rollback=False):
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if "--rollback" in sys.argv:
        print("==> Rolling back spray module...")
        run_sql(DOWN_SQL, rollback=True)
    else:
        print("==> Deploying spray module...")
        run_sql(UP_SQL)
        print("==> Spray module deployed successfully!")
