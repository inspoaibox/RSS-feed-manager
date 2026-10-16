"""New provider isolation, backups, transports, TLS, and credential-safe failures."""

import json
import logging
import smtplib
import socket
import ssl
from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

from app.api.v1.endpoints import external_notifications as endpoints
from app.core.security import create_access_token
from app.models.article import Article
from app.models.external_notification import NotificationChannel, NotificationDelivery
from app.models.feed import Feed
from app.models.user import User
from app.services import notification_email as email
from app.services import notification_sender as sender
from app.services.backup_export import generate_backup_data
from app.services.backup_import import import_backup_data
from app.tasks.notification_tasks import claim_delivery, finish_delivery
from app.utils import url_security

PREFIX = "/api/v1/external-notifications"
CONFIGS = {
    "wecom": {"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=private-wecom"},
    "email": {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_security": "starttls",
        "smtp_username": "notify@example.com",
        "smtp_password": " private-smtp-password ",
        "smtp_from": "notify@example.com",
        "smtp_to": ["reader@example.com", "other@example.com"],
    },
    "bark": {
        "server_url": "https://bark.example.com",
        "device_key": "private-bark-key",
        "bark_group": "Tech",
    },
    "pushplus": {
        "pushplus_token": "private-pushplus-token",
        "pushplus_channel": "wechat",
        "pushplus_topic": "readers",
    },
    "serverchan": {"serverchan_send_key": "SCTprivateServerChanKey"},
    "webhook": {
        "webhook_url": "https://notify.example.com/private-hook?token=private-query-token",
        "webhook_method": "PUT",
        "webhook_headers": {"Authorization": "Bearer private-auth-token"},
        "webhook_body": {
            "event": "rss",
            "data": {"title": "{{title}}", "body": "{{message}}", "enabled": True},
        },
    },
}
SECRETS = {
    "wecom": "private-wecom",
    "email": "private-smtp-password",
    "bark": "private-bark-key",
    "pushplus": "private-pushplus-token",
    "serverchan": "SCTprivateServerChanKey",
    "webhook": "private-auth-token",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", CONFIGS)
async def test_new_channels_encrypt_isolate_preserve_and_restore(
    client, db_session, monkeypatch, provider
):
    users = [
        User(username=f"platform-{i}", email=f"platform-{i}@example.com", password_hash="unused")
        for i in range(2)
    ]
    db_session.add_all(users)
    await db_session.flush()
    feed = Feed(user_id=users[0].id, url="https://example.com/rss", title="News")
    db_session.add(feed)
    await db_session.commit()
    user_id, feed_id = users[0].id, feed.id
    headers = [
        {
            "Authorization": "Bearer "
            + create_access_token({"sub": str(user.id), "token_version": user.token_version})
        }
        for user in users
    ]
    response = await client.post(
        f"{PREFIX}/channels",
        headers=headers[0],
        json={
            "name": provider,
            "provider": provider,
            "config": CONFIGS[provider],
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert SECRETS[provider] not in response.text
    assert "private-query-token" not in response.text
    stored = (await db_session.execute(select(NotificationChannel))).scalar_one()
    original = sender.decrypt_channel_config(stored.encrypted_config)
    assert SECRETS[provider] not in stored.encrypted_config
    blank_secrets = {key: "" for key in sender.SECRET_CONFIG_FIELDS if key in original}
    edited = await client.put(
        f"{PREFIX}/channels/{data['id']}", headers=headers[0], json={"config": blank_secrets}
    )
    assert edited.status_code == 200, edited.text
    assert sender.decrypt_channel_config(stored.encrypted_config) == original
    assert (await client.get(f"{PREFIX}/channels", headers=headers[1])).json() == []
    for method, suffix in [("PUT", ""), ("DELETE", ""), ("POST", "/test")]:
        foreign = await client.request(
            method,
            f"{PREFIX}/channels/{data['id']}{suffix}",
            headers=headers[1],
            json={"name": "Hijack"} if method == "PUT" else None,
        )
        assert foreign.status_code == 404
    send = AsyncMock()
    monkeypatch.setattr(endpoints, "send_notification", send)
    assert (await client.post(f"{PREFIX}/channels/{data['id']}/test", headers=headers[0])).json()[
        "success"
    ]
    assert send.await_args.kwargs["title"] == "测试通知"
    routing = await client.post(
        f"{PREFIX}/rules",
        headers=headers[0],
        json={
            "name": "Updates",
            "source_type": "feed",
            "source_id": feed_id,
            "channel_ids": [data["id"]],
        },
    )
    assert routing.status_code == 201
    db_session.add(Article(feed_id=feed_id, guid="first", title="Actual article title"))
    await db_session.commit()
    delivery = (
        await db_session.execute(
            select(NotificationDelivery).where(NotificationDelivery.is_test.is_(False))
        )
    ).scalar_one()
    from app.tasks import notification_tasks

    next_slot = notification_tasks.utc_now() + timedelta(seconds=10)
    monkeypatch.setattr(notification_tasks, "utc_now", lambda: next_slot)
    job = await db_session.run_sync(lambda session: claim_delivery(session, delivery.id))
    assert job["provider"] == provider and job["title"] == "Actual article title"
    await db_session.run_sync(lambda session: finish_delivery(session, delivery.id, None))
    backup = await generate_backup_data(db_session, user_id)
    assert backup["notification_channels"][0]["config"] == original
    restored = await import_backup_data(db_session, user_id, backup)
    assert restored.success, restored.errors
    assert sender.decrypt_channel_config(stored.encrypted_config) == original


class ProxyStub:
    url = "http://safe-proxy.example"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def mock_http(monkeypatch, handle):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(sender, "SafeBrowserProxy", ProxyStub)
    monkeypatch.setattr(sender, "validate_outbound_http_url", AsyncMock())
    monkeypatch.setattr(
        sender.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handle),
            follow_redirects=kwargs["follow_redirects"],
            trust_env=False,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,response",
    [
        ("wecom", {"errcode": 0}),
        ("bark", {"code": 200}),
        ("pushplus", {"code": 200}),
        ("serverchan", {"code": 0}),
        ("webhook", None),
    ],
)
async def test_provider_requests_and_acceptance(monkeypatch, provider, response):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(204) if response is None else httpx.Response(200, json=response)

    mock_http(monkeypatch, handle)
    config = sender.validate_channel_config(provider, CONFIGS[provider])
    text = 'New article "quotes"\n原文：https://example.com/story'
    await sender.send_notification(provider, config, text, title="Actual title\nSecond line")
    request = requests[0]
    payload = json.loads(request.content)
    assert request.url.scheme == "https"
    if provider == "wecom":
        assert payload == {"msgtype": "text", "text": {"content": text}}
    elif provider == "bark":
        assert request.url.path == "/push" and payload["device_key"] == config["device_key"]
        assert payload["group"] == "Tech" and payload["title"] == "Actual title Second line"
    elif provider == "pushplus":
        assert payload["token"] == config["pushplus_token"] and payload["topic"] == "readers"
        assert payload["channel"] == "wechat" and payload["content"] == text
    elif provider == "serverchan":
        assert request.url.host == "sctapi.ftqq.com" and payload["desp"] == text
    else:
        assert (
            request.method == "PUT"
            and request.headers["Authorization"] == "Bearer private-auth-token"
        )
        assert payload["data"] == {
            "title": "Actual title Second line",
            "body": text,
            "enabled": True,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("status,retryable", [(429, True), (503, True), (302, False), (400, False)])
async def test_http_errors_are_handled_before_json_and_redirects_not_followed(
    monkeypatch, status, retryable
):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            status,
            text="private-auth-token",
            headers={"Retry-After": "90", "Location": "https://other.example/steal"},
        )

    mock_http(monkeypatch, handle)
    with pytest.raises(sender.NotificationSendError) as error:
        await sender.send_notification("webhook", CONFIGS["webhook"], "Message")
    assert len(requests) == 1 and error.value.retryable == retryable
    assert "private-auth-token" not in str(error.value)
    if status == 429:
        assert error.value.retry_after == 90


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,data,retryable",
    [
        ("wecom", {"errcode": 45009}, True),
        ("wecom", {"errcode": 40014}, False),
        ("pushplus", {"code": 900, "msg": "rate limit private-pushplus-token"}, False),
        ("pushplus", {"code": 905}, False),
        ("bark", {"code": 400}, False),
        ("serverchan", {"code": 400}, False),
    ],
)
async def test_application_failures_do_not_report_success_or_expose_secrets(
    monkeypatch, provider, data, retryable
):
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=data))
    with pytest.raises(sender.NotificationSendError) as error:
        await sender.send_notification(
            provider, sender.validate_channel_config(provider, CONFIGS[provider]), "Message"
        )
    assert error.value.retryable == retryable
    assert SECRETS[provider] not in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://notify.example.com/hook",
        "https://127.0.0.1/hook",
        "https://[::ffff:127.0.0.1]/hook",
        "https://notify.example.com:bad/hook",
        "https://notify.example.com:0/hook",
        "https://private-token@notify.example.com/hook",
        "https://notify.example.com/#fragment",
    ],
)
def test_unsafe_custom_targets_are_rejected(url):
    for provider, field in [("webhook", "webhook_url"), ("bark", "server_url")]:
        with pytest.raises(ValueError) as error:
            sender.validate_channel_config(provider, {**CONFIGS[provider], field: url})
        assert "private-token" not in str(error.value)


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "evil.example"},
        {"Content-Length": "0"},
        {"Authorization": "secret\r\nInjected: yes"},
        {"Proxy-Authorization": "secret"},
        {"Content-Type": "text/plain"},
        {"Authorization": "非 ASCII"},
    ],
)
def test_unsafe_webhook_headers_are_rejected(headers):
    with pytest.raises(ValueError):
        sender.validate_channel_config(
            "webhook", {**CONFIGS["webhook"], "webhook_headers": headers}
        )


