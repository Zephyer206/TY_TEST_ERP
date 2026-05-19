"""
阶段五补充：原料单位与辅料消耗逻辑
======================================================================

变更摘要
--------
1. material_batches 表新增 unit 字段：主材默认 kg，辅料可传入桶/升/个等
2. 新增 consume_aux_material 服务函数
3. 新增 POST /api/materials/aux/{qr_uid}/consume 路由

关联 .cursorrules V3.2 §2.2 辅料（AUX）极简管理

极简入库原则（辅料）：
- 辅料不需要分条（不支持 slit 操作）
- 计量单位不固定（可能是 kg / 桶 / 升 / 个）
- 领用即消耗，扫码一卷一码

依赖：v5_material_qr_tracking
执行：alembic upgrade v5b_material_aux_unit
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v5b_material_aux_unit'
down_revision = 'v5_material_qr_tracking'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    print('[v5b-aux] 步骤1: 给 material_batches 新增 unit 字段')
    conn.execute(sa.text("""
        ALTER TABLE material_batches
        ADD COLUMN IF NOT EXISTS unit VARCHAR(10) NOT NULL DEFAULT 'kg';
    """))
    print('[v5b-aux]   unit 字段添加完成（默认值 kg）')
    print('[v5b-aux] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v5b-aux] 回滚：删除 unit 字段')
    conn.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS unit CASCADE;"))
    print('[v5b-aux] 回滚完成')
