"""Retirement must preserve articles and never enable a paid replacement."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.core.security import create_access_token
from app.models.article import Article
from app.models.custom_rule import CustomRule
from app.models.feed import Feed
from app.models.user import User
from app.tasks import feed_tasks
from tests.migration_support import postgres_migration_database


@pytest.fixture(params=["sqlite", "postgres"])
def migration_engine(request):
    if request.param == "postgres":
        with postgres_migration_database() as engine:
            yield engine
    else:
        engine = sa.create_engine("sqlite://")
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.mark.parametrize("seeded", [False, True])
def test_retirement_migration_preserves_data_and_only_disables_mc(migration_engine, seeded):
    path = Path(__file__).parents[1] / "alembic/versions/042_retire_mc_translation.py"
    spec = importlib.util.spec_from_file_location("retire_mc", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with migration_engine.begin() as connection:
        for table in ("feeds", "custom_rules"):
            connection.execute(
                sa.text(
                    f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, translate_method TEXT, "
                    "auto_translate BOOLEAN)"
                )
            )
            if seeded:
                connection.execute(
                    sa.text(
                        f"INSERT INTO {table} VALUES "
                        "(1, 'mc_translation', true), (2, 'ai', true), (3, 'mc_translation', false)"
                    )
                )
        connection.execute(
            sa.text(
                "CREATE TABLE articles (id INTEGER PRIMARY KEY, feed_id INTEGER, translation TEXT, "
                "translation_status TEXT, translation_error TEXT, "
                "translation_started_at TIMESTAMP, translation_completed_at TIMESTAMP)"
            )
        )
        if seeded:
            for row in [
                (1, 1, None, "queued"),
                (2, 1, "preserve translation", "translating"),
                (3, 1, "completed translation", "completed"),
                (4, 2, None, "queued"),
            ]:
                connection.execute(
                    sa.text(
                        "INSERT INTO articles (id,feed_id,translation,translation_status) "
                        "VALUES (:id,:feed_id,:translation,:status)"
                    ),
                    dict(zip(["id", "feed_id", "translation", "status"], row, strict=True)),
                )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
            migration.downgrade()
        if seeded:
            for table in ("feeds", "custom_rules"):
                assert connection.execute(
                    sa.text(f"SELECT id,translate_method,auto_translate FROM {table} ORDER BY id")
                ).all() == [(1, "none", False), (2, "ai", True), (3, "none", False)]
            assert connection.execute(
                sa.text("SELECT id,translation,translation_status FROM articles ORDER BY id")
            ).all() == [
                (1, None, "none"),
                (2, "preserve translation", "completed"),
                (3, "completed translation", "completed"),
                (4, None, "queued"),
            ]


async def account(db):
    user = User(username="retirement", email="retirement@example.test", password_hash="unused")
    db.add(user)
    await db.commit()
    token = create_access_token({"sub": str(user.id), "token_version": user.token_version})
    return user, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_legacy_backup_cannot_reactivate_mc(client, db_session):
    _, headers = await account(db_session)
    data = {
        "version": "2.0",
        "exported_at": "2026-10-17",
        "categories": [],
        "ai_providers": [],
        "ai_models": [],
        "feeds": [
            {
                "url": "https://example.test/mc",
                "translate_method": "mc_translation",
                "auto_translate": True,
                "target_language": "zh-CN",
            },
            {"url": "https://example.test/ai", "translate_method": "ai", "auto_translate": True},
        ],
        "custom_rules": [
            {
                "name": "Old rule",
                "target_url": "https://example.test/rule",
                "list_selector": "article",
                "title_selector": "h2",
                "translate_method": "mc_translation",
                "auto_translate": True,
            }
        ],
        "articles": [
            {
                "feed_url": "https://example.test/mc",
                "guid": "pending",
                "title": "Pending",
                "translation_status": "queued",
            },
            {
                "feed_url": "https://example.test/mc",
                "guid": "saved",
                "title": "Saved",
                "translation_status": "translating",
                "translation": "keep this translation",
            },
        ],
        "user_settings": {
            "mc_translation_api_key": "legacy-secret",
            "mc_translation_model": "argos",
        },
    }
    for _ in range(2):
        response = await client.post(
            "/api/v1/backup/import",
            headers=headers,
            files={"file": ("legacy.json", json.dumps(data), "application/json")},
        )
        assert response.status_code == 200, response.text
        assert not response.json()["errors"], response.text
    feeds = (await db_session.execute(sa.select(Feed).order_by(Feed.id))).scalars().all()
    assert [(f.translate_method, f.auto_translate) for f in feeds] == [
        ("none", False),
        ("ai", True),
    ]
    rule = (await db_session.execute(sa.select(CustomRule))).scalar_one()
    assert (rule.translate_method, rule.auto_translate) == ("none", False)
    articles = (await db_session.execute(sa.select(Article).order_by(Article.id))).scalars().all()
    assert [(a.translation, a.translation_status) for a in articles] == [
        (None, "none"),
        ("keep this translation", "completed"),
    ]
    settings = await client.get("/api/v1/ai/settings", headers=headers)
    assert not any(k.startswith("mc_translation_") for k in settings.json())


@pytest.mark.asyncio
async def test_retired_configuration_and_test_route_are_rejected(client, db_session):
    _, headers = await account(db_session)
    for method, route, body in [
        (
            "POST",
            "/api/v1/feeds",
            {"url": "https://example.test/rss", "translate_method": "mc_translation"},
        ),
        ("PUT", "/api/v1/feeds/1", {"translate_method": "mc_translation"}),
        (
            "POST",
            "/api/v1/rules",
            {
                "name": "Rule",
                "target_url": "https://example.test",
                "list_selector": "article",
                "title_selector": "h2",
                "translate_method": "mc_translation",
            },
        ),
        ("PUT", "/api/v1/rules/1", {"translate_method": "mc_translation"}),
    ]:
        response = await client.request(method, route, headers=headers, json=body)
        assert response.status_code == 422, (route, response.text)
    response = await client.put(
        "/api/v1/ai/settings", headers=headers, json={"mc_translation_api_key": "old-secret"}
    )
    assert response.status_code == 400
    response = await client.post("/api/v1/ai/mc-translation/test", headers=headers)
    assert response.status_code == 404


def test_stale_mc_tasks_cannot_fall_back_to_paid_ai():
    feed = SimpleNamespace(
        translate_method="mc_translation", auto_translate=True, target_language="zh-CN"
    )
    assert feed_tasks._translation_method_for_feed(feed) == "none"
    with pytest.raises(ValueError, match="translation enabled"):
        feed_tasks._perform_article_translation_sync(None, None, feed)
