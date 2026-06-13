"""Google Translate API key pool and rotation service."""
from datetime import datetime, timedelta
from typing import Iterable, List

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.google_translate_key import GoogleTranslateKey
from app.models.user import User
from app.repositories.google_translate_key_repository import GoogleTranslateKeyRepository
from app.schemas.google_translate_key import (
    GoogleTranslateKeyCreate,
    GoogleTranslateKeyResponse,
    GoogleTranslateKeyTestResponse,
    GoogleTranslateKeyUpdate,
)
from app.services.google_translate_service import GoogleTranslateError, GoogleTranslateService


def _now() -> datetime:
    return datetime.utcnow()


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None)


def mask_google_api_key(api_key: str) -> str:
    """Return a short masked API key for UI display."""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}{'*' * 8}{api_key[-4:]}"


def is_google_key_exhausted(entry: GoogleTranslateKey, at: datetime | None = None) -> bool:
    """Return whether a key has reached any configured rotation limit."""
    current = at or _now()
    usage_started_at = _naive(entry.usage_started_at)
    if entry.limit_days and usage_started_at:
        if current - usage_started_at >= timedelta(days=entry.limit_days):
            return True
    if entry.limit_articles and entry.usage_article_count >= entry.limit_articles:
        return True
    if entry.limit_characters and entry.usage_character_count >= entry.limit_characters:
        return True
    return False


def _reset_usage(entry: GoogleTranslateKey) -> None:
    entry.usage_started_at = None
    entry.usage_article_count = 0
    entry.usage_character_count = 0
    entry.last_error = None


def _key_sequence(entries: Iterable[GoogleTranslateKey], at: datetime | None = None) -> list[GoogleTranslateKey]:
    """Build the ordered key sequence to try for one translation."""
    current = at or _now()
    active_entries = sorted(
        [entry for entry in entries if entry.is_active],
        key=lambda item: (item.position, item.id),
    )
    if not active_entries:
        return []

    latest_index = -1
    latest_used_at: datetime | None = None
    for index, entry in enumerate(active_entries):
        last_used_at = _naive(entry.last_used_at)
        if last_used_at and (latest_used_at is None or last_used_at > latest_used_at):
            latest_index = index
            latest_used_at = last_used_at

    exhausted = [is_google_key_exhausted(entry, current) for entry in active_entries]
    if all(exhausted):
        for entry in active_entries:
            _reset_usage(entry)
        exhausted = [False for _ in active_entries]
        start_index = (latest_index + 1) % len(active_entries) if latest_index >= 0 else 0
    elif latest_index >= 0 and not exhausted[latest_index]:
        start_index = latest_index
    else:
        start_index = (latest_index + 1) % len(active_entries) if latest_index >= 0 else 0

    sequence: list[GoogleTranslateKey] = []
    for offset in range(len(active_entries)):
        index = (start_index + offset) % len(active_entries)
        if not exhausted[index]:
            sequence.append(active_entries[index])
    return sequence


def _record_key_success(entry: GoogleTranslateKey, article_count: int, character_count: int) -> None:
    now = _now()
    if entry.usage_started_at is None:
        entry.usage_started_at = now
    entry.usage_article_count += article_count
    entry.usage_character_count += character_count
    entry.last_used_at = now
    entry.last_error = None
    entry.fail_count = 0
    entry.is_active = True


def _record_key_failure(entry: GoogleTranslateKey, error: str) -> None:
    entry.fail_count += 1
    if entry.fail_count >= 5:
        entry.is_active = False
    entry.last_error = error[:1000]
    entry.last_used_at = _now()


