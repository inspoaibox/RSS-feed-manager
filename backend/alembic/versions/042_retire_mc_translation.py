"""Disable retired Mc-Translation sources without selecting a replacement.

Revision ID: 042
Revises: 041
"""

import sqlalchemy as sa

from alembic import op

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE articles SET translation_status = CASE "
            "WHEN translation IS NOT NULL AND translation <> '' THEN 'completed' ELSE 'none' END, "
            "translation_error = NULL, translation_started_at = NULL, "
            "translation_completed_at = NULL "
            "WHERE translation_status IN ('queued', 'translating') AND feed_id IN "
            "(SELECT id FROM feeds WHERE translate_method = 'mc_translation')"
        )
    )
    for table in ("feeds", "custom_rules"):
        op.execute(
            sa.text(
                f"UPDATE {table} SET translate_method = 'none', auto_translate = false "
                "WHERE translate_method = 'mc_translation'"
            )
        )


def downgrade():
    # Do not re-enable a retired external service or guess users' former selections.
    # Legacy credential columns and existing translations have not been deleted.
    pass
