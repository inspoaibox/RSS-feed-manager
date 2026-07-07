"""Add automatic AI summary generation switch.

Revision ID: 038
Revises: 037
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auto_generate_summaries",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        """
        UPDATE users
        SET auto_generate_summaries = TRUE
        WHERE EXISTS (
            SELECT 1
            FROM feeds
            WHERE feeds.user_id = users.id
              AND feeds.auto_summarize = TRUE
        )
        OR EXISTS (
            SELECT 1
            FROM custom_rules
            WHERE custom_rules.user_id = users.id
              AND custom_rules.auto_summarize = TRUE
        )
        """
    )
    op.alter_column("users", "auto_generate_summaries", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "auto_generate_summaries")