class GoogleTranslateKeyService:
    """Manage paid Google Translate keys and select them for translations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GoogleTranslateKeyRepository(session)

    async def list(self, user_id: int) -> List[GoogleTranslateKeyResponse]:
        entries = await self.repo.list(user_id)
        return [self._to_response(entry) for entry in entries]

    async def create(
        self,
        user_id: int,
        data: GoogleTranslateKeyCreate,
    ) -> GoogleTranslateKeyResponse:
        api_key = data.api_key.strip()
        if await self.repo.exists_by_api_key(user_id, api_key):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Google Translate API Key 已存在",
            )
        entry = await self.repo.create(
            user_id=user_id,
            name=data.name.strip(),
            api_key=api_key,
            is_active=data.is_active,
            limit_days=data.limit_days,
            limit_articles=data.limit_articles,
            limit_characters=data.limit_characters,
        )
        return self._to_response(entry)

    async def update(
        self,
        user_id: int,
        key_id: int,
        data: GoogleTranslateKeyUpdate,
    ) -> GoogleTranslateKeyResponse:
        entry = await self.repo.get_by_id(user_id, key_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key 不存在")

        update_data = data.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"]:
            update_data["name"] = update_data["name"].strip()
        if "api_key" in update_data and update_data["api_key"]:
            update_data["api_key"] = update_data["api_key"].strip()
            if await self.repo.exists_by_api_key(user_id, update_data["api_key"], exclude_id=key_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Google Translate API Key 已存在",
                )
        entry = await self.repo.update(entry, **update_data)
        await self.session.refresh(entry)
        return self._to_response(entry)

    async def delete(self, user_id: int, key_id: int) -> None:
        entry = await self.repo.get_by_id(user_id, key_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key 不存在")
        await self.repo.delete(entry)

    async def reset_usage(self, user_id: int, key_id: int) -> GoogleTranslateKeyResponse:
        entry = await self.repo.get_by_id(user_id, key_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key 不存在")
        _reset_usage(entry)
        entry.fail_count = 0
        entry.last_used_at = None
        entry.is_active = True
        await self.session.flush()
        await self.session.refresh(entry)
        return self._to_response(entry)

    async def test(self, user_id: int, key_id: int) -> GoogleTranslateKeyTestResponse:
        entry = await self.repo.get_by_id(user_id, key_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key 不存在")
        service = GoogleTranslateService(api_key=entry.api_key)
        try:
            success = await service.test_connection()
        except Exception as exc:
            success = False
            _record_key_failure(entry, str(exc))
            await self.session.flush()
            return GoogleTranslateKeyTestResponse(success=False, message=str(exc))

        if success:
            entry.fail_count = 0
            entry.last_error = None
            await self.session.flush()
            return GoogleTranslateKeyTestResponse(success=True, message="连接成功")

        _record_key_failure(entry, "测试失败")
        await self.session.flush()
        return GoogleTranslateKeyTestResponse(success=False, message="测试失败")

    async def translate_article(
        self,
        user_id: int,
        title: str,
        content: str,
        target_language: str,
    ) -> tuple[str, str]:
        """Translate title/content using the selected paid key or free endpoint."""
        entries = await self.repo.list(user_id, active_only=True)
        sequence = _key_sequence(entries)
        character_count = len(title or "") + len(content or "")
        last_error: Exception | None = None

        if not sequence:
            legacy_key = await self._get_legacy_api_key(user_id)
            return await self._translate_with_key(legacy_key, title, content, target_language)

        for entry in sequence:
            try:
                translated_title, translated_content = await self._translate_with_key(
                    entry.api_key,
                    title,
                    content,
                    target_language,
                )
                _record_key_success(entry, 1, character_count)
                await self.session.flush()
                return translated_title, translated_content
            except GoogleTranslateError as exc:
                last_error = exc
                _record_key_failure(entry, str(exc))
                await self.session.flush()

        if last_error:
            raise last_error
        raise GoogleTranslateError("没有可用的 Google Translate API Key")

    async def _translate_with_key(
        self,
        api_key: str | None,
        title: str,
        content: str,
        target_language: str,
    ) -> tuple[str, str]:
        service = GoogleTranslateService(api_key=api_key)
        translated_title = await service.translate(title, target_language) if title else ""
        translated_content = await service.translate(content, target_language) if content else ""
        return translated_title, translated_content

    async def _get_legacy_api_key(self, user_id: int) -> str | None:
        result = await self.session.execute(select(User.google_translate_api_key).where(User.id == user_id))
        return result.scalar_one_or_none()

    def _to_response(self, entry: GoogleTranslateKey) -> GoogleTranslateKeyResponse:
        return GoogleTranslateKeyResponse(
            id=entry.id,
            name=entry.name,
            masked_api_key=mask_google_api_key(entry.api_key),
            is_active=entry.is_active,
            position=entry.position,
            limit_days=entry.limit_days,
            limit_articles=entry.limit_articles,
            limit_characters=entry.limit_characters,
            usage_started_at=entry.usage_started_at,
            usage_article_count=entry.usage_article_count,
            usage_character_count=entry.usage_character_count,
            last_used_at=entry.last_used_at,
            last_error=entry.last_error,
            fail_count=entry.fail_count,
            is_exhausted=is_google_key_exhausted(entry),
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )


def translate_google_article_sync(
    db: Session,
    user_id: int,
    title: str,
    content: str,
    target_language: str,
    loop,
) -> tuple[str, str]:
    """Sync-session helper for Celery tasks."""
    entries = list(
        db.execute(
            select(GoogleTranslateKey)
            .where(
                GoogleTranslateKey.user_id == user_id,
                GoogleTranslateKey.is_active == True,
            )
            .order_by(GoogleTranslateKey.position, GoogleTranslateKey.id)
        ).scalars().all()
    )
    sequence = _key_sequence(entries)
    character_count = len(title or "") + len(content or "")
    last_error: Exception | None = None

    if not sequence:
        legacy_key = db.execute(
            select(User.google_translate_api_key).where(User.id == user_id)
        ).scalar_one_or_none()
        return _translate_with_key_sync(legacy_key, title, content, target_language, loop)

    for entry in sequence:
        try:
            translated_title, translated_content = _translate_with_key_sync(
                entry.api_key,
                title,
                content,
                target_language,
                loop,
            )
            _record_key_success(entry, 1, character_count)
            db.flush()
            return translated_title, translated_content
        except GoogleTranslateError as exc:
            last_error = exc
            _record_key_failure(entry, str(exc))
            db.flush()

    if last_error:
        raise last_error
    raise GoogleTranslateError("没有可用的 Google Translate API Key")


def _translate_with_key_sync(
    api_key: str | None,
    title: str,
    content: str,
    target_language: str,
    loop,
) -> tuple[str, str]:
    service = GoogleTranslateService(api_key=api_key)
    translated_title = (
        loop.run_until_complete(service.translate(title, target_language))
        if title
        else ""
    )
    translated_content = (
        loop.run_until_complete(service.translate(content, target_language))
        if content
        else ""
    )
    return translated_title, translated_content
