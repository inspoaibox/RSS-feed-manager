"""Backfill missing article published time.

Revision ID: 036
Revises: 035
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE articles SET published_at = created_at WHERE published_at IS NULL")


def downgrade() -> None:
    pass
