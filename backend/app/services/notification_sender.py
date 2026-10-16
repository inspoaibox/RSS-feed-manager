"""Provider payloads, encrypted credentials and safe notification transport."""

import asyncio
import base64
import contextvars
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import ceil
from urllib.parse import parse_qs, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.utils.browser_proxy import SafeBrowserProxy
from app.utils.url_security import (
    UnsafeOutboundURLError,
    _address_is_public,
    validate_outbound_http_url,
)

SECRET_CONFIG_FIELDS = (
    "webhook_url",
    "signing_secret",
    "bot_token",
    "server_url",
    "device_key",
    "pushplus_token",
    "serverchan_send_key",
    "smtp_password",
)
_notification_logging = contextvars.ContextVar("notification_logging", default=False)
MAX_NOTIFICATION_RESPONSE_BYTES = 64 * 1024
NOTIFICATION_HTTP_TIMEOUT_SECONDS = 20


def redact_notification_url(value: str) -> str:
    if _notification_logging.get():
        # Custom endpoints may put credentials anywhere in the path or query string.
        return re.sub(r"https?://[^\s\"'<>]+", "https://[REDACTED]", value)
    value = re.sub(r"(/bot)\d+:[A-Za-z0-9_-]+", r"\1[REDACTED]", value)
    value = re.sub(r"(/open-apis/bot/v2/hook/)[A-Za-z0-9-]+", r"\1[REDACTED]", value)
    value = re.sub(r"([?&]key=)[^&\s]+", r"\1[REDACTED]", value)
    return re.sub(
        r"(https://(?:sctapi\.ftqq\.com/|\d+\.push\.ft07\.com/send/))[^\s]+",
        r"\1[REDACTED]",
        value,
    )


class NotificationURLFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_notification_url(str(record.msg))
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_notification_url(str(value))
                if isinstance(value, (str, httpx.URL))
                else value
                for value in record.args
            )
        return True


logging.getLogger("httpx").addFilter(NotificationURLFilter())


class NotificationSendError(Exception):
    def __init__(
        self,
        message: str,
        retryable: bool = False,
        retry_after: int = 30,
        *,
        rate_limited: bool = False,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.rate_limited = rate_limited
        try:
            seconds = int(retry_after)
        except (ValueError, TypeError, OverflowError):
            seconds = 30
            if rate_limited and isinstance(retry_after, str):
                try:
                    deadline = parsedate_to_datetime(retry_after)
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=UTC)
                    seconds = ceil((deadline - datetime.now(UTC)).total_seconds())
                except (ValueError, TypeError, OverflowError):
                    pass
        self.retry_after = min(86400 if rate_limited else 300, max(1, seconds))


def credential_cipher() -> Fernet:
    secret = settings.NOTIFICATION_ENCRYPTION_KEY or settings.SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt_channel_config(config: dict) -> str:
    return credential_cipher().encrypt(json.dumps(config).encode()).decode()


def decrypt_channel_config(encrypted: str) -> dict:
    try:
        return json.loads(credential_cipher().decrypt(encrypted.encode()))
    except (InvalidToken, ValueError) as exc:
        raise NotificationSendError("通知凭据无法解密，请重新保存频道配置") from exc


def checked_https_url(value: str, label: str, *, base_url: bool = False):
    try:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or (parsed.port is not None and not 1 <= parsed.port <= 65535)
            or any(char.isspace() or ord(char) < 32 or char == "\\" for char in value)
            or (base_url and parsed.query)
        ):
            raise ValueError
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname):
                raise ValueError from None
        else:
            if not settings.ALLOW_PRIVATE_FETCH_URLS and not _address_is_public(parsed.hostname):
                raise ValueError
        return parsed
    except ValueError:
        raise ValueError(f"{label}必须是有效的 HTTPS 地址，不允许内网 IP、凭据或片段") from None


