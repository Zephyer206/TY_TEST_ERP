"""Add customer_id to parts table

Revision ID: add_parts_customer_id
Revises:
Create Date: 2026-05-09 08:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_parts_customer_id'
down_revision = 'nom003nomination_price_snapshot'
branch_labels = None
depends_on = None


def upgrade():
    # Add customer_id column to parts table, nullable first (existing parts have no customer)
    op.add_column('parts', sa.Column('customer_id', sa.Integer(), nullable=True))
    # Add FK reference (if tooling_customers table exists)
    # Making it nullable so no data violation
    op.create_foreign_key(
        'fk_parts_customer_id',
        'parts', 'tooling_customers',
        ['customer_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_parts_customer_id', 'parts', type_='foreignkey')
    op.drop_column('parts', 'customer_id')
