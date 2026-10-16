"""Verify legacy push cleanup without touching a real user database."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_push_ownership_migration():
    metadata = sa.MetaData()
    feeds = sa.Table("feeds", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("user_id", sa.Integer))
    categories = sa.Table("categories", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("user_id", sa.Integer))
    articles = sa.Table("articles", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("feed_id", sa.Integer))
    subscriptions = sa.Table("notification_subscriptions", metadata, sa.Column("id", sa.Integer, primary_key=True),
                             sa.Column("user_id", sa.Integer), sa.Column("target_id", sa.Integer), sa.Column("subscription_type", sa.String))
    pushes = sa.Table("notification_pushes", metadata, sa.Column("id", sa.Integer, primary_key=True),
                     sa.Column("user_id", sa.Integer), sa.Column("article_id", sa.Integer))
    devices = sa.Table("web_push_subscriptions", metadata, sa.Column("id", sa.Integer, primary_key=True),
                      sa.Column("user_id", sa.Integer), sa.Column("endpoint", sa.String),
                      sa.UniqueConstraint("user_id", "endpoint", name="uq_user_endpoint"))
    migration_path = Path(__file__).parents[1] / "alembic/versions/039_secure_push_ownership.py"
    spec = importlib.util.spec_from_file_location("secure_push_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(feeds.insert(), [{"id": 1, "user_id": 1}, {"id": 2, "user_id": 2}])
            connection.execute(categories.insert(), {"id": 1, "user_id": 1})
            connection.execute(articles.insert(), {"id": 1, "feed_id": 1})
            connection.execute(subscriptions.insert(), [
                {"id": 1, "user_id": 1, "target_id": 1, "subscription_type": "feed"},
                {"id": 2, "user_id": 2, "target_id": 1, "subscription_type": "feed"},
                {"id": 3, "user_id": 2, "target_id": None, "subscription_type": "keyword"},
            ])
            connection.execute(pushes.insert(), [{"id": 1, "user_id": 2, "article_id": 1},
                                                 {"id": 2, "user_id": 1, "article_id": 1}])
            connection.execute(devices.insert(), [{"id": 1, "user_id": 1, "endpoint": "same-device"},
                                                  {"id": 2, "user_id": 2, "endpoint": "same-device"}])
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert connection.execute(sa.select(subscriptions.c.id)).scalars().all() == [1, 3]
            assert connection.execute(sa.select(pushes.c.id)).scalars().all() == [2]
            assert connection.execute(sa.select(devices.c.user_id)).scalars().all() == [2]
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as connection:
            connection.execute(devices.insert(), {"id": 3, "user_id": 3, "endpoint": "same-device"})
    finally:
        engine.dispose()