def test_wecom_truncation_keeps_utf8_and_link():
    text = "标题：" + "新闻" * 1800 + "\n原文：https://example.com/story"
    _, payload = sender.build_provider_request("wecom", CONFIGS["wecom"], text)
    result = payload["text"]["content"]
    assert len(result.encode()) <= 2048 and result.endswith("原文：https://example.com/story")


@pytest.mark.parametrize("key", ["sctp123tPrivateKey", "sc3123tPrivateKey"])
def test_serverchan3_routes_to_the_matching_user_host(key):
    config = sender.validate_channel_config("serverchan", {"serverchan_send_key": key})
    url, _ = sender.build_provider_request("serverchan", config, "Message")
    assert url == f"https://123.push.ft07.com/send/{key}.send"


def test_webhook_template_validation_and_safe_value_substitution():
    with pytest.raises(ValueError):
        sender.validate_channel_config(
            "webhook", {**CONFIGS["webhook"], "webhook_body": {"text": "{{unknown}}"}}
        )
    with pytest.raises(ValueError):
        sender.validate_channel_config(
            "webhook", {**CONFIGS["webhook"], "webhook_body": {"number": float("nan")}}
        )
    config = sender.validate_channel_config(
        "webhook", {"webhook_url": "https://notify.example.com/hook"}
    )
    _, body = sender.build_provider_request(
        "webhook", config, '"}, "injected": true\n{{title}}', title="Heading"
    )
    assert body == {"title": "Heading", "message": '"}, "injected": true\n{{title}}'}


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["webhook", "bark", "email"])
async def test_private_dns_cannot_be_used_to_send_notifications(monkeypatch, provider):
    monkeypatch.setattr(
        url_security.socket,
        "getaddrinfo",
        lambda *_a, **_kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ],
    )
    factory = AsyncMock()
    monkeypatch.setattr(sender.httpx, "AsyncClient", factory)
    smtp = AsyncMock()
    monkeypatch.setattr(email, "_send_email", smtp)
    with pytest.raises(sender.NotificationSendError) as error:
        await sender.send_notification(
            provider, sender.validate_channel_config(provider, CONFIGS[provider]), "Message"
        )
    assert not error.value.retryable
    factory.assert_not_called()
    smtp.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["ssl", "starttls"])
