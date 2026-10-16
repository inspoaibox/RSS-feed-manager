"""User isolation, transactional outbox, provider payloads and delivery retries."""

import base64
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import func, select

from app.api.v1.endpoints import external_notifications as endpoints
from app.core.clock import utc_now
from app.core.security import create_access_token
from app.models.article import Article
from app.models.category import Category
from app.models.external_notification import NotificationChannel, NotificationDelivery
from app.models.feed import Feed
from app.models.user import User
from app.services import notification_sender as sender
from app.services.backup_export import generate_backup_data
from app.services.backup_import import import_backup_data
from app.tasks.notification_tasks import claim_delivery, finish_delivery, queue_pending_deliveries

PREFIX = "/api/v1/external-notifications"
WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/private-webhook-token"
TOKEN = "123456:abcdefghijklmnopqrstuvwxyz0123456789"


async def setup(db):
    users = [User(username=f"notifier-{i}", email=f"notify-{i}@example.com", password_hash="unused") for i in range(2)]
    db.add_all(users)
    await db.flush()
    category = Category(user_id=users[0].id, name="Technology")
    db.add(category)
    await db.flush()
    feeds = [Feed(user_id=user.id, url=f"https://example.com/{i}/rss", title=f"Feed {i}",
                  category_id=category.id if i == 0 else None) for i, user in enumerate(users)]
    db.add_all(feeds)
    await db.commit()
    headers = [{"Authorization": "Bearer " + create_access_token({"sub": str(user.id), "token_version": user.token_version})} for user in users]
    return SimpleNamespace(user_id=users[0].id, feed_id=feeds[0].id, other_feed_id=feeds[1].id,
                           category_id=category.id, headers=headers)


async def channel(client, headers, name="Work", provider="feishu"):
    config = {"webhook_url": WEBHOOK, "signing_secret": "private-signing-secret"} if provider == "feishu" else {"bot_token": TOKEN, "chat_id": "-1001234567890"}
    response = await client.post(f"{PREFIX}/channels", headers=headers,
                                 json={"name": name, "provider": provider, "config": config})
    assert response.status_code == 201, response.text
    return response.json()


