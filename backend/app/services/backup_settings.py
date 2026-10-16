"""Backup data operations."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_settings import SystemSettings

WEBDAV_CONFIG_KEY = "webdav_config"


async def get_webdav_config_from_db(db: AsyncSession, user_id: int) -> dict | None:
    """Get WebDAV config from database."""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == f"{WEBDAV_CONFIG_KEY}_{user_id}")
    )
    setting = result.scalar_one_or_none()
    if setting:
        return json.loads(setting.value)
    return None


async def save_webdav_config_to_db(db: AsyncSession, user_id: int, config: dict):
    """Save WebDAV config to database."""
    key = f"{WEBDAV_CONFIG_KEY}_{user_id}"
    result = await db.execute(select(SystemSettings).where(SystemSettings.key == key))
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = json.dumps(config)
    else:
        setting = SystemSettings(key=key, value=json.dumps(config))
        db.add(setting)

    await db.commit()
