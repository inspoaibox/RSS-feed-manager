"""Regression tests for pacing, bounded responses, SMTP errors, and orphan backups."""

import asyncio
import json
import smtplib
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.security import create_access_token
from app.models.external_notification import NotificationChannel, NotificationDelivery
from app.models.feed import Feed
from app.models.user import User
from app.services import notification_email as email
from app.services import notification_sender as sender
from app.services.backup_export import generate_backup_data
from app.services.backup_import import import_backup_data
from app.services.notification_rate_limit import as_utc
from app.tasks import notification_tasks as tasks

PREFIX = "/api/v1/external-notifications"
EMAIL_CONFIG = {
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_security": "starttls",
    "smtp_username": "sender@example.com",
    "smtp_password": "dummy-password",
    "smtp_from": "sender@example.com",
    "smtp_to": ["reader@example.com"],
}


@pytest.fixture
def notification_sessions(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "notification-reliability.db"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


def seed(factory, count=1, provider="wecom"):
    with factory() as db:
        number = db.scalar(select(func.count(User.id)))
        user = User(
            username=f"reliability-{number}",
            email=f"reliability-{number}@example.com",
            password_hash="unused",
        )
        db.add(user)
        db.flush()
        channel = NotificationChannel(
            user_id=user.id,
            name="News",
            provider=provider,
            encrypted_config=sender.encrypt_channel_config(
                {"webhook_url": "https://notify.example.com/hook"}
            ),
        )
        db.add(channel)
        db.flush()
        deliveries = [
            NotificationDelivery(
                user_id=user.id,
                channel_id=channel.id,
                channel_name=channel.name,
                provider=provider,
                article_title=f"Article {i}",
                message="Message",
            )
            for i in range(count)
        ]
        db.add_all(deliveries)
        db.flush()
        channel_id, ids = channel.id, [delivery.id for delivery in deliveries]
        db.commit()
        return channel_id, ids


def test_100_messages_are_paced_and_all_delivered_without_exhausting_retries(
    notification_sessions, monkeypatch
):
    _, ids = seed(notification_sessions, 100)
    now = as_utc(tasks.utc_now())
    monkeypatch.setattr(tasks, "utc_now", lambda: now)
    with notification_sessions() as db:
        assert tasks.queue_pending_deliveries(db) == ids
        schedule = dict(
            db.execute(select(NotificationDelivery.id, NotificationDelivery.next_attempt_at)).all()
        )
        recent = []
        for delivery_id in ids:
            now = as_utc(schedule[delivery_id])
            job = tasks.claim_delivery(db, delivery_id)
            assert job
            recent = [timestamp for timestamp in recent if now - timestamp < timedelta(minutes=1)]
            assert len(recent) < 20
            recent.append(now)
            tasks.finish_delivery(db, delivery_id, None)
        rows = db.scalars(select(NotificationDelivery)).all()
        assert len(rows) == 100
        assert all(
            row.status == "sent" and row.attempts == 1 and row.failure_attempts == 0 for row in rows
        )


def test_two_workers_cannot_send_the_same_channel_at_once(notification_sessions, monkeypatch):
    _, ids = seed(notification_sessions, 2)
    now = as_utc(tasks.utc_now())
    monkeypatch.setattr(tasks, "utc_now", lambda: now)

    def claim(delivery_id):
        with notification_sessions() as db:
            return tasks.claim_delivery(db, delivery_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, ids))
    assert sum(result is not None for result in results) == 1
    with notification_sessions() as db:
        rows = db.scalars(select(NotificationDelivery)).all()
        assert sorted(row.attempts for row in rows) == [0, 1]
        assert sorted(row.status for row in rows) == ["pending", "sending"]


def test_waiting_for_a_database_lock_does_not_use_a_stale_send_timestamp(
    notification_sessions, monkeypatch
):
    channel_id, ids = seed(notification_sessions)
    now = as_utc(tasks.utc_now())
    entered = threading.Event()

    def current_time():
        snapshot = now
        entered.set()
        return snapshot

    monkeypatch.setattr(tasks, "utc_now", current_time)

    def claim():
        with notification_sessions() as db:
            return tasks.claim_delivery(db, ids[0])

    with notification_sessions() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        blocker.execute(
            update(NotificationChannel)
            .where(NotificationChannel.id == channel_id)
            .values(next_send_at=None)
        )
        future = executor.submit(claim)
        assert entered.wait(2)
        now += timedelta(seconds=10)
        blocker.commit()
        assert future.result(timeout=3)
    with notification_sessions() as db:
        assert as_utc(db.get(NotificationChannel, channel_id).next_send_at) >= now + timedelta(
            seconds=3.1
        )


