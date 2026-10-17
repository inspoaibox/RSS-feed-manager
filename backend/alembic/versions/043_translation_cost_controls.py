"""Persist translation checkpoints, usage receipts and configurable limits.

Revision ID: 043
Revises: 042
"""

import sqlalchemy as sa

from alembic import op

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade():
    for name, default in [
        ("translation_max_input_tokens", "12000"),
        ("translation_max_output_tokens", "4096"),
        ("translation_article_token_limit", "100000"),
        ("translation_max_requests", "32"),
    ]:
        op.add_column(
            "users", sa.Column(name, sa.Integer(), nullable=False, server_default=default)
        )
    op.add_column(
        "users", sa.Column("translation_monthly_token_limit", sa.Integer(), nullable=True)
    )
    op.add_column(
        "articles",
        sa.Column("translation_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ai_providers",
        sa.Column("token_limit_parameter", sa.String(32), nullable=False, server_default="auto"),
    )
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "provider_id", sa.Integer(), sa.ForeignKey("ai_providers.id", ondelete="SET NULL")
        ),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="SET NULL")),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("cache_key", sa.String(64), unique=True),
        sa.Column("input_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("budget_tokens", sa.Integer(), nullable=False),
        *[
            sa.Column(name, sa.Integer())
            for name in (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cached_tokens",
                "reasoning_tokens",
            )
        ],
        sa.Column("result_text", sa.Text()),
        sa.Column("error", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"])
    op.create_index("ix_ai_usage_article_id", "ai_usage", ["article_id"])
    op.create_index("ix_ai_usage_input_key", "ai_usage", ["input_key"])


def downgrade():
    op.drop_table("ai_usage")
    with op.batch_alter_table("ai_providers") as batch:
        batch.drop_column("token_limit_parameter")
    with op.batch_alter_table("articles") as batch:
        batch.drop_column("translation_revision")
    with op.batch_alter_table("users") as batch:
        for name in (
            "translation_max_input_tokens",
            "translation_max_output_tokens",
            "translation_article_token_limit",
            "translation_monthly_token_limit",
            "translation_max_requests",
        ):
            batch.drop_column(name)
