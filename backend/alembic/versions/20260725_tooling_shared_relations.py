"""Create source-backed shared mold relations."""

from typing import Sequence, Union

from alembic import op


revision: str = "20260725_tooling_shared_relations"
down_revision: Union[str, Sequence[str], None] = "47d6fa6942ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tooling_shared_relations (
            id SERIAL PRIMARY KEY,
            tooling_id INTEGER NOT NULL REFERENCES tooling(id) ON DELETE CASCADE,
            related_tooling_id INTEGER NOT NULL REFERENCES tooling(id) ON DELETE CASCADE,
            relation_type VARCHAR(30) NOT NULL DEFAULT 'SHARED_MOLD',
            relation_scope VARCHAR(20) NOT NULL DEFAULT 'set',
            source_sheet VARCHAR(255),
            source_row INTEGER,
            source_note TEXT,
            confidence VARCHAR(30) NOT NULL DEFAULT 'EXPLICIT_NOTE',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_tooling_shared_relations_distinct CHECK (tooling_id <> related_tooling_id),
            CONSTRAINT uq_tooling_shared_relations_pair UNIQUE (tooling_id, related_tooling_id, relation_type)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tooling_shared_relations_tooling_id "
        "ON tooling_shared_relations (tooling_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tooling_shared_relations_related_tooling_id "
        "ON tooling_shared_relations (related_tooling_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tooling_shared_relations")
