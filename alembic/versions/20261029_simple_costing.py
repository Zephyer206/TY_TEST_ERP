"""Add canonical part treatments and immutable simple costing, without rewriting data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261029_simple_costing'
down_revision = '20261025_workbench_assignments'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'surface_treatment' not in {c['name'] for c in inspector.get_columns('parts')}:
        op.add_column('parts', sa.Column('surface_treatment', JSONB(), nullable=True))
    if inspector.has_table('quote_groups') and 'surface_rule_snapshot' not in {c['name'] for c in inspector.get_columns('quote_groups')}:
        op.add_column('quote_groups', sa.Column('surface_rule_snapshot', sa.JSON(), nullable=True))
    if inspector.has_table('costing_items') and 'source_reference' not in {c['name'] for c in inspector.get_columns('costing_items')}:
        op.add_column('costing_items',sa.Column('source_reference',sa.JSON(),nullable=True))
    inspector.clear_cache()
    definitions = [
        ('costing_tasks', [sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(150), nullable=False),
            sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=False, index=True),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False)]),
        ('costing_items', [sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('task_id', sa.Integer(), sa.ForeignKey('costing_tasks.id'), nullable=False, index=True),
            sa.Column('alias_id', sa.Integer(), sa.ForeignKey('part_customer_aliases.id'), nullable=False),
            sa.Column('part_id', sa.Integer(), sa.ForeignKey('parts.id'), nullable=False),
            sa.Column('tooling_id', sa.Integer(), sa.ForeignKey('tooling.id'), nullable=False),
            sa.Column('spec_id', sa.Integer(), sa.ForeignKey('part_tooling_specs.id'), nullable=True),
            sa.Column('scheme_key', sa.String(80), nullable=False),
            sa.Column('source_reference',sa.JSON(),nullable=True),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('task_id', 'alias_id', 'tooling_id', 'scheme_key', name='uq_costing_item_scheme')]),
        ('costing_revisions', [sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('item_id', sa.Integer(), sa.ForeignKey('costing_items.id'), nullable=False, index=True),
            sa.Column('revision_no', sa.Integer(), nullable=False),
            sa.Column('request_id', sa.String(100), nullable=False),
            sa.Column('payload_hash', sa.String(64), nullable=False),
            sa.Column('inputs', sa.JSON(), nullable=False), sa.Column('result', sa.JSON(), nullable=False),
            sa.Column('context', sa.JSON(), nullable=False),
            sa.Column('reason', sa.String(500), nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('item_id', 'revision_no', name='uq_costing_revision'),
            sa.UniqueConstraint('item_id', 'request_id', name='uq_costing_request')]),
    ]
    for name, columns in definitions:
        if inspector.has_table(name):
            expected = {c.name for c in columns if isinstance(c, sa.Column)}
            if {c['name'] for c in inspector.get_columns(name)} != expected:
                raise RuntimeError('Installed costing schema differs: ' + name)
            continue
        op.create_table(name, *columns)


def downgrade():
    # No automatic data-destroying downgrade. Feature rollback keeps recorded costs.
    raise RuntimeError('Costing stores business history; use a separately reviewed data-preserving rollback.')
