"""Add translation scope settings.

Revision ID: 029
Revises: 028
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    feed_columns = {column["name"] for column in inspector.get_columns("feeds")}
    if "translate_title" not in feed_columns:
        op.add_column(
            "feeds",
            sa.Column("translate_title", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "translate_content" not in feed_columns:
        op.add_column(
            "feeds",
            sa.Column("translate_content", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    rule_columns = {column["name"] for column in inspector.get_columns("custom_rules")}
    if "translate_title" not in rule_columns:
        op.add_column(
            "custom_rules",
            sa.Column("translate_title", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "translate_content" not in rule_columns:
        op.add_column(
            "custom_rules",
            sa.Column("translate_content", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    rule_columns = {column["name"] for column in inspector.get_columns("custom_rules")}
    if "translate_content" in rule_columns:
        op.drop_column("custom_rules", "translate_content")
    if "translate_title" in rule_columns:
        op.drop_column("custom_rules", "translate_title")

    feed_columns = {column["name"] for column in inspector.get_columns("feeds")}
    if "translate_content" in feed_columns:
        op.drop_column("feeds", "translate_content")
    if "translate_title" in feed_columns:
        op.drop_column("feeds", "translate_title")
