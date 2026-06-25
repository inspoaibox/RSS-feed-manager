"""Add keyword subscription source filters.

Revision ID: 032
Revises: 031
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("keyword_subscriptions")}

    if "excluded_category_ids" not in columns:
        op.add_column(
            "keyword_subscriptions",
            sa.Column(
                "excluded_category_ids",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            ),
        )
    if "excluded_feed_ids" not in columns:
        op.add_column(
            "keyword_subscriptions",
            sa.Column(
                "excluded_feed_ids",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("keyword_subscriptions")}

    if "excluded_feed_ids" in columns:
        op.drop_column("keyword_subscriptions", "excluded_feed_ids")
    if "excluded_category_ids" in columns:
        op.drop_column("keyword_subscriptions", "excluded_category_ids")
