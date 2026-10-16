"""A local forward proxy that pins browser connections to validated public IPs.

CONNECT tunnels preserve TLS certificate verification and browser cookies. The
upstream proxy, when configured, receives a validated IP rather than a hostname.
"""

import asyncio
import contextlib
import functools
import inspect
from urllib.parse import urlparse

from app.utils.url_security import resolve_outbound_http_url


def safe_browser_fetch(operation):
    @functools.wraps(operation)
    async def guarded(*args, **kwargs):
        bound = inspect.signature(operation).bind(*args, **kwargs)
        async with SafeBrowserProxy(bound.arguments.get("proxy_url")) as proxy:
            bound.arguments["proxy_url"] = proxy.url
            return await operation(*bound.args, **bound.kwargs)

    return guarded


class SafeBrowserProxy:
    def __init__(self, upstream: str | None = None):
        self.upstream = upstream
        self.server = None
        self.connections: set[asyncio.Task] = set()

    async def __aenter__(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0, limit=65536)
        port = self.server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        return self

    async def __aexit__(self, *_):
        self.server.close()
        await self.server.wait_closed()
        pending = list(self.connections)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    async def _handle(self, reader, writer):
        task = asyncio.current_task()
        self.connections.add(task)
        remote_writer = None
        relay_tasks = []
        try:
            raw_headers = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 15)
            lines = raw_headers.decode("latin-1").split("\r\n")
            method, target, version = lines[0].split(" ", 2)
            tunnel = method == "CONNECT"
            url = f"https://{target}" if tunnel else target
            parsed = urlparse(url)
            addresses = await resolve_outbound_http_url(url)
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if self.upstream:
                from python_socks.async_.asyncio import Proxy

                sock = await Proxy.from_url(self.upstream).connect(
                    dest_host=addresses[0],
                    dest_port=port,
                    timeout=30,
                )
                remote_reader, remote_writer = await asyncio.open_connection(sock=sock)
            else:
                remote_reader, remote_writer = await asyncio.wait_for(
                    asyncio.open_connection(addresses[0], port),
                    30,
                )
            if tunnel:
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
            else:
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                headers = [
                    line
                    for line in lines[1:]
                    if line
                    and not line.lower().startswith(
                        ("proxy-authorization:", "proxy-connection:", "connection:"),
                    )
                ]
                # Close after this request; prevent a later request from reusing
                # this socket for a different destination without validation.
                headers.append("Connection: close")
                remote_writer.write(
                    (f"{method} {path} {version}\r\n" + "\r\n".join(headers) + "\r\n\r\n").encode(
                        "latin-1"
                    )
                )
                await remote_writer.drain()
            relay_tasks = [
                asyncio.create_task(self._relay(reader, remote_writer)),
                asyncio.create_task(self._relay(remote_reader, writer)),
            ]
            await asyncio.wait(relay_tasks, return_when=asyncio.FIRST_COMPLETED)
        except (
            TimeoutError,
            ValueError,
            OSError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
        ):
            with contextlib.suppress(OSError):
                writer.write(
                    b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
                )
                await writer.drain()
        finally:
            for relay in relay_tasks:
                relay.cancel()
            await asyncio.gather(*relay_tasks, return_exceptions=True)
            if remote_writer:
                remote_writer.close()
            writer.close()
            self.connections.discard(task)

    @staticmethod
    async def _relay(reader, writer):
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