def _checked_token(value: str | None, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", value or ""):
        raise ValueError(f"{label}格式无效，请填写密钥而非完整推送地址")
    return value


def _validate_webhook_options(config: dict) -> dict:
    headers = config.get("webhook_headers") or {}
    if len(headers) > 20:
        raise ValueError("自定义请求头最多 20 个")
    for key, value in headers.items():
        if (
            not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,100}", key)
            or key.lower()
            in {"host", "content-length", "connection", "transfer-encoding", "upgrade"}
            or key.lower().startswith("proxy-")
            or len(value) > 4096
            or any(ord(char) < 32 or ord(char) > 126 for char in value)
        ):
            raise ValueError("请求头格式无效，请勿覆盖 Host、连接或消息长度等传输头")
        if key.lower() == "content-type" and not re.fullmatch(
            r"application/(?:json|[a-z0-9.+-]+\+json)(?:\s*;.*)?", value, re.I
        ):
            raise ValueError("通用 Webhook 的请求体为 JSON，请使用 JSON Content-Type")
    body = config.get("webhook_body")
    if body is not None:
        try:
            encoded = json.dumps(body, allow_nan=False)
            if len(encoded) > 20000:
                raise ValueError
            placeholders = re.findall(r"\{\{\s*([^{}]*?)\s*\}\}", encoded)
            if any(value.strip() not in {"title", "message"} for value in placeholders):
                raise ValueError
        except (ValueError, TypeError, RecursionError):
            raise ValueError(
                "请求体必须是有效 JSON 对象（最多 20000 字符），仅支持 {{title}} 和 {{message}}"
            ) from None
    method = config.get("webhook_method") or "POST"
    if method not in {"POST", "PUT"}:
        raise ValueError("通用 Webhook 仅支持 POST 或 PUT")
    return {"webhook_method": method, "webhook_headers": headers, "webhook_body": body}


def validate_channel_config(provider: str, config: dict) -> dict:
    config = {
        key: value.strip() if isinstance(value, str) and key != "smtp_password" else value
        for key, value in config.items()
    }
    if provider == "feishu":
        url = checked_https_url(config.get("webhook_url") or "", "飞书 Webhook")
        if (
            url.scheme != "https"
            or url.hostname not in {"open.feishu.cn", "open.larksuite.com"}
            or url.username
            or url.password
            or url.port not in {None, 443}
            or not re.fullmatch(r"/open-apis/bot/v2/hook/[A-Za-z0-9-]+", url.path)
            or url.query
            or url.fragment
        ):
            raise ValueError("请填写飞书或 Lark 自定义机器人的 HTTPS Webhook 地址")
        return {
            "webhook_url": config["webhook_url"],
            "signing_secret": config.get("signing_secret") or None,
        }
    if provider == "telegram":
        if not re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{20,}", config.get("bot_token") or ""):
            raise ValueError("Telegram Bot Token 格式无效")
        if not re.fullmatch(r"-?\d+|@[A-Za-z][A-Za-z0-9_]{4,}", config.get("chat_id") or ""):
            raise ValueError("请填写 Telegram Chat ID 或 @频道用户名")
        return {
            "bot_token": config["bot_token"],
            "chat_id": config["chat_id"],
            "message_thread_id": config.get("message_thread_id"),
        }
    if provider == "wecom":
        url = checked_https_url(config.get("webhook_url") or "", "企业微信 Webhook")
        params = parse_qs(url.query)
        if (
            url.hostname != "qyapi.weixin.qq.com"
            or url.port not in {None, 443}
            or url.path != "/cgi-bin/webhook/send"
            or set(params) != {"key"}
            or len(params["key"]) != 1
            or not re.fullmatch(r"[A-Za-z0-9_-]+", params["key"][0])
        ):
            raise ValueError("请填写企业微信群消息推送的 HTTPS Webhook 地址")
        return {"webhook_url": config["webhook_url"]}
    if provider == "email":
        from app.services.notification_email import validate_email_config

        return validate_email_config(config)
    if provider == "bark":
        server = config.get("server_url") or "https://api.day.app"
        checked_https_url(server, "Bark 服务器", base_url=True)
        return {
            "server_url": server.rstrip("/"),
            "device_key": _checked_token(config.get("device_key"), "Bark Device Key"),
            "bark_group": config.get("bark_group") or "RSS",
        }
    if provider == "pushplus":
        channel = config.get("pushplus_channel") or "wechat"
        if channel not in {"wechat", "app", "mail", "webhook", "cp", "extension", "qq"}:
            raise ValueError("PushPlus 接收渠道无效")
        if channel in {"mail", "webhook", "cp"} and not config.get("pushplus_option"):
            raise ValueError("所选 PushPlus 渠道需要填写在 PushPlus 后台创建的渠道编码")
        return {
            "pushplus_token": _checked_token(config.get("pushplus_token"), "PushPlus Token"),
            "pushplus_channel": channel,
            "pushplus_topic": config.get("pushplus_topic") or None,
            "pushplus_option": config.get("pushplus_option") or None,
        }
    if provider == "serverchan":
        key = config.get("serverchan_send_key") or ""
        if not re.fullmatch(r"SCT[A-Za-z0-9_-]+|(?:sctp|sc3)\d+t[A-Za-z0-9_-]+", key):
            raise ValueError("请填写 Server酱 Turbo 或 Server酱³ 的 SendKey")
        return {"serverchan_send_key": key}
    if provider == "webhook":
        checked_https_url(config.get("webhook_url") or "", "Webhook")
        return {"webhook_url": config["webhook_url"], **_validate_webhook_options(config)}
    raise ValueError("不支持的通知应用")


