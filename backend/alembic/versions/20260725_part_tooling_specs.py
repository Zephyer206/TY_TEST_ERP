"""Store source-backed TWP options per part and tooling."""

from typing import Sequence, Union

from alembic import op


revision: str = "20260725_part_tooling_specs"
down_revision: Union[str, Sequence[str], None] = "20260725_tooling_shared_relations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS part_tooling_specs (
            id SERIAL PRIMARY KEY,
            part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
            tooling_id INTEGER NOT NULL REFERENCES tooling(id) ON DELETE CASCADE,
            spec_twph VARCHAR(100),
            thickness NUMERIC(10, 3),
            width NUMERIC(10, 3),
            pitch NUMERIC(10, 3),
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            source_sheet VARCHAR(200),
            source_row INTEGER,
            source_note TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_part_tooling_specs_part_id "
        "ON part_tooling_specs (part_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_part_tooling_specs_tooling_id "
        "ON part_tooling_specs (tooling_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_part_tooling_specs_primary "
        "ON part_tooling_specs (part_id) WHERE is_primary"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS part_tooling_specs")
