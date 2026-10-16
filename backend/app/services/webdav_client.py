"""WebDAV helpers with validated connections and bounded downloads."""

import contextvars
import functools
import io
import re

from fastapi import HTTPException
from webdav3.client import Client

from app.core.config import settings
from app.utils.browser_proxy import SafeBrowserProxy

_proxy_url = contextvars.ContextVar("webdav_proxy_url", default=None)


def guarded_webdav(operation):
    @functools.wraps(operation)
    async def guarded(*args, **kwargs):
        async with SafeBrowserProxy() as proxy:
            token = _proxy_url.set(proxy.url)
            try:
                return await operation(*args, **kwargs)
            finally:
                _proxy_url.reset(token)

    return guarded


def get_webdav_client(config: dict) -> Client:
    client = Client(
        {
            "webdav_hostname": config["server_url"],
            "webdav_login": config["username"],
            "webdav_password": config["password"],
            "webdav_timeout": 30,
        }
    )
    client.session.trust_env = False
    proxy_url = _proxy_url.get()
    if not proxy_url:
        raise RuntimeError("WebDAV requests require the validated proxy")
    client.session.proxies = {"http": proxy_url, "https": proxy_url}
    return client


def validate_backup_filename(filename: str) -> None:
    if not re.fullmatch(r"rss_manager_backup_\d{8}_\d{6}\.json", filename):
        raise HTTPException(status_code=400, detail="无效的备份文件名")


class LimitedBackupBuffer(io.BytesIO):
    def write(self, data):
        if self.tell() + len(data) > settings.MAX_IMPORT_BYTES:
            raise HTTPException(status_code=413, detail="备份超过允许大小")
        return super().write(data)
