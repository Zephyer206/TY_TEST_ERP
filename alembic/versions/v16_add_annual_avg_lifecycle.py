"""v16_add_annual_avg_lifecycle

Revision ID: v16
Revises: v15_add_sdr_drawing_path
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'v16'
down_revision = 'v15_add_sdr_drawing_path'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('quotes') as batch:
        batch.add_column(sa.Column('annual_avg', sa.Numeric(precision=12, scale=2), nullable=True))
        batch.add_column(sa.Column('lifecycle_years', sa.Numeric(precision=5, scale=2), nullable=True))


def downgrade():
    with op.batch_alter_table('quotes') as batch:
        batch.drop_column('annual_avg')
        batch.drop_column('lifecycle_years')
