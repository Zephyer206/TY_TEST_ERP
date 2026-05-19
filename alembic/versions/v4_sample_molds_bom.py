"""
阶段二：打样与工艺定型流 —— 数据库迁移
======================================================================

变更摘要
--------
1. molds（模具台账表）：记录模具身份、生命周期、改模断代
2. bom_routings（工艺路线表）：工序顺序与模具绑定
3. sample_tasks（打样与 PPAP 三方会签表）：技术/质量/业务三部门签到

关联 .cursorrules V3.2 §2.3 机台维修两扫制 §2.4 样件物流与反馈

依赖：v3part_status_lifecycle（head）
执行：alembic upgrade head
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v4_sample_molds_bom'
down_revision = 'v3part_status_lifecycle'
branch_labels = None
depends_on = None


def upgrade():
    """
    创建 molds / bom_routings / sample_tasks 三张表及索引。

    注意：PostgreSQL 在 DDL 执行时内部已开启事务，
    Alembic 的 context.begin_transaction() 会自动包含所有 DDL。
    """
    conn = op.get_bind()

    # ── 1. molds 表 ─────────────────────────────────────────────────
    print('[v4-sample-molds] 步骤1: 创建 molds 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS molds (
            id                          SERIAL PRIMARY KEY,
            mold_number                VARCHAR(100) UNIQUE NOT NULL,
                -- 本厂产品编号 = 模具唯一编号 = 内部零件号 (part_number)
            part_id                    INTEGER REFERENCES parts(id),
                -- 关联零件主档（未匹配时为 NULL）
            mold_type                  VARCHAR(50),
                -- 模具类型
            mold_set_count             INTEGER DEFAULT 1,
                -- 物理模具套数 / 工序数（提取自'模数'列，如"1套"→1）
            cavity_count               INTEGER DEFAULT 1,
                -- 一出几（从'备注'/'用料规格'文本中用正则提取，如"1出2"→2）
            press_tonnage              VARCHAR(50),
                -- 参考冲床吨位（直接映射'参考冲床吨位'列）
            lifecycle_status            VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
                -- AVAILABLE / IN_USE / MAINTENANCE / MODIFYING / CONVERTED / SCRAPPED
            converted_to_mold_id       INTEGER REFERENCES molds(id),
                -- 改模后指向新款模具，旧模标记 CONVERTED
            remarks                    TEXT,
                -- 备注（原始文本，用于 cavity_count 等字段的后续提取）
            created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at                 TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_molds_status
        ON molds(lifecycle_status) WHERE lifecycle_status != 'SCRAPPED';
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_molds_part_id
        ON molds(part_id) WHERE part_id IS NOT NULL;
    """))
    print('[v4-sample-molds]   molds 表 + 索引创建完成')

    # ── 2. bom_routings 表 ─────────────────────────────────────────
    print('[v4-sample-molds] 步骤2: 创建 bom_routings 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bom_routings (
            id                          SERIAL PRIMARY KEY,
            part_id                     INTEGER NOT NULL
                                           REFERENCES parts(id) ON DELETE CASCADE,
            step_seq                    INTEGER NOT NULL,
            process_name                VARCHAR(100) NOT NULL,
            process_code                VARCHAR(50),
            mold_id                     INTEGER REFERENCES molds(id),
            is_outsource               BOOLEAN NOT NULL DEFAULT FALSE,
            outsource_vendor_id         INTEGER,
            labor_minutes               NUMERIC(8,2) DEFAULT 0,
            is_critical                 BOOLEAN DEFAULT FALSE,
            remarks                     TEXT,
            created_at                  TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at                  TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_bom_part_step UNIQUE (part_id, step_seq)
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_bom_part_seq
        ON bom_routings(part_id, step_seq DESC);
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_bom_mold_id
        ON bom_routings(mold_id) WHERE mold_id IS NOT NULL;
    """))
    print('[v4-sample-molds]   bom_routings 表 + 索引创建完成')

    # ── 3. sample_tasks 表 ──────────────────────────────────────────
    print('[v4-sample-molds] 步骤3: 创建 sample_tasks 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sample_tasks (
            id                          SERIAL PRIMARY KEY,
            part_id                     INTEGER NOT NULL
                                           REFERENCES parts(id) ON DELETE CASCADE,
            quote_id                    INTEGER REFERENCES quotes(id),
            sample_type                 VARCHAR(30) DEFAULT 'FIRST_SAMPLE',
            sample_fee                  NUMERIC(10,4) DEFAULT 0,
            proof_file_path             TEXT,
            tech_sign_by                INTEGER REFERENCES users(id),
            tech_sign_at                TIMESTAMP,
            qa_sign_by                  INTEGER REFERENCES users(id),
            qa_sign_at                  TIMESTAMP,
            sales_sign_by               INTEGER REFERENCES users(id),
            sales_sign_at               TIMESTAMP,
            task_status                 VARCHAR(20) NOT NULL DEFAULT 'IN_PROGRESS',
            mass_prod_activated_by      INTEGER REFERENCES users(id),
            mass_prod_activated_at      TIMESTAMP,
            related_mold_id             INTEGER REFERENCES molds(id),
            remarks                     TEXT,
            created_at                  TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at                  TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_sample_part_id
        ON sample_tasks(part_id DESC, created_at DESC);
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_sample_status
        ON sample_tasks(task_status) WHERE task_status = 'IN_PROGRESS';
    """))
    print('[v4-sample-molds]   sample_tasks 表 + 索引创建完成')

    print('[v4-sample-molds] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v4-sample-molds] 回滚：删除三张表（按依赖顺序）')
    conn.execute(sa.text("DROP TABLE IF EXISTS sample_tasks CASCADE;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS bom_routings CASCADE;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS molds CASCADE;"))
    print('[v4-sample-molds] 三张表已删除')
    print('[v4-sample-molds] ======== 回滚完成 ========')