def _message_title(title: str) -> str:
    return " ".join(title.split())[:100] or "RSS 订阅更新"


def _render_webhook_body(value, title: str, message: str):
    if isinstance(value, str):
        return re.sub(
            r"\{\{\s*(title|message)\s*\}\}",
            lambda match: title if match[1] == "title" else message,
            value,
        )
    if isinstance(value, list):
        return [_render_webhook_body(item, title, message) for item in value]
    if isinstance(value, dict):
        return {key: _render_webhook_body(item, title, message) for key, item in value.items()}
    return value


def _wecom_text(message: str) -> str:
    # Preserve the article link when a long title/source exceeds WeCom's UTF-8 limit.
    head, marker, link = message.rpartition("\n原文：")
    suffix = marker + link if marker and len(link.encode()) < 1024 else ""
    content = head if suffix else message
    return content.encode()[: 2048 - len(suffix.encode())].decode("utf-8", errors="ignore") + suffix


def build_provider_request(
    provider: str, config: dict, message: str, *, title: str = "RSS 订阅更新"
) -> tuple[str, dict]:
    title = _message_title(title)
    if provider == "feishu":
        payload = {"msg_type": "text", "content": {"text": message[:4000]}}
        if config.get("signing_secret"):
            timestamp = str(int(time.time()))
            key = f"{timestamp}\n{config['signing_secret']}".encode()
            payload.update(
                timestamp=timestamp,
                sign=base64.b64encode(hmac.new(key, b"", hashlib.sha256).digest()).decode(),
            )
        return config["webhook_url"], payload
    if provider == "telegram":
        payload = {
            "chat_id": config["chat_id"],
            "text": message[:4000],
            "link_preview_options": {"is_disabled": True},
        }
        if config.get("message_thread_id"):
            payload["message_thread_id"] = config["message_thread_id"]
        return f"https://api.telegram.org/bot{config['bot_token']}/sendMessage", payload
    if provider == "wecom":
        return config["webhook_url"], {"msgtype": "text", "text": {"content": _wecom_text(message)}}
    if provider == "bark":
        payload = {
            "device_key": config["device_key"],
            "title": title,
            "body": message,
            "group": config.get("bark_group") or "RSS",
        }
        return config["server_url"] + "/push", payload
    if provider == "pushplus":
        payload = {
            "token": config["pushplus_token"],
            "title": title,
            "content": message,
            "template": "txt",
            "channel": config["pushplus_channel"],
        }
        for key in ("topic", "option"):
            if config.get(f"pushplus_{key}"):
                payload[key] = config[f"pushplus_{key}"]
        return "https://www.pushplus.plus/send", payload
    if provider == "serverchan":
        key = config["serverchan_send_key"]
        uid = re.match(r"^(?:sctp|sc3)(\d+)t", key)
        url = (
            f"https://{uid[1]}.push.ft07.com/send/{key}.send"
            if uid
            else f"https://sctapi.ftqq.com/{key}.send"
        )
        return url, {"title": title, "desp": message}
    if provider == "webhook":
        body = config.get("webhook_body")
        if body is None:
            body = {"title": "{{title}}", "message": "{{message}}"}
        return config["webhook_url"], _render_webhook_body(body, title, message)
    raise NotificationSendError("不支持的通知应用")


async def _bounded_response_json(response: httpx.Response) -> dict:
    # Small acknowledgement responses need no compression; never inflate untrusted bodies.
    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
        raise NotificationSendError("通知服务返回不支持的压缩响应，结果未知，请确认后再重试")
    body = bytearray()
    if response.is_stream_consumed:
        # Mock transports may supply an already-buffered response.
        body.extend(response.content)
    else:
        async for chunk in response.aiter_raw(chunk_size=8192):
            if len(body) + len(chunk) > MAX_NOTIFICATION_RESPONSE_BYTES:
                raise NotificationSendError("通知服务响应超过 64 KiB，结果未知，请确认后再重试")
            body.extend(chunk)
    if len(body) > MAX_NOTIFICATION_RESPONSE_BYTES:
        raise NotificationSendError("通知服务响应超过 64 KiB，结果未知，请确认后再重试")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise NotificationSendError("通知服务返回无效响应，结果未知，请确认后再重试") from None
    if not isinstance(data, dict):
        raise NotificationSendError("通知服务返回无效响应，结果未知，请确认后再重试")
    return data


