"""Add precomputed keyword article matches.

Revision ID: 034
Revises: 033
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "keyword_article_matches" not in tables:
        op.create_table(
            "keyword_article_matches",
            sa.Column("keyword_subscription_id", sa.Integer(), nullable=False),
            sa.Column("article_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["keyword_subscription_id"],
                ["keyword_subscriptions.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("keyword_subscription_id", "article_id"),
        )
        op.create_index(
            "ix_keyword_article_matches_article_id",
            "keyword_article_matches",
            ["article_id"],
        )

    keyword_columns = {
        column["name"]
        for column in inspector.get_columns("keyword_subscriptions")
    }
    if "matches_built_at" not in keyword_columns:
        op.add_column(
            "keyword_subscriptions",
            sa.Column("matches_built_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    keyword_columns = {
        column["name"]
        for column in inspector.get_columns("keyword_subscriptions")
    }
    if "matches_built_at" in keyword_columns:
        op.drop_column("keyword_subscriptions", "matches_built_at")

    tables = set(inspector.get_table_names())
    if "keyword_article_matches" in tables:
        op.drop_index(
            "ix_keyword_article_matches_article_id",
            table_name="keyword_article_matches",
        )
        op.drop_table("keyword_article_matches")
