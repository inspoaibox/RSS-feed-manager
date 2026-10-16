"""Exercise the new notification schema on an isolated database."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_external_notification_migration_upgrade_and_downgrade():
    path = Path(__file__).parents[1] / "alembic/versions/040_add_external_notifications.py"
    spec = importlib.util.spec_from_file_location("external_notification_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            connection.execute(sa.text("CREATE TABLE articles (id INTEGER PRIMARY KEY)"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                inspector = sa.inspect(connection)
                assert {
                    "notification_channels",
                    "notification_rules",
                    "notification_rule_channels",
                    "notification_deliveries",
                }.issubset(inspector.get_table_names())
                assert {
                    column["name"] for column in inspector.get_columns("notification_deliveries")
                } >= {
                    "user_id",
                    "channel_id",
                    "article_id",
                    "status",
                    "attempts",
                    "next_attempt_at",
                }
                assert "uq_notification_delivery" in {
                    constraint["name"]
                    for constraint in inspector.get_unique_constraints("notification_deliveries")
                }
                migration.downgrade()
                assert set(sa.inspect(connection).get_table_names()) == {"users", "articles"}
    finally:
        engine.dispose()


def test_notification_rate_limit_migration_preserves_settings_and_backfills_failures():
    migrations = []
    for filename in ["040_add_external_notifications.py", "041_notification_rate_limits.py"]:
        path = Path(__file__).parents[1] / "alembic/versions" / filename
        spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migrations.append(migration)
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            connection.execute(sa.text("CREATE TABLE articles (id INTEGER PRIMARY KEY)"))
            connection.execute(sa.text("INSERT INTO users VALUES (1)"))
            with Operations.context(MigrationContext.configure(connection)):
                migrations[0].upgrade()
                connection.execute(
                    sa.text(
                        "INSERT INTO notification_channels "
                        "(id,user_id,name,provider,encrypted_config,is_enabled) "
                        "VALUES (1,1,'Legacy','wecom','encrypted-settings',1)"
                    )
                )
                for row in [
                    {"id": 1, "status": "pending", "attempts": 2, "error": "Temporary failure"},
                    {"id": 2, "status": "pending", "attempts": 2, "error": "通知服务限流"},
                    {"id": 3, "status": "sent", "attempts": 1, "error": None},
                ]:
                    connection.execute(
                        sa.text(
                            "INSERT INTO notification_deliveries "
                            "(id,user_id,channel_id,channel_name,provider,article_title,message,"
                            "is_test,status,attempts,error) "
                            "VALUES (:id,1,1,'Legacy','wecom','Title','Message',"
                            "0,:status,:attempts,:error)"
                        ),
                        row,
                    )
                migrations[1].upgrade()
                rows = connection.execute(
                    sa.text(
                        "SELECT id,attempts,failure_attempts,status "
                        "FROM notification_deliveries ORDER BY id"
                    )
                ).all()
                assert rows == [(1, 2, 2, "pending"), (2, 2, 0, "pending"), (3, 1, 0, "sent")]
                channel = connection.execute(
                    sa.text("SELECT encrypted_config,next_send_at FROM notification_channels")
                ).one()
                assert channel == ("encrypted-settings", None)
                migrations[1].downgrade()
                assert "failure_attempts" not in {
                    column["name"]
                    for column in sa.inspect(connection).get_columns("notification_deliveries")
                }
                assert (
                    connection.scalar(sa.text("SELECT count(*) FROM notification_deliveries")) == 3
                )
                migrations[0].downgrade()
    finally:
        engine.dispose()
