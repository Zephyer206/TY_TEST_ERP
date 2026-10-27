"""Persist workbench ownership independently from source business states."""

from alembic import op
import sqlalchemy as sa

revision = "20261025_workbench_assignments"
down_revision = "20261022_product_box_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Local acceptance may apply this additive domain alone while unrelated
    # feature migrations remain pending. A later normal Alembic upgrade must
    # recognize the identical installed schema without removing any records.
    inspector = sa.inspect(op.get_bind())
    expected = {
        "workbench_assignments": {"id", "task_key", "source_revision", "assignee_id", "state", "version", "updated_by", "updated_at"},
        "workbench_assignment_events": {"id", "task_key", "source_revision", "action", "version", "actor_id", "actor_name", "previous_assignee_id", "assignee_id", "created_at"},
    }
    installed = set(inspector.get_table_names()).intersection(expected)
    if installed:
        if installed != set(expected):
            raise RuntimeError("Workbench schema is partially installed; inspect it before retrying.")
        for table, columns in expected.items():
            if {column["name"] for column in inspector.get_columns(table)} != columns:
                raise RuntimeError("Installed workbench schema does not match this migration.")
        if not any(set(item["column_names"]) == {"task_key"} for item in inspector.get_unique_constraints("workbench_assignments")):
            raise RuntimeError("Installed workbench schema is missing unique task ownership.")
        return
    op.create_table(
        "workbench_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_key", sa.String(240), nullable=False, unique=True),
        sa.Column("source_revision", sa.String(300), nullable=False),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_workbench_assignment_version"),
        sa.CheckConstraint("state IN ('unassigned', 'claimed', 'assigned')", name="ck_workbench_assignment_state"),
    )
    op.create_index("ix_workbench_assignments_assignee_id", "workbench_assignments", ["assignee_id"])
    op.create_table(
        "workbench_assignment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_key", sa.String(240), nullable=False),
        sa.Column("source_revision", sa.String(300), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_name", sa.String(100), nullable=False),
        sa.Column("previous_assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workbench_assignment_events_task_key", "workbench_assignment_events", ["task_key"])


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("workbench_assignments", "workbench_assignment_events"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} LIMIT 1)")).scalar():
            raise RuntimeError("Refusing to remove workbench ownership or audit records.")
    op.drop_table("workbench_assignment_events")
    op.drop_table("workbench_assignments")
