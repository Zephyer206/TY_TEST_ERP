"""Persist nonconforming records, source import batches and rework molds."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20261017_nonconforming'
down_revision = '20261009_qg_pricing_costs'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('nonconforming_import_batches',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('source_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('file_name', sa.Text(), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))
    op.create_table('nonconforming_records',
        sa.Column('id', sa.String(120), primary_key=True),
        sa.Column('company', sa.String(20), nullable=False),
        sa.Column('record_no', sa.String(80), nullable=False),
        sa.Column('part_no', sa.String(200), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('quantity_verified', sa.Boolean(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('company', 'record_no', name='uq_nc_company_no'),
        sa.CheckConstraint('quantity >= 0', name='ck_nc_quantity'),
        sa.CheckConstraint('revision >= 1', name='ck_nc_revision'),
        sa.CheckConstraint("company IN ('tianyue','gaibo')", name='ck_nc_company'),
        sa.CheckConstraint("status IN ('pending_confirmation','pending','processing','inspection','closed')", name='ck_nc_status'))
    for name in ['company', 'part_no', 'status']:
        op.create_index(f'ix_nonconforming_records_{name}', 'nonconforming_records', [name])
    op.create_table('nonconforming_rework_molds',
        sa.Column('id', sa.String(120), primary_key=True),
        sa.Column('company', sa.String(20), nullable=False),
        sa.Column('part_no', sa.String(200), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('revision >= 1', name='ck_nc_mold_revision'))
    for name in ['company', 'part_no']:
        op.create_index(f'ix_nonconforming_rework_molds_{name}', 'nonconforming_rework_molds', [name])

def downgrade():
    op.drop_table('nonconforming_rework_molds')
    op.drop_table('nonconforming_records')
    op.drop_table('nonconforming_import_batches')
