"""Add user-owned Feishu/Telegram channels, routing rules and delivery outbox.

Revision ID: 040
Revises: 039
"""

import sqlalchemy as sa
from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]


def user_column():
    return sa.Column(
        "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def upgrade():
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        user_column(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("encrypted_config", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("user_id", "name", name="uq_notification_channel_name"),
    )
    op.create_index("ix_notification_channels_user_id", "notification_channels", ["user_id"])
    op.create_table(
        "notification_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        user_column(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint(
            "user_id", "name", "source_type", "source_id", name="uq_notification_rule_name_source"
        ),
    )
    op.create_index("ix_notification_rules_user_id", "notification_rules", ["user_id"])
    op.create_table(
        "notification_rule_channels",
        sa.Column(
            "rule_id",
            sa.Integer(),
            sa.ForeignKey("notification_rules.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "channel_id",
            sa.Integer(),
            sa.ForeignKey("notification_channels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        user_column(),
        sa.Column(
            "channel_id",
            sa.Integer(),
            sa.ForeignKey("notification_channels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "article_id",
            sa.Integer(),
            sa.ForeignKey("articles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel_name", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("article_title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("channel_id", "article_id", name="uq_notification_delivery"),
    )
    op.create_index("ix_notification_deliveries_user_id", "notification_deliveries", ["user_id"])
    op.create_index("ix_notification_deliveries_status", "notification_deliveries", ["status"])


def downgrade():
    for table in [
        "notification_deliveries",
        "notification_rule_channels",
        "notification_rules",
        "notification_channels",
    ]:
        op.drop_table(table)
