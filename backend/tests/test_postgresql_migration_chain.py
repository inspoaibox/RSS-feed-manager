"""Actual PostgreSQL fresh installs and upgrades from historical 038 layouts."""

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from tests.migration_support import postgres_migration_database

pytestmark = pytest.mark.skipif(
    os.environ.get("MIGRATION_TEST_FULL_CHAIN") != "1",
    reason="Full migration chain requires the CI pgvector PostgreSQL service",
)


@pytest.mark.parametrize("layout", ["fresh", "missing", "renamed", "global-index"])
def test_postgresql_full_migration_chain(layout):
    root = Path(__file__).parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    expected = ScriptDirectory.from_config(config).get_current_head()
    with postgres_migration_database() as engine:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            if layout != "fresh":
                command.upgrade(config, "038")
                if layout == "renamed":
                    connection.execute(
                        sa.text(
                            "ALTER TABLE web_push_subscriptions RENAME CONSTRAINT "
                            "uq_user_endpoint TO legacy_user_endpoint_key"
                        )
                    )
                else:
                    connection.execute(
                        sa.text(
                            "ALTER TABLE web_push_subscriptions DROP CONSTRAINT uq_user_endpoint"
                        )
                    )
                    if layout == "global-index":
                        connection.execute(
                            sa.text(
                                "CREATE UNIQUE INDEX legacy_endpoint_index "
                                "ON web_push_subscriptions (endpoint)"
                            )
                        )
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == expected
            assert {"notification_channels", "notification_deliveries"}.issubset(
                sa.inspect(connection).get_table_names()
            )
            assert any(
                item["name"] == "uq_web_push_endpoint" and item["column_names"] == ["endpoint"]
                for item in sa.inspect(connection).get_unique_constraints("web_push_subscriptions")
            )
