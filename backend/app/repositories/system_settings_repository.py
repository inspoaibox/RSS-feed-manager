"""System settings repository for database operations."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_settings import SystemSettings


class SystemSettingsRepository:
    """Repository for SystemSettings database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> str | None:
        """Get a setting value by key."""
        result = await self.session.execute(
            select(SystemSettings).where(SystemSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

    async def set(self, key: str, value: str, description: str | None = None) -> SystemSettings:
        """Set a setting value."""
        result = await self.session.execute(
            select(SystemSettings).where(SystemSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = value
            if description:
                setting.description = description
        else:
            setting = SystemSettings(key=key, value=value, description=description)
            self.session.add(setting)
        
        await self.session.flush()
        return setting

    async def get_all(self) -> list[SystemSettings]:
        """Get all settings."""
        result = await self.session.execute(select(SystemSettings))
        return list(result.scalars().all())

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean setting value."""
        value = await self.get(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')
