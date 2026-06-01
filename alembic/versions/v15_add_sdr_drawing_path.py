"""v15_add_sdr_drawing_path

业务提交图纸后，开发填写技术参数的SDR图纸路径字段。

Revision ID: v15
Revises: nom004quotes_parts_mold_split
Create Date: 2026-05-25

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'v15_add_sdr_drawing_path'
down_revision = 'nom004quotes_parts_mold_split'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('quotes', sa.Column('sdr_drawing_path', sa.String(500), nullable=True, comment='SDR分析图纸路径'))


def downgrade():
    op.drop_column('quotes', 'sdr_drawing_path')
