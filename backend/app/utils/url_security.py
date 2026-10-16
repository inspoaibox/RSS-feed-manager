"""Validation for server-side outbound HTTP requests."""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings


class UnsafeOutboundURLError(ValueError):
    """Raised when an outbound URL could reach a non-public network."""


def _address_is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return bool(ip.is_global)


async def resolve_outbound_http_url(url: str) -> list[str]:
    if any(ord(char) < 32 or char == "\\" for char in url):
        raise UnsafeOutboundURLError("Invalid URL characters")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeOutboundURLError("URL must be a valid http(s) address")
    if parsed.username or parsed.password:
        raise UnsafeOutboundURLError("Credentials are not allowed in target URLs")
    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeOutboundURLError("URL host could not be resolved") from exc

    resolved = {item[4][0] for item in addresses}
    if not resolved or (
        not settings.ALLOW_PRIVATE_FETCH_URLS
        and any(not _address_is_public(address) for address in resolved)
    ):
        raise UnsafeOutboundURLError(
            "Private, loopback, link-local, or reserved addresses are blocked"
        )
    # Containers commonly lack IPv6 routes even when DNS returns AAAA records.
    return sorted(resolved, key=lambda address: (ipaddress.ip_address(address).version, address))


async def validate_outbound_http_url(url: str) -> None:
    await resolve_outbound_http_url(url)


async def get_with_safe_redirects(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int = 5,
    **kwargs,
) -> httpx.Response:
    current_url = url
    for redirect_count in range(max_redirects + 1):
        addresses = await resolve_outbound_http_url(current_url)
        original_url = httpx.URL(current_url)
        pinned_url = original_url.copy_with(host=addresses[0])
        headers = httpx.Headers(kwargs.get("headers", {}))
        if original_url.host != httpx.URL(url).host:
            # Domainless custom-rule cookies must not follow a cross-host redirect.
            headers["Cookie"] = ""
            if "Authorization" in headers:
                del headers["Authorization"]
        headers["Host"] = original_url.netloc.decode("ascii")
        request_options = {
            **kwargs,
            "headers": headers,
            "extensions": {"sni_hostname": original_url.host},
        }
        response = await client.get(pinned_url, follow_redirects=False, **request_options)
        # Resolve redirect locations against the logical URL, never the pinned IP.
        response.request.url = original_url
        if not response.is_redirect:
            return response
        if redirect_count == max_redirects:
            raise UnsafeOutboundURLError("Too many redirects")
        location = response.headers.get("location")
        if not location:
            return response
        current_url = urljoin(str(response.url), location)
    raise UnsafeOutboundURLError("Too many redirects")
