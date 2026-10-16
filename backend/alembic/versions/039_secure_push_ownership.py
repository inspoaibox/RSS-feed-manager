"""Remove legacy foreign push records and make device endpoints exclusive.

Revision ID: 039
Revises: 038
"""

import sqlalchemy as sa

from alembic import op

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None

TABLE = "web_push_subscriptions"
NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_N_name)s"}


def _whole_unique_index(index, columns) -> bool:
    options = index.get("dialect_options") or {}
    return (
        bool(index.get("unique"))
        and set(index.get("column_names") or []) == set(columns)
        and not index.get("duplicates_constraint")
        and not any(value is not None for key, value in options.items() if key.endswith("_where"))
    )


def _replace_uniqueness(remove_columns, add_columns, name) -> None:
    inspector = sa.inspect(op.get_bind())
    constraints = inspector.get_unique_constraints(TABLE)
    indexes = inspector.get_indexes(TABLE)
    already_unique = any(
        item["name"] == name and set(item["column_names"]) == set(add_columns)
        for item in constraints
    )
    obsolete_constraints = [
        item
        for item in constraints
        if set(item["column_names"]) == set(remove_columns)
        or (set(item["column_names"]) == set(add_columns) and item["name"] != name)
    ]
    obsolete_indexes = [
        item
        for item in indexes
        if _whole_unique_index(item, remove_columns) or _whole_unique_index(item, add_columns)
    ]
    if not obsolete_constraints and not obsolete_indexes and already_unique:
        return
    # Legacy installations may use generated names, standalone indexes, or no constraint.
    # Naming reflected SQLite constraints makes unnamed legacy constraints removable too.
    with op.batch_alter_table(TABLE, naming_convention=NAMING_CONVENTION) as batch:
        for item in obsolete_constraints:
            constraint_name = item["name"] or f"uq_{TABLE}_{'_'.join(item['column_names'])}"
            batch.drop_constraint(constraint_name, type_="unique")
        for item in obsolete_indexes:
            batch.drop_index(item["name"])
        if not already_unique:
            batch.create_unique_constraint(name, add_columns)


def upgrade() -> None:
    # Only remove records that violate the same ownership checks enforced by the API.
    op.execute(
        sa.text("""
        DELETE FROM notification_pushes WHERE EXISTS (
            SELECT 1 FROM articles a JOIN feeds f ON f.id = a.feed_id
            WHERE a.id = notification_pushes.article_id
              AND f.user_id <> notification_pushes.user_id
        )
    """)
    )
    op.execute(
        sa.text("""
        DELETE FROM notification_subscriptions
        WHERE (subscription_type = 'feed' AND NOT EXISTS (
            SELECT 1 FROM feeds f WHERE f.id = notification_subscriptions.target_id
              AND f.user_id = notification_subscriptions.user_id
        )) OR (subscription_type = 'category' AND NOT EXISTS (
            SELECT 1 FROM categories c WHERE c.id = notification_subscriptions.target_id
              AND c.user_id = notification_subscriptions.user_id
        ))
    """)
    )
    op.execute(
        sa.text("""
        DELETE FROM web_push_subscriptions WHERE id NOT IN (
            SELECT MAX(id) FROM web_push_subscriptions GROUP BY endpoint
        )
    """)
    )
    _replace_uniqueness(["user_id", "endpoint"], ["endpoint"], "uq_web_push_endpoint")


def downgrade() -> None:
    _replace_uniqueness(["endpoint"], ["user_id", "endpoint"], "uq_user_endpoint")
