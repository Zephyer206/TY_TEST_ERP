"""Make TWP primary uniqueness scoped to (part_id, tooling_id).

Revision ID: 20260727_twp_primary_per_tooling
Revises: 20260725_part_tooling_specs
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260727_twp_primary_per_tooling"
down_revision: Union[str, Sequence[str], None] = "20260725_part_tooling_specs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old part-wide primary constraint
    op.execute(
        "DROP INDEX IF EXISTS uq_part_tooling_specs_primary"
    )
    # Create the new (part_id, tooling_id)-scoped primary constraint
    op.execute(
        """
        CREATE UNIQUE INDEX uq_part_tooling_specs_primary_per_tooling
        ON part_tooling_specs (part_id, tooling_id)
        WHERE is_primary
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uq_part_tooling_specs_primary_per_tooling"
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_part_tooling_specs_primary
        ON part_tooling_specs (part_id)
        WHERE is_primary
        """
    )
