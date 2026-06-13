"""Add Argos translate source language settings.

Revision ID: 025
Revises: 024
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "argos_source_language" not in user_columns:
        op.add_column(
            "users",
            sa.Column("argos_source_language", sa.String(length=10), nullable=True),
        )

    feed_columns = {column["name"] for column in inspector.get_columns("feeds")}
    if "source_language" not in feed_columns:
        op.add_column(
            "feeds",
            sa.Column("source_language", sa.String(length=10), nullable=True),
        )

    rule_columns = {column["name"] for column in inspector.get_columns("custom_rules")}
    if "source_language" not in rule_columns:
        op.add_column(
            "custom_rules",
            sa.Column("source_language", sa.String(length=10), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    rule_columns = {column["name"] for column in inspector.get_columns("custom_rules")}
    if "source_language" in rule_columns:
        op.drop_column("custom_rules", "source_language")

    feed_columns = {column["name"] for column in inspector.get_columns("feeds")}
    if "source_language" in feed_columns:
        op.drop_column("feeds", "source_language")

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "argos_source_language" in user_columns:
        op.drop_column("users", "argos_source_language")
