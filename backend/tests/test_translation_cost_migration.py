"""Actual PostgreSQL reservations and upgrade/downgrade coverage."""

import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import sessionmaker

from app.models.ai_provider import AIModel, AIProvider
from app.models.ai_usage import AIUsage
from app.models.user import User
from app.services.ai_client import AIClientError
from app.services.ai_usage_service import TranslationUsageRecorder
from tests.migration_support import postgres_migration_database


@pytest.mark.parametrize("database", ["sqlite", "postgres"])
def test_translation_controls_upgrade_and_downgrade(database):
    def verify(engine):
        path = Path(__file__).parents[1] / "alembic/versions/043_translation_cost_controls.py"
        spec = importlib.util.spec_from_file_location("translation_controls", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            for table in ("users", "articles", "ai_providers"):
                connection.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
                connection.execute(sa.text(f"INSERT INTO {table} VALUES (1)"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert connection.execute(
                    sa.text(
                        "SELECT translation_max_input_tokens,translation_max_output_tokens,"
                        "translation_article_token_limit,translation_monthly_token_limit FROM users"
                    )
                ).one() == (12000, 4096, 100000, None)
                assert connection.scalar(sa.text("SELECT translation_revision FROM articles")) == 0
                assert "ai_usage" in sa.inspect(connection).get_table_names()
                migration.downgrade()
                assert "ai_usage" not in sa.inspect(connection).get_table_names()
                for table in ("users", "articles", "ai_providers"):
                    assert connection.scalar(sa.text(f"SELECT count(*) FROM {table}")) == 1

    if database == "postgres":
        with postgres_migration_database() as engine:
            verify(engine)
    else:
        engine = sa.create_engine("sqlite://")
        try:
            verify(engine)
        finally:
            engine.dispose()


def test_concurrent_workers_cannot_over_reserve_monthly_budget():
    with postgres_migration_database() as engine:
        for table in (User.__table__, AIProvider.__table__, AIModel.__table__):
            table.create(engine)
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE articles (id INTEGER PRIMARY KEY)"))
        AIUsage.__table__.create(engine)
        factory = sessionmaker(engine)
        with factory() as db:
            user = User(
                username="budget",
                email="budget@example.test",
                password_hash="unused",
                translation_monthly_token_limit=200,
            )
            db.add(user)
            db.flush()
            provider = AIProvider(user_id=user.id, name="fake", type="openai", api_key="unused")
            db.add(provider)
            db.flush()
            model = AIModel(provider_id=provider.id, model_id="fake", name="fake")
            db.add(model)
            db.commit()
            ids = user.id, provider.id, model.id

        def reserve(_):
            with factory() as db:
                recorder = TranslationUsageRecorder(db, *ids, operation="translation_test")
                try:
                    recorder.begin(
                        "chat/completions",
                        {
                            "model": "fake",
                            "max_tokens": 128,
                            "messages": [{"role": "user", "content": "Hello"}],
                        },
                    )
                    return True
                except AIClientError:
                    return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, range(2)))
        assert results.count(True) == 1
        with factory() as db:
            assert db.scalar(sa.select(sa.func.count(AIUsage.id))) == 1
            assert db.scalar(sa.select(sa.func.sum(AIUsage.budget_tokens))) <= 200
