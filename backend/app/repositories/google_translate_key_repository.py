"""Google Translate key repository."""
from typing import Iterable, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.google_translate_key import GoogleTranslateKey


class GoogleTranslateKeyRepository:
    """Repository for Google Translate API keys."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        name: str,
        api_key: str,
        is_active: bool = True,
        limit_days: int | None = None,
        limit_articles: int | None = None,
        limit_characters: int | None = None,
    ) -> GoogleTranslateKey:
        position = await self.next_position(user_id)
        entry = GoogleTranslateKey(
            user_id=user_id,
            name=name,
            api_key=api_key,
            is_active=is_active,
            position=position,
            limit_days=limit_days,
            limit_articles=limit_articles,
            limit_characters=limit_characters,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def next_position(self, user_id: int) -> int:
        result = await self.session.execute(
            select(GoogleTranslateKey.position)
            .where(GoogleTranslateKey.user_id == user_id)
            .order_by(GoogleTranslateKey.position.desc())
            .limit(1)
        )
        current = result.scalar_one_or_none()
        return 0 if current is None else current + 1

    async def get_by_id(self, user_id: int, key_id: int) -> GoogleTranslateKey | None:
        result = await self.session.execute(
            select(GoogleTranslateKey).where(
                GoogleTranslateKey.id == key_id,
                GoogleTranslateKey.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, user_id: int, active_only: bool = False) -> List[GoogleTranslateKey]:
        query = select(GoogleTranslateKey).where(GoogleTranslateKey.user_id == user_id)
        if active_only:
            query = query.where(GoogleTranslateKey.is_active == True)
        query = query.order_by(GoogleTranslateKey.position, GoogleTranslateKey.id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def exists_by_api_key(
        self,
        user_id: int,
        api_key: str,
        exclude_id: int | None = None,
    ) -> bool:
        query = select(GoogleTranslateKey.id).where(
            GoogleTranslateKey.user_id == user_id,
            GoogleTranslateKey.api_key == api_key,
        )
        if exclude_id is not None:
            query = query.where(GoogleTranslateKey.id != exclude_id)
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def update(self, entry: GoogleTranslateKey, **kwargs) -> GoogleTranslateKey:
        nullable_fields = {"limit_days", "limit_articles", "limit_characters", "last_error"}
        for key, value in kwargs.items():
            if hasattr(entry, key) and (value is not None or key in nullable_fields):
                setattr(entry, key, value)
        await self.session.flush()
        return entry

    async def delete(self, entry: GoogleTranslateKey) -> None:
        await self.session.delete(entry)
        await self.session.flush()

    async def get_many_by_ids(
        self,
        user_id: int,
        key_ids: Iterable[int],
    ) -> List[GoogleTranslateKey]:
        ids = list(key_ids)
        if not ids:
            return []
        result = await self.session.execute(
            select(GoogleTranslateKey)
            .where(GoogleTranslateKey.user_id == user_id, GoogleTranslateKey.id.in_(ids))
            .order_by(GoogleTranslateKey.position, GoogleTranslateKey.id)
        )
        return list(result.scalars().all())