def test_channels_keep_independent_pacing_and_new_batches_do_not_overlap(
    notification_sessions, monkeypatch
):
    first, first_ids = seed(notification_sessions, 2)
    second, second_ids = seed(notification_sessions, 1)
    now = as_utc(tasks.utc_now())
    monkeypatch.setattr(tasks, "utc_now", lambda: now)
    with notification_sessions() as db:
        tasks.queue_pending_deliveries(db)
        assert tasks.claim_delivery(db, first_ids[0])
        assert tasks.claim_delivery(db, second_ids[0])
        assert tasks.claim_delivery(db, first_ids[1]) is None
        channel = db.get(NotificationChannel, first)
        db.add(
            NotificationDelivery(
                user_id=channel.user_id,
                channel_id=first,
                channel_name="News",
                provider="wecom",
                article_title="Later",
                message="Message",
            )
        )
        db.commit()
        tasks.queue_pending_deliveries(db)
        slots = list(
            db.scalars(
                select(NotificationDelivery.next_attempt_at)
                .where(
                    NotificationDelivery.channel_id == first,
                    NotificationDelivery.status == "queued",
                )
                .order_by(NotificationDelivery.next_attempt_at)
            )
        )
        assert all(as_utc(slot) > now for slot in slots)
        assert len(slots) == len(set(slots))


def test_scheduled_message_is_not_recovered_or_sent_before_its_eta(
    notification_sessions, monkeypatch
):
    _, ids = seed(notification_sessions, 100)
    now = as_utc(tasks.utc_now())
    monkeypatch.setattr(tasks, "utc_now", lambda: now)
    with notification_sessions() as db:
        tasks.queue_pending_deliveries(db)
        future_id = ids[-1]
        assert tasks.claim_delivery(db, future_id) is None
        now += timedelta(minutes=5, seconds=1)
        tasks.queue_pending_deliveries(db)
        assert db.get(NotificationDelivery, future_id).status == "queued"
        assert db.get(NotificationDelivery, future_id).attempts == 0


def test_rate_limits_wait_without_consuming_failure_budget_and_pause_sibling_messages(
    notification_sessions, monkeypatch
):
    channel_id, ids = seed(notification_sessions, 2)
    now = as_utc(tasks.utc_now())
    monkeypatch.setattr(tasks, "utc_now", lambda: now)
    failure = sender.NotificationSendError("Rate limit", True, 3600, rate_limited=True)
    with notification_sessions() as db:
        for attempt in range(5):
            assert tasks.claim_delivery(db, ids[0])
            tasks.finish_delivery(db, ids[0], failure)
            delivery = db.get(NotificationDelivery, ids[0])
            assert delivery.status == "pending" and delivery.failure_attempts == 0
            assert delivery.attempts == attempt + 1
            assert as_utc(delivery.next_attempt_at) == now + timedelta(hours=1)
            assert tasks.claim_delivery(db, ids[1]) is None
            now += timedelta(hours=1, seconds=1)
        assert tasks.claim_delivery(db, ids[0])
        tasks.finish_delivery(db, ids[0], None)
        assert db.get(NotificationDelivery, ids[0]).status == "sent"
        assert db.get(NotificationChannel, channel_id).next_send_at is not None


def test_retry_after_supports_http_dates_and_long_channel_cooldowns():
    header = format_datetime(datetime.now(UTC) + timedelta(minutes=10), usegmt=True)
    failure = sender.NotificationSendError("Throttled", True, header, rate_limited=True)
    assert 590 <= failure.retry_after <= 600
    assert (
        sender.NotificationSendError("Throttled", True, 3600, rate_limited=True).retry_after == 3600
    )


