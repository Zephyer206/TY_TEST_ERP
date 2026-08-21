"""Explicit part display grouping tables

Revision ID: 20260730_explicit_part_grouping
Revises: multiple heads merge
Create Date: 2026-07-30

Stage 2: Explicit left/right and shared-source grouping with user confirmation.
No inference from names, suffixes, or Excel text—user actions must be explicit.
Source metadata (sheet/row) preserved as read-only audit trail.

Merges ten existing heads into unified chain.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260730_explicit_part_grouping'
down_revision = (
    '001_initial',
    '20260707_customer_price_system',
    'add_parts_customer_id',
    'clarify20260620c',
    'mbp0002_parts_material_name',
    'nom005quotes_nomination_status',
    'sales_pricing_engine_v1',
    'v10_canonical_lv1_lv4',
    'v14_dies_architecture_refactor',
    'v6_shopfloor_execution',
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create part_display_group_defs table
    op.create_table(
        'part_display_group_defs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_type', sa.String(length=50), nullable=False, comment='left_right or shared_source'),
        sa.Column('group_key', sa.String(length=200), nullable=False, comment='Stable display key for frontend'),
        sa.Column('display_name', sa.String(length=200), nullable=True, comment='Optional user-friendly name'),
        sa.Column('source_sheet', sa.String(length=100), nullable=True, comment='Source Excel sheet (read-only metadata)'),
        sa.Column('source_rows', sa.String(length=200), nullable=True, comment='Source Excel row numbers (read-only metadata)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_key', name='uq_part_display_group_def_key'),
    )
    op.create_index('ix_part_display_group_defs_group_type', 'part_display_group_defs', ['group_type'])
    op.create_index('ix_part_display_group_defs_group_key', 'part_display_group_defs', ['group_key'])
    op.create_index('ix_part_display_group_defs_is_active', 'part_display_group_defs', ['is_active'])

    # Create part_display_group_members table
    op.create_table(
        'part_display_group_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('part_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.String(length=20), nullable=True, comment='left/right for left_right groups'),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0', comment='Display order within group'),
        sa.Column('source_row', sa.Integer(), nullable=True, comment='Source Excel row (read-only metadata)'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['group_id'], ['part_display_group_defs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['part_id'], ['parts.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('part_id', name='uq_part_display_group_member_part'),
    )
    op.create_index('ix_part_display_group_members_group_id', 'part_display_group_members', ['group_id'])
    op.create_index('ix_part_display_group_members_part_id', 'part_display_group_members', ['part_id'])

    # Create shared_field_group_defs table
    op.create_table(
        'shared_field_group_defs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_key', sa.String(length=200), nullable=False, comment='Stable key for field sharing scope'),
        sa.Column('display_name', sa.String(length=200), nullable=True),
        sa.Column('shares_material', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('shares_thickness', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('shares_width', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('shares_pitch', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('shares_cavity', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('source_sheet', sa.String(length=100), nullable=True, comment='Source Excel sheet (read-only metadata)'),
        sa.Column('source_rows', sa.String(length=200), nullable=True, comment='Source Excel row numbers (read-only metadata)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_key', name='uq_shared_field_group_def_key'),
    )
    op.create_index('ix_shared_field_group_defs_group_key', 'shared_field_group_defs', ['group_key'])
    op.create_index('ix_shared_field_group_defs_is_active', 'shared_field_group_defs', ['is_active'])

    # Create shared_field_group_members table
    op.create_table(
        'shared_field_group_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('part_id', sa.Integer(), nullable=True),
        sa.Column('tooling_id', sa.Integer(), nullable=True),
        sa.Column('source_row', sa.Integer(), nullable=True, comment='Source Excel row (read-only metadata)'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['group_id'], ['shared_field_group_defs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['part_id'], ['parts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tooling_id'], ['tooling.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_shared_field_group_members_group_id', 'shared_field_group_members', ['group_id'])
    op.create_index('ix_shared_field_group_members_part_id', 'shared_field_group_members', ['part_id'])
    op.create_index('ix_shared_field_group_members_tooling_id', 'shared_field_group_members', ['tooling_id'])


def downgrade() -> None:
    op.drop_index('ix_shared_field_group_members_tooling_id', table_name='shared_field_group_members')
    op.drop_index('ix_shared_field_group_members_part_id', table_name='shared_field_group_members')
    op.drop_index('ix_shared_field_group_members_group_id', table_name='shared_field_group_members')
    op.drop_table('shared_field_group_members')

    op.drop_index('ix_shared_field_group_defs_is_active', table_name='shared_field_group_defs')
    op.drop_index('ix_shared_field_group_defs_group_key', table_name='shared_field_group_defs')
    op.drop_table('shared_field_group_defs')

    op.drop_index('ix_part_display_group_members_part_id', table_name='part_display_group_members')
    op.drop_index('ix_part_display_group_members_group_id', table_name='part_display_group_members')
    op.drop_table('part_display_group_members')

    op.drop_index('ix_part_display_group_defs_is_active', table_name='part_display_group_defs')
    op.drop_index('ix_part_display_group_defs_group_key', table_name='part_display_group_defs')
    op.drop_index('ix_part_display_group_defs_group_type', table_name='part_display_group_defs')
    op.drop_table('part_display_group_defs')
