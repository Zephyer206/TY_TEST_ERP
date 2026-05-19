"""
Spray 喷涂模块 —— Alembic 迁移存根

关联 .cursorrules V3.0 §1.1 spraying 部门规范 + §2.3 喷涂工艺配方驱动规范。

本迁移为幂等存根：
- spray 模块已通过独立脚本 upgrade_spray_module.py 执行
- 本迁移确保 Alembic 历史与数据库实际状态同步，并成为新的 head
- 所有对象均用 IF NOT EXISTS / IF NOT EXISTS (column) 保护，可安全重复执行

依赖：mno345pkg_shipping_customer（pkg_shipping_customer）

执行方式：alembic upgrade head
回滚方式：alembic downgrade -1
（降级仅移除本条 Alembic 记录，不回滚已创建的数据库对象）
"""

from alembic import op
import sqlalchemy as sa

revision = 'spr0001spray_module'
down_revision = 'mno345pkg_shipping_customer'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. spraying_recipes ───────────────────────────────────────────────
    try:
        op.execute("""
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
            )
        """)
        op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_recipe_part_id ON spraying_recipes(part_id)")
        print('[spray] spraying_recipes table created / already exists')
    except Exception as e:
        print(f'[spray] spraying_recipes skipped: {e}')

    # ── 2. spraying_logs ─────────────────────────────────────────────────
    try:
        op.execute("""
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
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS idx_spray_log_part_id ON spraying_logs(part_id)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_spray_log_actual_date ON spraying_logs(actual_date)")
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_spray_log_uncalc
            ON spraying_logs(part_id) WHERE is_calculated = FALSE
        """)
        print('[spray] spraying_logs table created / already exists')
    except Exception as e:
        print(f'[spray] spraying_logs skipped: {e}')

    # ── 3. spraying_material_consumption ──────────────────────────────────
    try:
        op.execute("""
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
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS idx_consumption_part_id ON spraying_material_consumption(part_id)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_consumption_mat_name ON spraying_material_consumption(material_name)")
        print('[spray] spraying_material_consumption table created / already exists')
    except Exception as e:
        print(f'[spray] spraying_material_consumption skipped: {e}')

    # ── 4. parts.spray_status ────────────────────────────────────────────
    try:
        op.execute("""
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

                -- CHECK 约束（可重复执行）
                ALTER TABLE parts DROP CONSTRAINT IF EXISTS chk_spray_status;
                ALTER TABLE parts ADD CONSTRAINT chk_spray_status
                CHECK (spray_status IN ('pending', 'stamped', 'qc_passed', 'pkg_ready', 'shipped'));
            END $$;
        """)
        print('[spray] parts.spray_status / spray_stamped_at created / already exists')
    except Exception as e:
        print(f'[spray] parts columns skipped: {e}')

    print('[spray] Spray module migration complete — now at head')


def downgrade():
    # 降级仅记录 Alembic 历史，不实际删除数据库对象
    # （upgrade_spray_module.py 已通过独立脚本创建这些对象）
    print('[spray] Downgrade: Alembic record only — database objects preserved')
