"""Remove legacy foreign push records and make device endpoints exclusive.

Revision ID: 039
Revises: 038
"""

from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only remove records that violate the same ownership checks enforced by the API.
    op.execute(sa.text("""
        DELETE FROM notification_pushes WHERE EXISTS (
            SELECT 1 FROM articles a JOIN feeds f ON f.id = a.feed_id
            WHERE a.id = notification_pushes.article_id
              AND f.user_id <> notification_pushes.user_id
        )
    """))
    op.execute(sa.text("""
        DELETE FROM notification_subscriptions
        WHERE (subscription_type = 'feed' AND NOT EXISTS (
            SELECT 1 FROM feeds f WHERE f.id = notification_subscriptions.target_id
              AND f.user_id = notification_subscriptions.user_id
        )) OR (subscription_type = 'category' AND NOT EXISTS (
            SELECT 1 FROM categories c WHERE c.id = notification_subscriptions.target_id
              AND c.user_id = notification_subscriptions.user_id
        ))
    """))
    op.execute(sa.text("""
        DELETE FROM web_push_subscriptions WHERE id NOT IN (
            SELECT MAX(id) FROM web_push_subscriptions GROUP BY endpoint
        )
    """))
    with op.batch_alter_table("web_push_subscriptions") as batch:
        batch.drop_constraint("uq_user_endpoint", type_="unique")
        batch.create_unique_constraint("uq_web_push_endpoint", ["endpoint"])


def downgrade() -> None:
    with op.batch_alter_table("web_push_subscriptions") as batch:
        batch.drop_constraint("uq_web_push_endpoint", type_="unique")
        batch.create_unique_constraint("uq_user_endpoint", ["user_id", "endpoint"])