def test_dispatch_passes_reserved_countdowns_and_recovers_unpublished_rows(
    notification_sessions, monkeypatch
):
    _, ids = seed(notification_sessions, 3)
    now = as_utc(tasks.utc_now())
    monkeypatch.setattr(tasks, "utc_now", lambda: now)
    monkeypatch.setattr(tasks, "get_session", notification_sessions)
    from app.tasks.celery_app import celery_app

    countdowns = []

    def publish(name, **options):
        countdowns.append(options["countdown"])
        assert name == "app.tasks.notification_tasks.send_delivery"
        assert options["queue"] == "celery"
        if len(countdowns) == 2:
            raise OSError("Queue unavailable")

    monkeypatch.setattr(celery_app, "send_task", publish)
    result = tasks.dispatch_pending()
    assert result == {"dispatched": 1, "queue_unavailable": True}
    assert countdowns == [0, pytest.approx(3.3)]
    with notification_sessions() as db:
        rows = [db.get(NotificationDelivery, delivery_id) for delivery_id in ids]
        assert [row.status for row in rows] == ["queued", "pending", "pending"]
        assert all(row.attempts == 0 for row in rows)
        assert rows[1].next_attempt_at is not None and rows[2].next_attempt_at is not None


class ProxyStub:
    url = "http://unused.invalid"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class ResponseStream(httpx.AsyncByteStream):
    def __init__(self, chunks=100, delay=0):
        self.chunks, self.delay, self.read_bytes, self.closed = chunks, delay, 0, False

    async def __aiter__(self):
        for _ in range(self.chunks):
            if self.delay:
                await asyncio.sleep(self.delay)
            self.read_bytes += 8192
            yield b"x" * 8192

    async def aclose(self):
        self.closed = True


def response_transport(monkeypatch, status, stream, headers=None):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(sender, "SafeBrowserProxy", ProxyStub)
    monkeypatch.setattr(sender, "validate_outbound_http_url", AsyncMock())

    def handle(request):
        assert request.headers["Accept-Encoding"] == "identity"
        return httpx.Response(status, stream=stream, headers=headers)

    monkeypatch.setattr(
        sender.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handle),
            follow_redirects=False,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 204, 400, 503])
async def test_webhook_acceptance_and_http_errors_close_without_reading_bodies(monkeypatch, status):
    stream = ResponseStream(chunks=1000)
    response_transport(monkeypatch, status, stream)
    if status < 300:
        await sender.send_notification(
            "webhook", {"webhook_url": "https://notify.example.com"}, "Message"
        )
    else:
        with pytest.raises(sender.NotificationSendError):
            await sender.send_notification(
                "webhook", {"webhook_url": "https://notify.example.com"}, "Message"
            )
    assert stream.read_bytes == 0 and stream.closed


@pytest.mark.asyncio
async def test_provider_acknowledgement_stops_at_64_kib_and_requires_manual_confirmation(
    monkeypatch,
):
    stream = ResponseStream()
    response_transport(monkeypatch, 200, stream)
    with pytest.raises(sender.NotificationSendError) as error:
        await sender.send_notification(
            "feishu",
            {"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/dummy"},
            "Message",
        )
    assert "64 KiB" in str(error.value) and not error.value.retryable
    assert stream.read_bytes <= sender.MAX_NOTIFICATION_RESPONSE_BYTES + 8192 and stream.closed


@pytest.mark.asyncio
async def test_compressed_acknowledgement_is_not_inflated(monkeypatch):
    stream = ResponseStream()
    response_transport(monkeypatch, 200, stream, {"Content-Encoding": "gzip"})
    with pytest.raises(sender.NotificationSendError):
        await sender.send_notification(
            "feishu",
            {"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/dummy"},
            "Message",
        )
    assert stream.read_bytes == 0 and stream.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("status,limited", [(200, False), (429, True)])
async def test_slow_response_has_an_overall_deadline_and_retains_known_throttling(
    monkeypatch, status, limited
):
    stream = ResponseStream(delay=0.01)
    response_transport(monkeypatch, status, stream, {"Retry-After": "90"})
    monkeypatch.setattr(sender, "NOTIFICATION_HTTP_TIMEOUT_SECONDS", 0.025)
    with pytest.raises(sender.NotificationSendError) as error:
        await sender.send_notification(
            "feishu",
            {"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/dummy"},
            "Message",
        )
    assert error.value.rate_limited == limited and stream.closed
    assert error.value.retryable == limited


