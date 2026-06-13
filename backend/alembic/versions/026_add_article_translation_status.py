"""Add article translation queue status.

Revision ID: 026
Revises: 025
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    article_columns = {column["name"] for column in inspector.get_columns("articles")}

    if "translation_status" not in article_columns:
        op.add_column(
            "articles",
            sa.Column(
                "translation_status",
                sa.String(length=20),
                nullable=False,
                server_default="none",
            ),
        )
        op.execute(
            "UPDATE articles SET translation_status = 'completed' "
            "WHERE translation IS NOT NULL AND translation <> ''"
        )

    if "translation_error" not in article_columns:
        op.add_column("articles", sa.Column("translation_error", sa.Text(), nullable=True))

    if "translation_started_at" not in article_columns:
        op.add_column(
            "articles",
            sa.Column("translation_started_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "translation_completed_at" not in article_columns:
        op.add_column(
            "articles",
            sa.Column("translation_completed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    article_columns = {column["name"] for column in inspector.get_columns("articles")}

    if "translation_completed_at" in article_columns:
        op.drop_column("articles", "translation_completed_at")
    if "translation_started_at" in article_columns:
        op.drop_column("articles", "translation_started_at")
    if "translation_error" in article_columns:
        op.drop_column("articles", "translation_error")
    if "translation_status" in article_columns:
        op.drop_column("articles", "translation_status")