async def rule(client, headers, channel_ids, source_id, source_type="feed"):
    response = await client.post(f"{PREFIX}/rules", headers=headers, json={
        "name": "Updates", "source_type": source_type, "source_id": source_id, "channel_ids": channel_ids,
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_channels_are_available_to_non_admin_and_owner_only(client, db_session, monkeypatch):
    context = await setup(db_session)
    data = await channel(client, context.headers[0])
    encoded = json.dumps(data)
    assert data["has_webhook"] and data["has_signing_secret"]
    assert WEBHOOK not in encoded and "private-signing-secret" not in encoded
    encrypted = (await db_session.execute(select(NotificationChannel.encrypted_config))).scalar_one()
    assert WEBHOOK not in encrypted
    assert sender.decrypt_channel_config(encrypted)["webhook_url"] == WEBHOOK
    assert (await client.get(f"{PREFIX}/channels", headers=context.headers[1])).json() == []
    send = AsyncMock()
    monkeypatch.setattr(endpoints, "send_notification", send)
    for method, suffix, body in [("put", "", {"name": "Hijack"}), ("delete", "", None), ("post", "/test", None)]:
        response = await client.request(method, f"{PREFIX}/channels/{data['id']}{suffix}",
                                        headers=context.headers[1], json=body)
        assert response.status_code == 404
    send.assert_not_called()


@pytest.mark.asyncio
async def test_rule_rejects_foreign_sources_and_channels(client, db_session):
    context = await setup(db_session)
    own = await channel(client, context.headers[0])
    other = await channel(client, context.headers[1])
    for source_id, ids in [(context.other_feed_id, [own["id"]]), (context.feed_id, [other["id"]])]:
        response = await client.post(f"{PREFIX}/rules", headers=context.headers[0], json={
            "name": "Bad", "source_type": "feed", "source_id": source_id, "channel_ids": ids,
        })
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_edit_retains_secrets_and_can_clear_signature(client, db_session):
    context = await setup(db_session)
    data = await channel(client, context.headers[0])
    response = await client.put(f"{PREFIX}/channels/{data['id']}", headers=context.headers[0], json={
        "config": {"webhook_url": "", "signing_secret": None},
    })
    assert response.status_code == 200 and not response.json()["has_signing_secret"]
    encrypted = (await db_session.execute(select(NotificationChannel.encrypted_config))).scalar_one()
    assert sender.decrypt_channel_config(encrypted)["webhook_url"] == WEBHOOK


@pytest.mark.asyncio
async def test_new_articles_create_durable_deduplicated_deliveries(client, db_session):
    context = await setup(db_session)
    destination = await channel(client, context.headers[0])
    await rule(client, context.headers[0], [destination["id"]], context.feed_id)
    await rule(client, context.headers[0], [destination["id"]], context.category_id, "category")
    article = Article(feed_id=context.feed_id, guid="new", title="New information",
                      link="https://example.com/article", published_at=utc_now())
    db_session.add(article)
    await db_session.commit()
    deliveries = list((await db_session.execute(select(NotificationDelivery))).scalars())
    assert len(deliveries) == 1
    assert "New information" in deliveries[0].message and "Feed 0" in deliveries[0].message
    assert "https://example.com/article" in deliveries[0].message
    article.title = "Updated content"
    await db_session.commit()
    assert (await db_session.execute(select(func.count(NotificationDelivery.id)))).scalar() == 1
    db_session.add(Article(feed_id=context.feed_id, guid="rolled-back", title="Not committed"))
    await db_session.flush()
    await db_session.rollback()
    assert (await db_session.execute(select(func.count(NotificationDelivery.id)))).scalar() == 1


@pytest.mark.asyncio
async def test_multiple_channels_and_disabled_rule(client, db_session):
    context = await setup(db_session)
    first = await channel(client, context.headers[0], "Feishu")
    second = await channel(client, context.headers[0], "TG", "telegram")
    routing = await rule(client, context.headers[0], [first["id"], second["id"]], context.feed_id)
    db_session.add(Article(feed_id=context.feed_id, guid="two", title="Two destinations"))
    await db_session.commit()
    assert (await db_session.execute(select(func.count(NotificationDelivery.id)))).scalar() == 2
    await client.put(f"{PREFIX}/rules/{routing['id']}", headers=context.headers[0], json={**routing, "is_enabled": False})
    db_session.add(Article(feed_id=context.feed_id, guid="disabled", title="Disabled rule"))
    await db_session.commit()
    assert (await db_session.execute(select(func.count(NotificationDelivery.id)))).scalar() == 2


@pytest.mark.asyncio
async def test_atomic_claim_retry_and_history_isolation(client, db_session, monkeypatch):
    from app.tasks import notification_tasks

    now = utc_now()
    monkeypatch.setattr(notification_tasks, "utc_now", lambda: now)
    context = await setup(db_session)
    destination = await channel(client, context.headers[0])
    await rule(client, context.headers[0], [destination["id"]], context.feed_id)
    db_session.add(Article(feed_id=context.feed_id, guid="retries", title="Retry article"))
    await db_session.commit()
    delivery_id = (await db_session.execute(select(NotificationDelivery.id))).scalar_one()
    assert await db_session.run_sync(lambda session: claim_delivery(session, delivery_id))
    assert await db_session.run_sync(lambda session: claim_delivery(session, delivery_id)) is None
    failure = sender.NotificationSendError("Temporary failure", True, 1)
    for attempt in range(1, 4):
        await db_session.run_sync(lambda session: finish_delivery(session, delivery_id, failure))
        delivery = await db_session.get(NotificationDelivery, delivery_id)
        assert delivery.attempts == attempt
        if attempt < 3:
            assert delivery.status == "pending"
            now += timedelta(seconds=10)
            delivery.next_attempt_at = utc_now() - timedelta(seconds=1)
            await db_session.commit()
            assert await db_session.run_sync(lambda session: claim_delivery(session, delivery_id))
        else:
            assert delivery.status == "failed"
    assert (await client.get(f"{PREFIX}/deliveries", headers=context.headers[1])).json()["total"] == 0
    assert (await client.post(f"{PREFIX}/deliveries/{delivery_id}/retry", headers=context.headers[1])).status_code == 404
    assert (await client.post(f"{PREFIX}/deliveries/{delivery_id}/retry", headers=context.headers[0])).status_code == 200


@pytest.mark.asyncio
async def test_saved_channel_test_sends_and_records_sanitized_failure(client, db_session, monkeypatch):
    context = await setup(db_session)
    destination = await channel(client, context.headers[0])
    send = AsyncMock(side_effect=sender.NotificationSendError("请检查机器人权限"))
    monkeypatch.setattr(endpoints, "send_notification", send)
    response = await client.post(f"{PREFIX}/channels/{destination['id']}/test", headers=context.headers[0])
    assert response.json() == {"success": False, "message": "请检查机器人权限"}
    send.assert_awaited_once()
    history = (await client.get(f"{PREFIX}/deliveries", headers=context.headers[0])).json()
    assert history["items"][0]["is_test"] and history["items"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_backup_restores_notification_settings_without_sending_old_articles(client, db_session):
    context = await setup(db_session)
    destination = await channel(client, context.headers[0])
    await rule(client, context.headers[0], [destination["id"]], context.feed_id)
    db_session.add(Article(feed_id=context.feed_id, guid="backup", title="Existing"))
    await db_session.commit()
    backup = await generate_backup_data(db_session, context.user_id)
    assert backup["notification_channels"][0]["config"]["webhook_url"] == WEBHOOK
    backup["articles"][0]["guid"] = "restored-new-guid"
    result = await import_backup_data(db_session, context.user_id, backup)
    assert result.success, result.errors
    assert (await db_session.execute(select(func.count(NotificationDelivery.id)))).scalar() == 1


def test_feishu_signature_and_telegram_payload(monkeypatch):
    monkeypatch.setattr(sender.time, "time", lambda: 1_700_000_000)
    url, body = sender.build_provider_request("feishu", {"webhook_url": WEBHOOK, "signing_secret": "sign"}, "Message")
    expected = base64.b64encode(hmac.new(b"1700000000\nsign", b"", hashlib.sha256).digest()).decode()
    assert url == WEBHOOK and body["sign"] == expected and body["timestamp"] == "1700000000"
    url, body = sender.build_provider_request("telegram", {"bot_token": TOKEN, "chat_id": "-123", "message_thread_id": 7}, "Message")
    assert url.endswith("/sendMessage") and body["message_thread_id"] == 7 and body["chat_id"] == "-123"
    assert "parse_mode" not in body


class ProxyStub:
    url = "http://safe-proxy.example"
    async def __aenter__(self):
        return self
    async def __aexit__(self, *_):
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize("status,data,retryable", [
    (200, {"code": 19021, "msg": "private-webhook-token"}, False),
    (429, {"parameters": {"retry_after": 90}}, True),
    (503, {}, True),
])
async def test_provider_errors_do_not_leak_credentials(monkeypatch, status, data, retryable):
    class ClientStub:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            return False
        @asynccontextmanager
        async def stream(self, *_args, **_kwargs):
            yield httpx.Response(status, json=data)
    monkeypatch.setattr(sender, "SafeBrowserProxy", ProxyStub)
    monkeypatch.setattr(sender.httpx, "AsyncClient", lambda **_: ClientStub())
    with pytest.raises(sender.NotificationSendError) as error:
        await sender.send_notification("feishu", {"webhook_url": WEBHOOK}, "Message")
    assert error.value.retryable == retryable
    assert "private-webhook-token" not in str(error.value)


@pytest.mark.asyncio
async def test_invalid_webhook_target_is_rejected(client, db_session):
    context = await setup(db_session)
    response = await client.post(f"{PREFIX}/channels", headers=context.headers[0], json={
        "name": "Unsafe", "provider": "feishu", "config": {"webhook_url": "http://127.0.0.1/admin"},
    })
    assert response.status_code == 422


def test_http_logs_redact_bot_and_webhook_tokens():
    record = logging.LogRecord("httpx", logging.INFO, "", 0, "HTTP Request: %s %s", (
        "POST", httpx.URL(f"https://api.telegram.org/bot{TOKEN}/sendMessage"),
    ), None)
    sender.NotificationURLFilter().filter(record)
    assert TOKEN not in record.getMessage() and "[REDACTED]" in record.getMessage()
    assert "private-webhook-token" not in sender.redact_notification_url(WEBHOOK)


@pytest.mark.asyncio
async def test_channel_delete_keeps_history_and_removes_rule_binding(client, db_session):
    context = await setup(db_session)
    destination = await channel(client, context.headers[0])
    await rule(client, context.headers[0], [destination["id"]], context.feed_id)
    db_session.add(Article(feed_id=context.feed_id, guid="delete-channel", title="History remains"))
    await db_session.commit()
    response = await client.delete(f"{PREFIX}/channels/{destination['id']}", headers=context.headers[0])
    assert response.status_code == 204
    delivery = (await db_session.execute(select(NotificationDelivery))).scalar_one()
    assert delivery.channel_id is None and delivery.channel_name == "Work"
    assert (await client.get(f"{PREFIX}/rules", headers=context.headers[0])).json()[0]["channel_ids"] == []


@pytest.mark.asyncio
async def test_successful_delivery_is_not_reclaimed_and_disabled_channels_skip(client, db_session):
    context = await setup(db_session)
    destination = await channel(client, context.headers[0])
    await rule(client, context.headers[0], [destination["id"]], context.feed_id)
    db_session.add(Article(feed_id=context.feed_id, guid="success", title="Success"))
    await db_session.commit()
    delivery_id = (await db_session.execute(select(NotificationDelivery.id))).scalar_one()
    assert await db_session.run_sync(lambda session: claim_delivery(session, delivery_id))
    await db_session.run_sync(lambda session: finish_delivery(session, delivery_id, None))
    assert await db_session.run_sync(lambda session: claim_delivery(session, delivery_id)) is None
    sent = await db_session.get(NotificationDelivery, delivery_id)
    assert sent.status == "sent" and sent.sent_at is not None
    db_session.add(Article(feed_id=context.feed_id, guid="will-skip", title="Skip"))
    await db_session.commit()
    pending_id = (await db_session.execute(select(NotificationDelivery.id).where(NotificationDelivery.status == "pending"))).scalar_one()
    await client.put(f"{PREFIX}/channels/{destination['id']}", headers=context.headers[0], json={"is_enabled": False})
    assert await db_session.run_sync(lambda session: claim_delivery(session, pending_id)) is None
    assert (await db_session.get(NotificationDelivery, pending_id)).status == "skipped"


@pytest.mark.asyncio
async def test_dispatch_does_not_queue_pending_messages_twice(client, db_session):
    context = await setup(db_session)
    destination = await channel(client, context.headers[0])
    await rule(client, context.headers[0], [destination["id"]], context.feed_id)
    db_session.add(Article(feed_id=context.feed_id, guid="queued-once", title="Queue once"))
    await db_session.commit()
    ids = await db_session.run_sync(queue_pending_deliveries)
    assert len(ids) == 1
    assert await db_session.run_sync(queue_pending_deliveries) == []
    delivery = await db_session.get(NotificationDelivery, ids[0])
    assert delivery.status == "queued" and delivery.attempts == 0
    delivery.claimed_at = utc_now() - timedelta(minutes=6)
    delivery.next_attempt_at = utc_now() - timedelta(minutes=6)
    await db_session.commit()
    assert await db_session.run_sync(queue_pending_deliveries) == ids
    assert await db_session.run_sync(lambda session: claim_delivery(session, ids[0]))
    assert await db_session.run_sync(lambda session: claim_delivery(session, ids[0])) is None
