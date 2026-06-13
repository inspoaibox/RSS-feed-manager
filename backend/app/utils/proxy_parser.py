"""Proxy parsing utilities."""
import re
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlparse


SUPPORTED_PROXY_PROTOCOLS = {"http", "https", "socks4", "socks5", "socks5h"}


class ProxyParseError(ValueError):
    """Raised when a proxy line cannot be parsed."""


@dataclass(frozen=True)
class ParsedProxy:
    """Parsed proxy endpoint."""

    protocol: str
    host: str
    port: int
    username: str | None
    password: str | None
    country: str | None
    source_format: str
    proxy_url: str


def _normalize_protocol(protocol: str | None) -> str:
    normalized = (protocol or "http").strip().lower()
    if normalized not in SUPPORTED_PROXY_PROTOCOLS:
        raise ProxyParseError(f"不支持的代理协议: {protocol}")
    return normalized


def _normalize_country(country: str | None) -> str | None:
    if not country:
        return None
    normalized = country.strip().lower()
    return normalized or None


def _extract_country(*values: str | None) -> str | None:
    text = " ".join(value or "" for value in values)
    patterns = [
        r"(?:^|[-_:])country[-_=]?([a-zA-Z]{2,6})(?:$|[-_:])",
        r"(?:^|[-_:])cc[-_=]?([a-zA-Z]{2,6})(?:$|[-_:])",
        r"(?:^|[-_:])region[-_=]?([a-zA-Z]{2,6})(?:$|[-_:])",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


def _build_proxy_url(
    protocol: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
) -> str:
    auth = ""
    if username:
        auth = quote(username, safe="")
        if password is not None:
            auth += f":{quote(password, safe='')}"
        auth += "@"
    return f"{protocol}://{auth}{host}:{port}"


def _parse_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise ProxyParseError(f"端口无效: {value}") from exc
    if port < 1 or port > 65535:
        raise ProxyParseError(f"端口超出范围: {value}")
    return port


def _from_url(
    raw: str,
    default_protocol: str,
    default_country: str | None,
    source_format: str,
) -> ParsedProxy:
    value = raw if "://" in raw else f"{default_protocol}://{raw}"
    parsed = urlparse(value)
    protocol = _normalize_protocol(parsed.scheme)
    host = parsed.hostname
    if not host or parsed.port is None:
        raise ProxyParseError("缺少代理主机或端口")

    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None
    country = _normalize_country(default_country) or _extract_country(username, password, raw)
    proxy_url = _build_proxy_url(protocol, host, parsed.port, username, password)
    return ParsedProxy(
        protocol=protocol,
        host=host,
        port=parsed.port,
        username=username,
        password=password,
        country=country,
        source_format=source_format,
        proxy_url=proxy_url,
    )


def _from_parts(
    protocol: str,
    host: str,
    port: str,
    username: str | None,
    password: str | None,
    country: str | None,
    source_format: str,
    raw: str,
) -> ParsedProxy:
    normalized_protocol = _normalize_protocol(protocol)
    normalized_host = host.strip()
    if not normalized_host:
        raise ProxyParseError("缺少代理主机")
    parsed_port = _parse_port(port.strip())
    normalized_username = username.strip() if username else None
    normalized_password = password.strip() if password is not None else None
    normalized_country = _normalize_country(country) or _extract_country(
        normalized_username,
        normalized_password,
        raw,
    )
    return ParsedProxy(
        protocol=normalized_protocol,
        host=normalized_host,
        port=parsed_port,
        username=normalized_username,
        password=normalized_password,
        country=normalized_country,
        source_format=source_format,
        proxy_url=_build_proxy_url(
            normalized_protocol,
            normalized_host,
            parsed_port,
            normalized_username,
            normalized_password,
        ),
    )


def parse_proxy_line(
    raw: str,
    default_protocol: str = "http",
    default_country: str | None = None,
) -> ParsedProxy:
    """Parse one proxy line into a canonical proxy URL."""
    line = raw.strip()
    if not line:
        raise ProxyParseError("空代理行")

    protocol = _normalize_protocol(default_protocol)

    if "," in line:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            raise ProxyParseError("CSV 代理格式无效")
        if len(parts) >= 4 and parts[1].isdigit():
            return _from_parts(
                protocol,
                parts[0],
                parts[1],
                parts[2],
                parts[3],
                default_country,
                "csv_host_port_user_pass",
                line,
            )
        if len(parts) >= 4 and parts[3].isdigit():
            return _from_parts(
                protocol,
                parts[2],
                parts[3],
                parts[0],
                parts[1],
                default_country,
                "csv_user_pass_host_port",
                line,
            )
        if len(parts) >= 2 and parts[1].isdigit():
            return _from_parts(
                protocol,
                parts[0],
                parts[1],
                None,
                None,
                default_country,
                "csv_host_port",
                line,
            )
        raise ProxyParseError("CSV 代理格式无效")

    if "://" in line:
        return _from_url(line, protocol, default_country, "url")

    if "@" in line:
        return _from_url(line, protocol, default_country, "auth_host_port")

    parts = line.split(":")
    if len(parts) == 2:
        return _from_parts(
            protocol,
            parts[0],
            parts[1],
            None,
            None,
            default_country,
            "host_port",
            line,
        )

    if len(parts) >= 4 and parts[1].isdigit():
        return _from_parts(
            protocol,
            parts[0],
            parts[1],
            parts[2],
            ":".join(parts[3:]),
            default_country,
            "host_port_user_pass",
            line,
        )

    raise ProxyParseError("无法识别代理格式")


def iter_proxy_lines(content: str) -> list[str]:
    """Split pasted proxy text into meaningful lines."""
    return [
        line.strip()
        for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]
