"""Add Google Translate key pool.

Revision ID: 024
Revises: 023
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "google_translate_keys" not in tables:
        op.create_table(
            "google_translate_keys",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("api_key", sa.String(length=500), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("limit_days", sa.Integer(), nullable=True),
            sa.Column("limit_articles", sa.Integer(), nullable=True),
            sa.Column("limit_characters", sa.Integer(), nullable=True),
            sa.Column("usage_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("usage_article_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("usage_character_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "api_key", name="uq_google_translate_key_user_api_key"),
        )
        op.create_index("ix_google_translate_keys_user_id", "google_translate_keys", ["user_id"])
        op.create_index("ix_google_translate_keys_is_active", "google_translate_keys", ["is_active"])

        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "google_translate_api_key" in user_columns:
            users = sa.table(
                "users",
                sa.column("id", sa.Integer()),
                sa.column("google_translate_api_key", sa.String()),
            )
            keys = sa.table(
                "google_translate_keys",
                sa.column("user_id", sa.Integer()),
                sa.column("name", sa.String()),
                sa.column("api_key", sa.String()),
                sa.column("is_active", sa.Boolean()),
                sa.column("position", sa.Integer()),
                sa.column("created_at", sa.DateTime(timezone=True)),
            )
            bind.execute(
                keys.insert().from_select(
                    ["user_id", "name", "api_key", "is_active", "position", "created_at"],
                    sa.select(
                        users.c.id,
                        sa.literal("默认 Google Key"),
                        users.c.google_translate_api_key,
                        sa.true(),
                        sa.literal(0),
                        sa.func.now(),
                    ).where(
                        users.c.google_translate_api_key.is_not(None),
                        users.c.google_translate_api_key != "",
                    ),
                )
            )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "google_translate_keys" in tables:
        op.drop_table("google_translate_keys")
