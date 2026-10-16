"""Persist channel pacing and separate failures from rate-limited sends.

Revision ID: 041
Revises: 040
"""

import sqlalchemy as sa

from alembic import op

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notification_channels",
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("failure_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        sa.text(
            "UPDATE notification_deliveries SET failure_attempts = CASE "
            "WHEN status IN ('pending', 'queued') AND error LIKE '%限流%' THEN 0 "
            "WHEN status IN ('sent', 'sending') THEN CASE "
            "WHEN attempts > 3 THEN 3 WHEN attempts > 0 THEN attempts - 1 ELSE 0 END "
            "WHEN attempts > 3 THEN 3 ELSE attempts END"
        )
    )


def downgrade():
    with op.batch_alter_table("notification_deliveries") as batch:
        batch.drop_column("failure_attempts")
    with op.batch_alter_table("notification_channels") as batch:
        batch.drop_column("next_send_at")
