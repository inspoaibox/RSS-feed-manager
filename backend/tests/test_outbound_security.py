"""Private targets, unsafe redirects, DNS pinning, and encrypted backups."""

import asyncio
import io
import socket
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.services.backup_crypto import decrypt_backup, encrypt_backup
from app.utils import url_security
from app.utils.browser_proxy import SafeBrowserProxy
from app.utils.uploads import read_upload_limited


def resolved(address):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]


@pytest.mark.asyncio
@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "0.0.0.0", "192.168.1.1"])
async def test_private_targets_are_rejected(monkeypatch, address):
    monkeypatch.setattr(url_security.socket, "getaddrinfo", lambda *_args, **_kwargs: resolved(address))
    with pytest.raises(url_security.UnsafeOutboundURLError):
        await url_security.validate_outbound_http_url("https://target.example/rss")


@pytest.mark.asyncio
async def test_redirect_revalidates_dns_and_pins_address(monkeypatch):
    monkeypatch.setattr(url_security.socket, "getaddrinfo", lambda host, *_a, **_kw: resolved("127.0.0.1" if host == "private.example" else "93.184.216.34"))
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://private.example/data"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(url_security.UnsafeOutboundURLError):
            await url_security.get_with_safe_redirects(client, "https://public.example/feed")
    assert len(requests) == 1
    assert requests[0].extensions["sni_hostname"] == "public.example"
    assert requests[0].headers["host"] == "public.example"


@pytest.mark.asyncio
async def test_browser_proxy_refuses_loopback():
    async with SafeBrowserProxy() as proxy:
        port = int(proxy.url.rsplit(":", 1)[1])
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"CONNECT 127.0.0.1:8000 HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await writer.drain()
        assert b"403" in await asyncio.wait_for(reader.read(1024), 3)
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
async def test_upload_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_IMPORT_BYTES", 3)
    with pytest.raises(HTTPException) as exc:
        await read_upload_limited(UploadFile(file=io.BytesIO(b"1234")))
    assert exc.value.status_code == 413


def test_encrypted_backup_roundtrip_and_authentication():
    data = {"feeds": [], "user_settings": {"api_key": "secret-that-must-not-leak"}}
    encrypted = encrypt_backup(data, "strong-backup-password")
    assert b"secret-that-must-not-leak" not in encrypted
    assert decrypt_backup(encrypted, "strong-backup-password") == data
    with pytest.raises(ValueError):
        decrypt_backup(encrypted, "wrong-backup-password")
    with pytest.raises(ValueError):
        decrypt_backup(encrypted.replace(b'"nonce":', b'"wrong":'), "strong-backup-password")
    assert decrypt_backup(b'{"feeds": []}') == {"feeds": []}
