"""
Allow duplicate part_numbers by adding remark field (required).
Migration: v13_allow_duplicate_part_numbers
"""
from alembic import op
import sqlalchemy as sa

revision = 'v13_allow_duplicate_part_numbers'
down_revision = 'v12_inventory_die_architecture'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add remark column (NOT NULL with default)
    op.add_column('parts', sa.Column('remark', sa.String(200), nullable=False, server_default=''))

    # 2. Drop the global unique constraint on part_number
    # PostgreSQL constraint names can be quoted or unquoted
    op.execute("ALTER TABLE parts DROP CONSTRAINT IF EXISTS parts_part_number_key;")

    # 3. Verify the (part_number, version) unique constraint still exists
    op.execute("""
        ALTER TABLE parts ADD CONSTRAINT uq_parts_number_version
        UNIQUE (part_number, version);
    """)

    # 4. Set default remark = internal_name for existing rows (if internal_name is not null)
    op.execute("""
        UPDATE parts SET remark = COALESCE(internal_name, '')
        WHERE remark = '';
    """)

    print('[v13] Added remark column, dropped parts_part_number_key constraint')


def downgrade():
    op.drop_column('parts', 'remark')
    op.execute("""
        ALTER TABLE parts ADD CONSTRAINT parts_part_number_key
        UNIQUE (part_number);
    """)
    print('[v13] Reverted: dropped remark column, restored parts_part_number_key')
