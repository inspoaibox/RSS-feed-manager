"""Reproduce the deployed 038 failure through Alembic on an isolated PostgreSQL DB."""

from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from tests.migration_support import postgres_migration_database


def test_postgresql_038_missing_constraint_upgrades_through_notification_migrations():
    root = Path(__file__).parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    expected = ScriptDirectory.from_config(config).get_current_head()
    with postgres_migration_database() as engine:
        with engine.begin() as connection:
            for statement in [
                "CREATE TABLE users (id INTEGER PRIMARY KEY)",
                "CREATE TABLE ai_providers (id INTEGER PRIMARY KEY)",
                "CREATE TABLE feeds (id INTEGER PRIMARY KEY, user_id INTEGER, "
                "translate_method TEXT DEFAULT 'none', auto_translate BOOLEAN DEFAULT false)",
                "CREATE TABLE categories (id INTEGER PRIMARY KEY, user_id INTEGER)",
                "CREATE TABLE articles (id INTEGER PRIMARY KEY, feed_id INTEGER, "
                "translation TEXT, translation_status TEXT DEFAULT 'none', "
                "translation_error TEXT, translation_started_at TIMESTAMP, "
                "translation_completed_at TIMESTAMP)",
                "CREATE TABLE custom_rules (id INTEGER PRIMARY KEY, "
                "translate_method TEXT DEFAULT 'none', auto_translate BOOLEAN DEFAULT false)",
                "CREATE TABLE notification_subscriptions "
                "(id INTEGER PRIMARY KEY, user_id INTEGER, "
                "target_id INTEGER, subscription_type TEXT)",
                "CREATE TABLE notification_pushes "
                "(id INTEGER PRIMARY KEY, user_id INTEGER, article_id INTEGER)",
                "CREATE TABLE web_push_subscriptions "
                "(id INTEGER PRIMARY KEY, user_id INTEGER, endpoint TEXT)",
            ]:
                connection.execute(sa.text(statement))
            config.attributes["connection"] = connection
            command.stamp(config, "038")
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == expected
            assert {
                "notification_channels",
                "notification_rules",
                "notification_deliveries",
            }.issubset(sa.inspect(connection).get_table_names())
            assert "failure_attempts" in {
                column["name"]
                for column in sa.inspect(connection).get_columns("notification_deliveries")
            }
            assert any(
                item["name"] == "uq_web_push_endpoint" and item["column_names"] == ["endpoint"]
                for item in sa.inspect(connection).get_unique_constraints("web_push_subscriptions")
            )
