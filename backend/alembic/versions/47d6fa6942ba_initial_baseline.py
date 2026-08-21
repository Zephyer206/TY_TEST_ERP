"""initial_baseline

Revision ID: 47d6fa6942ba
Revises: feb2532a66b9
Create Date: 2026-07-20 07:52:03.678908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47d6fa6942ba'
down_revision: Union[str, Sequence[str], None] = 'feb2532a66b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
