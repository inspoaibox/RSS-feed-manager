"""Allow empty custom rule link selector.

Revision ID: 035
Revises: 034
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "custom_rules",
        "link_selector",
        existing_type=sa.String(length=500),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE custom_rules SET link_selector = 'self' WHERE link_selector IS NULL")
    op.alter_column(
        "custom_rules",
        "link_selector",
        existing_type=sa.String(length=500),
        nullable=False,
    )