@pytest.mark.asyncio
@pytest.mark.parametrize("status,limited", [(200, False), (429, True)])
async def test_broken_response_retains_received_throttling_without_exposing_errors(
    monkeypatch, status, limited
):
    class BrokenStream(ResponseStream):
        async def __aiter__(self):
            yield b"x"
            raise httpx.ReadError("private-response-token")

    stream = BrokenStream()
    response_transport(monkeypatch, status, stream, {"Retry-After": "90"})
    with pytest.raises(sender.NotificationSendError) as error:
        await sender.send_notification(
            "feishu",
            {"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/dummy"},
            "Message",
        )
    assert error.value.rate_limited == limited and error.value.retryable == limited
    assert "private-response-token" not in str(error.value) and stream.closed


class SMTPStub:
    failure = None
    refused = {}

    def __init__(self, *_a, **_kw):
        pass

    def starttls(self, **_kw):
        pass

    def login(self, *_a):
        pass

    def send_message(self, mail):
        if self.failure:
            raise self.failure
        return self.refused

    def close(self):
        pass


@pytest.mark.parametrize("code,retryable", [(450, True), (451, True), (452, True), (550, False)])
def test_all_temporarily_refused_smtp_recipients_are_retryable(monkeypatch, code, retryable):
    monkeypatch.setattr(email, "PinnedSMTP", SMTPStub)
    monkeypatch.setattr(
        SMTPStub,
        "failure",
        smtplib.SMTPRecipientsRefused({"reader@example.com": (code, b"dummy-password")}),
    )
    with pytest.raises(sender.NotificationSendError) as error:
        email._send_email(EMAIL_CONFIG, "93.184.216.34", "Message", "Title")
    assert error.value.retryable == retryable and "dummy-password" not in str(error.value)


def test_partial_smtp_acceptance_remains_non_retryable(monkeypatch):
    monkeypatch.setattr(email, "PinnedSMTP", SMTPStub)
    monkeypatch.setattr(SMTPStub, "refused", {"reader@example.com": (450, b"Temporary failure")})
    with pytest.raises(sender.NotificationSendError) as error:
        email._send_email(
            {**EMAIL_CONFIG, "smtp_to": ["reader@example.com", "other@example.com"]},
            "93.184.216.34",
            "Message",
            "Title",
        )
    assert not error.value.retryable


async def account(db, name):
    user = User(username=name, email=f"{name}@example.com", password_hash="unused")
    db.add(user)
    await db.commit()
    headers = {
        "Authorization": "Bearer "
        + create_access_token({"sub": str(user.id), "token_version": user.token_version})
    }
    return user.id, headers


@pytest.mark.asyncio
async def test_new_unicode_credentials_are_rejected_and_legacy_ones_record_a_safe_failure(
    client, db_session, monkeypatch
):
    _, headers = await account(db_session, "unicode-mail")
    invalid = {**EMAIL_CONFIG, "smtp_password": "测试Password"}
    response = await client.post(
        f"{PREFIX}/channels",
        headers=headers,
        json={"name": "Mail", "provider": "email", "config": invalid},
    )
    assert response.status_code == 422 and "测试Password" not in response.text
    created = await client.post(
        f"{PREFIX}/channels",
        headers=headers,
        json={"name": "Mail", "provider": "email", "config": EMAIL_CONFIG},
    )
    channel_id = created.json()["id"]
    channel = await db_session.get(NotificationChannel, channel_id)
    channel.encrypted_config = sender.encrypt_channel_config(invalid)
    await db_session.commit()

    class LegacySMTP(SMTPStub, smtplib.SMTP):
        def __init__(self, *_a, **_kw):
            self.esmtp_features = {"auth": "PLAIN"}

        login = smtplib.SMTP.login

        def ehlo_or_helo_if_needed(self):
            pass

        def docmd(self, *_a):
            return 235, b"OK"

    monkeypatch.setattr(email, "PinnedSMTP", LegacySMTP)
    monkeypatch.setattr(
        email, "resolve_outbound_http_url", AsyncMock(return_value=["93.184.216.34"])
    )
    tested = await client.post(f"{PREFIX}/channels/{channel_id}/test", headers=headers)
    assert tested.status_code == 200 and not tested.json()["success"]
    history = (await client.get(f"{PREFIX}/deliveries", headers=headers)).json()
    assert len(history["items"]) == 1 and history["items"][0]["status"] == "failed"
    assert "测试Password" not in json.dumps(history, ensure_ascii=False)


