"""Verify legacy push cleanup without touching a real user database."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from tests.migration_support import postgres_migration_database


@pytest.fixture(params=["sqlite", "postgresql"])
def migration_engine(request):
    if request.param == "postgresql":
        with postgres_migration_database() as engine:
            yield engine
    else:
        engine = sa.create_engine("sqlite://")
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.mark.parametrize(
    "layout",
    [
        "named",
        "renamed",
        "unnamed",
        "missing",
        "pair-index",
        "global",
        "renamed-global",
        "global-index",
        "both",
        "partial-global-index",
        "misnamed-pair",
    ],
)
def test_push_ownership_migration(layout, migration_engine):
    metadata = sa.MetaData()
    feeds = sa.Table(
        "feeds",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer),
    )
    categories = sa.Table(
        "categories",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer),
    )
    articles = sa.Table(
        "articles",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("feed_id", sa.Integer),
    )
    subscriptions = sa.Table(
        "notification_subscriptions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer),
        sa.Column("target_id", sa.Integer),
        sa.Column("subscription_type", sa.String),
    )
    pushes = sa.Table(
        "notification_pushes",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer),
        sa.Column("article_id", sa.Integer),
    )
    devices = sa.Table(
        "web_push_subscriptions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer),
        sa.Column("endpoint", sa.String),
    )
    if layout in {"named", "renamed", "unnamed", "both", "misnamed-pair"}:
        name = {
            "named": "uq_user_endpoint",
            "renamed": "legacy_user_endpoint_key",
            "unnamed": None,
            "both": "legacy_pair_key",
            "misnamed-pair": "uq_web_push_endpoint",
        }[layout]
        devices.append_constraint(sa.UniqueConstraint("user_id", "endpoint", name=name))
    if layout in {"global", "renamed-global", "both"}:
        name = "legacy_endpoint_key" if layout == "renamed-global" else "uq_web_push_endpoint"
        devices.append_constraint(sa.UniqueConstraint("endpoint", name=name))
    if layout == "pair-index":
        sa.Index("legacy_pair_index", devices.c.user_id, devices.c.endpoint, unique=True)
    if layout == "global-index":
        sa.Index("legacy_endpoint_index", devices.c.endpoint, unique=True)
    if layout == "partial-global-index":
        sa.Index(
            "legacy_partial_endpoint_index",
            devices.c.endpoint,
            unique=True,
            sqlite_where=devices.c.user_id == 1,
            postgresql_where=devices.c.user_id == 1,
        )
    sa.Index("ix_legacy_devices_user", devices.c.user_id)
    globally_unique = layout in {"global", "renamed-global", "global-index", "both"}
    migration_path = Path(__file__).parents[1] / "alembic/versions/039_secure_push_ownership.py"
    spec = importlib.util.spec_from_file_location("secure_push_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = migration_engine
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(feeds.insert(), [{"id": 1, "user_id": 1}, {"id": 2, "user_id": 2}])
            connection.execute(categories.insert(), {"id": 1, "user_id": 1})
            connection.execute(articles.insert(), {"id": 1, "feed_id": 1})
            connection.execute(
                subscriptions.insert(),
                [
                    {"id": 1, "user_id": 1, "target_id": 1, "subscription_type": "feed"},
                    {"id": 2, "user_id": 2, "target_id": 1, "subscription_type": "feed"},
                    {"id": 3, "user_id": 2, "target_id": None, "subscription_type": "keyword"},
                ],
            )
            connection.execute(
                pushes.insert(),
                [
                    {"id": 1, "user_id": 2, "article_id": 1},
                    {"id": 2, "user_id": 1, "article_id": 1},
                ],
            )
            connection.execute(
                devices.insert(),
                [
                    {
                        "id": 1,
                        "user_id": 1,
                        "endpoint": "first-device" if globally_unique else "same-device",
                    },
                    {"id": 2, "user_id": 2, "endpoint": "same-device"},
                ],
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
            assert connection.execute(sa.select(subscriptions.c.id)).scalars().all() == [1, 3]
            assert connection.execute(sa.select(pushes.c.id)).scalars().all() == [2]
            owners = (
                connection.execute(sa.select(devices.c.user_id).order_by(devices.c.id))
                .scalars()
                .all()
            )
            assert owners == ([1, 2] if globally_unique else [2])
            assert "ix_legacy_devices_user" in {
                item["name"] for item in sa.inspect(connection).get_indexes(devices.name)
            }
            assert any(
                item["name"] == "uq_web_push_endpoint" and item["column_names"] == ["endpoint"]
                for item in sa.inspect(connection).get_unique_constraints(devices.name)
            )
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as connection:
            connection.execute(devices.insert(), {"id": 3, "user_id": 3, "endpoint": "same-device"})
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                migration.downgrade()
            connection.execute(devices.insert(), {"id": 3, "user_id": 3, "endpoint": "same-device"})
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as connection:
            connection.execute(devices.insert(), {"id": 4, "user_id": 2, "endpoint": "same-device"})
    finally:
        engine.dispose()