async def test_email_pins_dns_and_authenticates_only_after_tls(monkeypatch, mode):
    events = []
    config = {**CONFIGS["email"], "smtp_security": mode}
    resolve = AsyncMock(return_value=["93.184.216.34"])
    monkeypatch.setattr(email, "resolve_outbound_http_url", resolve)

    class SMTPStub:
        def __init__(self, hostname, address, port, **kwargs):
            assert hostname == "smtp.example.com" and address == "93.184.216.34"
            if mode == "ssl":
                assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED
                events.append("tls")

        def starttls(self, context):
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            events.append("tls")

        def login(self, username, password):
            assert events == ["tls"] and password == " private-smtp-password "
            events.append("login")

        def send_message(self, mail):
            assert events == ["tls", "login"]
            assert mail["Subject"] == "Actual title Second line"
            assert "reader@example.com" in mail["To"] and "Plain message" in mail.get_content()
            events.append("send")
            return {}

        def close(self):
            events.append("close")

    monkeypatch.setattr(email, "PinnedSMTPSSL", SMTPStub)
    monkeypatch.setattr(email, "PinnedSMTP", SMTPStub)
    await sender.send_notification(
        "email", config, "Plain message", title="Actual title\nSecond line"
    )
    assert events == ["tls", "login", "send", "close"]
    resolve.assert_awaited_once_with("https://smtp.example.com:587")