@pytest.mark.asyncio
async def test_orphan_rule_backup_restores_into_a_new_account_without_allowing_empty_api_rules(
    client, db_session
):
    user_id, headers = await account(db_session, "orphan-original")
    feed = Feed(user_id=user_id, title="News", url="https://example.com/rss")
    db_session.add(feed)
    await db_session.commit()
    feed_id = feed.id
    channel = (
        await client.post(
            f"{PREFIX}/channels",
            headers=headers,
            json={
                "name": "Disposable",
                "provider": "webhook",
                "config": {"webhook_url": "https://notify.example.com"},
            },
        )
    ).json()
    rule = await client.post(
        f"{PREFIX}/rules",
        headers=headers,
        json={
            "name": "Updates",
            "source_type": "feed",
            "source_id": feed_id,
            "channel_ids": [channel["id"]],
        },
    )
    assert rule.status_code == 201
    await client.delete(f"{PREFIX}/channels/{channel['id']}", headers=headers)
    backup = await generate_backup_data(db_session, user_id)
    assert backup["notification_rules"][0]["channel_names"] == []
    restored_id, restored_headers = await account(db_session, "orphan-restored")
    imported = await import_backup_data(db_session, restored_id, backup)
    await db_session.commit()
    assert imported.success, imported.errors
    rules = (await client.get(f"{PREFIX}/rules", headers=restored_headers)).json()
    assert len(rules) == 1 and rules[0]["name"] == "Updates" and rules[0]["channel_ids"] == []
    response = await client.post(
        f"{PREFIX}/rules",
        headers=restored_headers,
        json={
            "name": "Empty new",
            "source_type": "feed",
            "source_id": rules[0]["source_id"],
            "channel_ids": [],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_testing_a_disabled_channel_still_works_and_test_sends_share_the_budget(
    client, db_session, monkeypatch
):
    _, headers = await account(db_session, "test-budget")
    channel = (
        await client.post(
            f"{PREFIX}/channels",
            headers=headers,
            json={
                "name": "Disabled",
                "provider": "webhook",
                "config": {"webhook_url": "https://notify.example.com"},
                "is_enabled": False,
            },
        )
    ).json()
    from app.api.v1.endpoints import external_notifications as endpoints

    send = AsyncMock()
    monkeypatch.setattr(endpoints, "send_notification", send)
    first = await client.post(f"{PREFIX}/channels/{channel['id']}/test", headers=headers)
    second = await client.post(f"{PREFIX}/channels/{channel['id']}/test", headers=headers)
    assert first.json()["success"] and not second.json()["success"]
    send.assert_awaited_once()


@pytest.mark.asyncio
async def test_platform_throttle_on_test_send_also_pauses_automatic_delivery(
    client, db_session, monkeypatch
):
    user_id, headers = await account(db_session, "test-throttle")
    channel = (
        await client.post(
            f"{PREFIX}/channels",
            headers=headers,
            json={
                "name": "Throttled",
                "provider": "webhook",
                "config": {"webhook_url": "https://notify.example.com"},
            },
        )
    ).json()
    from app.api.v1.endpoints import external_notifications as endpoints

    monkeypatch.setattr(
        endpoints,
        "send_notification",
        AsyncMock(
            side_effect=sender.NotificationSendError("Throttled", True, 60, rate_limited=True)
        ),
    )
    tested = await client.post(f"{PREFIX}/channels/{channel['id']}/test", headers=headers)
    assert tested.status_code == 200 and not tested.json()["success"]
    delivery = NotificationDelivery(
        user_id=user_id,
        channel_id=channel["id"],
        channel_name="Throttled",
        provider="webhook",
        article_title="New article",
        message="Message",
    )
    db_session.add(delivery)
    await db_session.commit()
    assert (
        await db_session.run_sync(lambda session: tasks.claim_delivery(session, delivery.id))
        is None
    )
    await db_session.refresh(delivery)
    assert delivery.status == "pending" and delivery.attempts == 0
    assert as_utc(delivery.next_attempt_at) > as_utc(tasks.utc_now()) + timedelta(seconds=50)