async def _send_http_notification(
    provider: str,
    config: dict,
    message: str,
    title: str,
    response_state: dict,
) -> None:
    url, payload = build_provider_request(provider, config, message, title=title)
    if provider in {"bark", "webhook"}:
        try:
            await validate_outbound_http_url(url)
        except UnsafeOutboundURLError:
            raise NotificationSendError("目标地址无法解析或不允许访问，请检查服务器地址") from None
    headers = httpx.Headers(config.get("webhook_headers") or {} if provider == "webhook" else {})
    headers["Accept-Encoding"] = "identity"
    method = config.get("webhook_method", "POST") if provider == "webhook" else "POST"
    async with SafeBrowserProxy() as proxy:
        async with httpx.AsyncClient(
            proxy=proxy.url, trust_env=False, timeout=15, follow_redirects=False
        ) as client:
            async with client.stream(method, url, json=payload, headers=headers) as response:
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", 30)
                    response_state.update(rate_limited=True, retry_after=retry_after)
                    try:
                        data = await _bounded_response_json(response)
                        parameters = data.get("parameters")
                        if isinstance(parameters, dict):
                            retry_after = parameters.get("retry_after", retry_after)
                    except NotificationSendError:
                        # The HTTP status already proves throttling, even with a bad body.
                        pass
                    response_state["retry_after"] = retry_after
                    raise NotificationSendError(
                        "通知服务限流，稍后自动重试", True, retry_after, rate_limited=True
                    )
                if response.status_code >= 500:
                    raise NotificationSendError("通知服务暂时不可用", retryable=True)
                if not 200 <= response.status_code < 300:
                    raise NotificationSendError(
                        f"通知服务拒绝请求（HTTP {response.status_code}），请检查凭据、权限和地址"
                    )
                if provider == "webhook":
                    # Acceptance only needs the status; do not read any optional response body.
                    return
                data = await _bounded_response_json(response)
    accepted = {
        "feishu": data.get("code", data.get("StatusCode")) == 0,
        "telegram": data.get("ok") is True,
        "wecom": data.get("errcode") == 0,
        "bark": data.get("code") == 200,
        "pushplus": data.get("code") == 200,
        "serverchan": data.get("code") == 0,
    }.get(provider, False)
    if not accepted:
        code = data.get("errcode") if provider == "wecom" else data.get("code")
        if provider == "wecom" and code == 45009:
            raise NotificationSendError(
                "企业微信发送频率受限，稍后自动重试", True, 60, rate_limited=True
            )
        if provider == "pushplus" and code in {900, 905}:
            reason = "账户受限或额度耗尽" if code == 900 else "账户尚未完成实名认证"
            raise NotificationSendError(f"PushPlus {reason}，请在 PushPlus 后台处理后手动重试")
        reason = str(
            data.get("msg") or data.get("errmsg") or data.get("StatusMessage") or ""
        ).lower()
        if any(marker in reason for marker in ("too many", "rate limit", "频率", "限流")):
            raise NotificationSendError("通知应用限流，稍后自动重试", True, 60, rate_limited=True)
        raise NotificationSendError("通知应用未接受消息，请检查机器人、目标频道及安全设置")


async def send_notification(
    provider: str, config: dict, message: str, *, title: str = "RSS 订阅更新"
) -> None:
    if provider == "email":
        from app.services.notification_email import send_email_notification

        await send_email_notification(config, message, _message_title(title))
        return
    log_token = _notification_logging.set(True)
    response_state = {}
    try:
        async with asyncio.timeout(NOTIFICATION_HTTP_TIMEOUT_SECONDS):
            await _send_http_notification(provider, config, message, title, response_state)
    except TimeoutError:
        if response_state.get("rate_limited"):
            raise NotificationSendError(
                "通知服务限流，稍后自动重试", True, response_state["retry_after"], rate_limited=True
            ) from None
        raise NotificationSendError("通知发送超时，结果未知，请确认频道后再重试") from None
    except httpx.RequestError as exc:
        if response_state.get("rate_limited"):
            raise NotificationSendError(
                "通知服务限流，稍后自动重试", True, response_state["retry_after"], rate_limited=True
            ) from None
        retryable = isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ProxyError))
        reason = (
            "通知服务连接失败，稍后自动重试"
            if retryable
            else "发送结果未知，请确认频道是否收到消息后再重试"
        )
        raise NotificationSendError(reason, retryable=retryable) from None
    finally:
        _notification_logging.reset(log_token)
