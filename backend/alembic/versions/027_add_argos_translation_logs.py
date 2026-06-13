"""Add Argos translation logs.

Revision ID: 027
Revises: 026
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "argos_translation_logs" in tables:
        return

    op.create_table(
        "argos_translation_logs",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=True),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("feed_title", sa.String(length=255), nullable=True),
        sa.Column("article_title", sa.String(length=500), nullable=True),
        sa.Column("source_language", sa.String(length=10), nullable=False),
        sa.Column("target_language", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="translating"),
        sa.Column("title_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_argos_translation_logs_user_id", "argos_translation_logs", ["user_id"])
    op.create_index("ix_argos_translation_logs_feed_id", "argos_translation_logs", ["feed_id"])
    op.create_index("ix_argos_translation_logs_article_id", "argos_translation_logs", ["article_id"])
    op.create_index("ix_argos_translation_logs_status", "argos_translation_logs", ["status"])
    op.create_index(
        "ix_argos_translation_logs_user_started",
        "argos_translation_logs",
        ["user_id", "started_at"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "argos_translation_logs" not in tables:
        return

    op.drop_index("ix_argos_translation_logs_user_started", table_name="argos_translation_logs")
    op.drop_index("ix_argos_translation_logs_status", table_name="argos_translation_logs")
    op.drop_index("ix_argos_translation_logs_article_id", table_name="argos_translation_logs")
    op.drop_index("ix_argos_translation_logs_feed_id", table_name="argos_translation_logs")
    op.drop_index("ix_argos_translation_logs_user_id", table_name="argos_translation_logs")
    op.drop_table("argos_translation_logs")
