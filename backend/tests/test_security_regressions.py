"""Regression tests against account revocation and cross-user access."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.v1.endpoints import ai
from app.core.config import Settings
from app.core.security import create_access_token
from app.models.article import Article, UserArticle
from app.models.category import Category
from app.models.feed import Feed
from app.models.push_notification import NotificationSubscription
from app.models.user import User
from app.services.category_service import CategoryService
from app.services.push_notification_service import PushNotificationService


async def seed_users(db):
    users = [User(username=f"user-{i}", email=f"user-{i}@example.com", password_hash="unused")
             for i in range(2)]
    db.add_all(users)
    await db.flush()
    feed = Feed(user_id=users[0].id, title="Private feed", url="https://example.com/rss")
    db.add(feed)
    await db.flush()
    article = Article(feed_id=feed.id, guid="a", title="private alpha", content="secret alpha")
    db.add(article)
    await db.commit()
    return users, feed, article


def bearer(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id), 'token_version': user.token_version})}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("revocation", ["password", "disabled", "deleted"])
async def test_all_user_routes_reject_revoked_access(client, db_session, revocation):
    users, _, _ = await seed_users(db_session)
    user = users[0]
    headers = bearer(user)
    if revocation == "password":
        user.token_version += 1
    elif revocation == "disabled":
        user.is_active = False
    else:
        await db_session.delete(user)
    await db_session.commit()
    for path in ["feeds", "articles", "ai/settings", "mobile/sync", "push-notifications/subscriptions"]:
        response = await client.get(f"/api/v1/{path}", headers=headers)
        assert response.status_code in {401, 403}, (path, response.text)


@pytest.mark.asyncio
async def test_ai_operations_do_not_read_other_users_articles(client, db_session):
    users, _, article = await seed_users(db_session)
    article_id, headers = article.id, bearer(users[1])
    for operation in ["translate", "summarize"]:
        response = await client.post(f"/api/v1/ai/{operation}/{article_id}",
                                     json={"target_language": "zh-CN"}, headers=headers)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_push_target_must_be_owned_by_requesting_user(client, db_session):
    users, feed, _ = await seed_users(db_session)
    feed_id, owner_headers = feed.id, bearer(users[0])
    response = await client.post("/api/v1/push-notifications/subscriptions", headers=bearer(users[1]),
                                json={"name": "other", "subscription_type": "feed", "target_id": feed_id})
    assert response.status_code == 404
    response = await client.post("/api/v1/push-notifications/subscriptions", headers=owner_headers,
                                json={"name": "owned", "subscription_type": "feed", "target_id": feed_id})
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_keyword_push_only_matches_feed_owner(db_session):
    users, feed, article = await seed_users(db_session)
    db_session.add_all([NotificationSubscription(user_id=user.id, name="alpha", keyword="alpha",
                                                subscription_type="keyword") for user in users])
    await db_session.commit()
    def check(session):
        candidate = session.get(Article, article.id)
        matches = PushNotificationService(session)._find_matching_subscriptions(candidate, feed.id, None)
        assert len(matches) == 1
        assert matches[0].user_id == users[0].id
    await db_session.run_sync(check)


@pytest.mark.asyncio
async def test_foreign_embedding_task_cannot_be_cancelled(client, db_session, monkeypatch):
    users, _, _ = await seed_users(db_session)
    async def deny(*_):
        raise HTTPException(status_code=404, detail="Task not found")
    monkeypatch.setattr(ai, "_require_embedding_task_owner", deny)
    from app.tasks.celery_app import celery_app
    revoke = AsyncMock()
    monkeypatch.setattr(celery_app.control, "revoke", revoke)
    response = await client.post("/api/v1/ai/embeddings/task/foreign/cancel", headers=bearer(users[0]))
    assert response.status_code == 404
    revoke.assert_not_called()


@pytest.mark.asyncio
async def test_cookie_login_refresh_and_logout(client, db_session):
    response = await client.post("/api/v1/auth/register", json={"username": "alice", "email": "alice@example.com", "password": "valid-password"})
    assert response.status_code == 201, response.text
    assert "refresh_token" not in response.json()
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "rss_refresh_token" in client.cookies
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert (await client.post("/api/v1/auth/refresh", json={})).status_code == 200
    assert (await client.post("/api/v1/auth/refresh", json={}, headers={"Origin": "https://attacker.example"})).status_code == 403
    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
    assert (await client.get("/api/v1/feeds", headers=headers)).status_code == 401
    assert (await client.post("/api/v1/auth/refresh", json={})).status_code == 401


@pytest.mark.asyncio
async def test_category_unread_counts(db_session):
    users, feed, article = await seed_users(db_session)
    category = Category(user_id=users[0].id, name="Articles")
    db_session.add(category)
    await db_session.flush()
    feed.category_id = category.id
    await db_session.flush()
    assert (await CategoryService(db_session).get_all(users[0].id))[0].unread_count == 1
    db_session.add(UserArticle(user_id=users[0].id, article_id=article.id, is_read=True,
                              read_at=datetime.now(timezone.utc)))
    await db_session.flush()
    assert (await CategoryService(db_session).get_by_id(users[0].id, category.id)).unread_count == 0


def test_production_refuses_default_secret():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(_env_file=None, ENVIRONMENT="production", COOKIE_SECURE=True,
                 SECRET_KEY="rss_manager_secret_key_2024_production")


@pytest.mark.asyncio
async def test_bcrypt_utf8_limit_is_validation_error(client):
    response = await client.post("/api/v1/auth/register", json={"username": "long-password", "email": "long@example.com", "password": "密" * 30})
    assert response.status_code == 422