@pytest.mark.parametrize(
    "failure,retryable",
    [
        (smtplib.SMTPAuthenticationError(535, b"private-smtp-password"), False),
        (smtplib.SMTPDataError(451, b"private-smtp-password"), True),
        (smtplib.SMTPServerDisconnected("private-smtp-password"), False),
        (ssl.SSLError("private-smtp-password"), False),
    ],
)
def test_smtp_failures_are_sanitized_and_ambiguous_sends_not_retried(
    monkeypatch, failure, retryable
):
    class SMTPStub:
        def __init__(self, *_a, **_kw):
            pass

        def starttls(self, **_kw):
            pass

        def login(self, *_a):
            pass

        def send_message(self, mail):
            raise failure

        def close(self):
            pass

    monkeypatch.setattr(email, "PinnedSMTP", SMTPStub)
    with pytest.raises(sender.NotificationSendError) as error:
        email._send_email(CONFIGS["email"], "93.184.216.34", "Message", "Title")
    assert error.value.retryable == retryable and "private-smtp-password" not in str(error.value)


def test_smtp_ssl_connects_to_pinned_ip_but_checks_original_hostname(monkeypatch):
    calls = []
    monkeypatch.setattr(
        smtplib.SMTP,
        "_get_socket",
        lambda self, host, port, timeout: calls.append(host) or "socket",
    )
    instance = email.PinnedSMTPSSL.__new__(email.PinnedSMTPSSL)
    instance._pinned_address = "93.184.216.34"
    instance._host = "smtp.example.com"

    class Context:
        def wrap_socket(self, sock, server_hostname):
            assert sock == "socket" and server_hostname == "smtp.example.com"
            return "tls-socket"

    instance.context = Context()
    assert instance._get_socket("smtp.example.com", 465, 10) == "tls-socket"
    assert calls == ["93.184.216.34"]


@pytest.mark.asyncio
async def test_custom_webhook_http_logs_never_include_url_credentials(monkeypatch, caplog):
    mock_http(monkeypatch, lambda request: httpx.Response(204))
    with caplog.at_level(logging.INFO, logger="httpx"):
        await sender.send_notification("webhook", CONFIGS["webhook"], "Message")
    assert "private-query-token" not in caplog.text and "private-hook" not in caplog.text
    assert "[REDACTED]" in caplog.text


@pytest.mark.asyncio
async def test_validation_responses_do_not_echo_invalid_credentials(client, db_session):
    user = User(
        username="invalid-config", email="invalid-config@example.com", password_hash="unused"
    )
    db_session.add(user)
    await db_session.commit()
    headers = {
        "Authorization": "Bearer "
        + create_access_token({"sub": str(user.id), "token_version": user.token_version})
    }
    for config in [
        {"pushplus_token": "private-token-" * 100},
        {"webhook_headers": {"Authorization": ["private-token"]}},
        {"unknown": "private-token"},
    ]:
        response = await client.post(
            f"{PREFIX}/channels",
            headers=headers,
            json={
                "name": "Invalid",
                "provider": "webhook",
                "config": config,
            },
        )
        assert response.status_code == 422 and "private-token" not in response.text
        assert all("input" not in error for error in response.json()["detail"])
