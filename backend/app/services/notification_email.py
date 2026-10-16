"""Encrypted SMTP transport with public DNS pinning and cautious delivery retries."""

import asyncio
import ipaddress
import re
import smtplib
import ssl
from email.message import EmailMessage

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.config import settings
from app.services.notification_sender import NotificationSendError
from app.utils.url_security import (
    UnsafeOutboundURLError,
    _address_is_public,
    resolve_outbound_http_url,
)


def validate_email_config(config: dict) -> dict:
    host = config.get("smtp_host") or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host):
            raise ValueError("SMTP 主机应为域名或 IP，不要填写协议、端口或路径") from None
    else:
        if not settings.ALLOW_PRIVATE_FETCH_URLS and not _address_is_public(host):
            raise ValueError("SMTP 主机不允许使用内网、回环或保留 IP")
    security = config.get("smtp_security") or "ssl"
    if security not in {"ssl", "starttls"}:
        raise ValueError("邮件通知仅支持 SSL/TLS 或 STARTTLS")
    username, password = config.get("smtp_username") or "", config.get("smtp_password") or ""
    if not username or not password:
        raise ValueError("请填写 SMTP 用户名和密码或授权码")
    if not username.isascii() or not password.isascii():
        raise ValueError("SMTP 用户名及密码/授权码仅支持 ASCII 字符，请使用邮箱的 SMTP 授权码")
    try:
        validator = TypeAdapter(EmailStr)
        from_address = str(validator.validate_python(config.get("smtp_from") or username))
        to_addresses = list(
            dict.fromkeys(
                str(validator.validate_python(value)) for value in config.get("smtp_to") or []
            )
        )
    except ValidationError:
        raise ValueError("发件人和收件人必须是有效邮箱地址") from None
    if not to_addresses or len(to_addresses) > 20:
        raise ValueError("请配置 1 至 20 个收件人")
    port = config.get("smtp_port") or (465 if security == "ssl" else 587)
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("SMTP 端口无效")
    return {
        "smtp_host": host,
        "smtp_port": port,
        "smtp_security": security,
        "smtp_username": username,
        "smtp_password": password,
        "smtp_from": from_address,
        "smtp_to": to_addresses,
    }


class _PinnedSMTPMixin:
    def __init__(self, hostname, address, port, **kwargs):
        self._pinned_address = address
        # Keep the logical host for TLS certificate verification, connect only to the validated IP.
        super().__init__(hostname, port, **kwargs)

    def _get_socket(self, host, port, timeout):
        return super()._get_socket(self._pinned_address, port, timeout)


class PinnedSMTP(_PinnedSMTPMixin, smtplib.SMTP):
    pass


class PinnedSMTPSSL(_PinnedSMTPMixin, smtplib.SMTP_SSL):
    pass


def _send_email(config: dict, address: str, message: str, title: str) -> None:
    mail = EmailMessage()
    mail["Subject"] = title
    mail["From"] = config["smtp_from"]
    mail["To"] = ", ".join(config["smtp_to"])
    mail.set_content(message)
    context = ssl.create_default_context()
    server = None
    sending = False
    try:
        factory = PinnedSMTPSSL if config["smtp_security"] == "ssl" else PinnedSMTP
        options = {"timeout": 10}
        if config["smtp_security"] == "ssl":
            options["context"] = context
        server = factory(config["smtp_host"], address, config["smtp_port"], **options)
        if config["smtp_security"] == "starttls":
            server.starttls(context=context)
        server.login(config["smtp_username"], config["smtp_password"])
        sending = True
        refused = server.send_message(mail)
        if refused:
            raise NotificationSendError("部分收件人被拒收，其他收件人可能已收到，请确认后手动重试")
    except smtplib.SMTPRecipientsRefused as exc:
        temporary = bool(exc.recipients) and all(
            400 <= result[0] < 500 for result in exc.recipients.values()
        )
        raise NotificationSendError(
            "收件人暂时无法接收邮件，稍后自动重试"
            if temporary
            else "邮件收件人被拒收，请检查收件地址和发送权限",
            retryable=temporary,
        ) from None
    except smtplib.SMTPAuthenticationError:
        raise NotificationSendError("SMTP 登录失败，请检查用户名、密码或授权码") from None
    except smtplib.SMTPResponseException as exc:
        raise NotificationSendError(
            f"邮件服务器拒绝请求（SMTP {exc.smtp_code}）", retryable=400 <= exc.smtp_code < 500
        ) from None
    except (ssl.SSLError, smtplib.SMTPNotSupportedError):
        raise NotificationSendError("SMTP 加密连接失败，请检查 TLS 模式、端口和证书") from None
    except (OSError, smtplib.SMTPServerDisconnected):
        raise NotificationSendError(
            "邮件发送结果未知，请确认收件箱后再重试" if sending else "SMTP 连接失败，稍后自动重试",
            retryable=not sending,
        ) from None
    except smtplib.SMTPException:
        raise NotificationSendError("邮件服务器未接受消息，请检查 SMTP 配置") from None
    except UnicodeError:
        raise NotificationSendError(
            "SMTP 用户名或密码包含不支持的字符，请重新填写 ASCII 用户名和 SMTP 授权码"
        ) from None
    finally:
        if server is not None:
            server.close()


async def send_email_notification(config: dict, message: str, title: str) -> None:
    host = config["smtp_host"]
    authority = f"[{host}]" if ":" in host else host
    try:
        addresses = await resolve_outbound_http_url(f"https://{authority}:{config['smtp_port']}")
    except UnsafeOutboundURLError:
        raise NotificationSendError("SMTP 地址无法解析或不允许访问，请检查服务器地址") from None
    try:
        await asyncio.wait_for(
            asyncio.to_thread(_send_email, config, addresses[0], message, title), 25
        )
    except TimeoutError:
        raise NotificationSendError("邮件发送超时，结果未知，请确认收件箱后再重试") from None
