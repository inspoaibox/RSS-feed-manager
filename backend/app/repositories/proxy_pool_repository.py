"""Proxy pool repository."""
from datetime import datetime
from typing import Iterable, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proxy_pool import ProxyPoolEntry
from app.utils.proxy_parser import ParsedProxy


class ProxyPoolRepository:
    """Repository for proxy pool entries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        parsed: ParsedProxy,
        is_active: bool = True,
    ) -> ProxyPoolEntry:
        entry = ProxyPoolEntry(
            user_id=user_id,
            protocol=parsed.protocol,
            host=parsed.host,
            port=parsed.port,
            username=parsed.username,
            password=parsed.password,
            country=parsed.country,
            source_format=parsed.source_format,
            proxy_url=parsed.proxy_url,
            is_active=is_active,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def exists_by_url(self, user_id: int, proxy_url: str) -> bool:
        result = await self.session.execute(
            select(ProxyPoolEntry.id)
            .where(ProxyPoolEntry.user_id == user_id, ProxyPoolEntry.proxy_url == proxy_url)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_by_id(self, user_id: int, proxy_id: int) -> ProxyPoolEntry | None:
        result = await self.session.execute(
            select(ProxyPoolEntry).where(
                ProxyPoolEntry.id == proxy_id,
                ProxyPoolEntry.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_many_by_ids(
        self,
        user_id: int,
        proxy_ids: Iterable[int],
    ) -> List[ProxyPoolEntry]:
        ids = list(proxy_ids)
        if not ids:
            return []
        result = await self.session.execute(
            select(ProxyPoolEntry)
            .where(ProxyPoolEntry.user_id == user_id, ProxyPoolEntry.id.in_(ids))
            .order_by(ProxyPoolEntry.id)
        )
        return list(result.scalars().all())

    async def list(
        self,
        user_id: int,
        country: str | None = None,
        protocol: str | None = None,
        active: bool | None = None,
    ) -> List[ProxyPoolEntry]:
        query = select(ProxyPoolEntry).where(ProxyPoolEntry.user_id == user_id)
        if country:
            query = query.where(ProxyPoolEntry.country == country.lower())
        if protocol:
            query = query.where(ProxyPoolEntry.protocol == protocol.lower())
        if active is not None:
            query = query.where(ProxyPoolEntry.is_active == active)
        query = query.order_by(
            ProxyPoolEntry.is_active.desc(),
            ProxyPoolEntry.country,
            ProxyPoolEntry.protocol,
            ProxyPoolEntry.fail_count,
            ProxyPoolEntry.id,
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_candidates(
        self,
        user_id: int,
        country: str | None = None,
        protocol: str | None = None,
    ) -> List[ProxyPoolEntry]:
        query = select(ProxyPoolEntry).where(
            ProxyPoolEntry.user_id == user_id,
            ProxyPoolEntry.is_active == True,
        )
        if country:
            query = query.where(ProxyPoolEntry.country == country.lower())
        if protocol:
            query = query.where(ProxyPoolEntry.protocol == protocol.lower())
        query = query.order_by(
            ProxyPoolEntry.fail_count,
            ProxyPoolEntry.last_used_at.is_not(None),
            ProxyPoolEntry.last_used_at,
            ProxyPoolEntry.last_latency_ms.is_(None),
            ProxyPoolEntry.last_latency_ms,
            ProxyPoolEntry.id,
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, entry: ProxyPoolEntry, **kwargs) -> ProxyPoolEntry:
        nullable_fields = {"country", "last_latency_ms", "last_error", "last_used_at"}
        for key, value in kwargs.items():
            if hasattr(entry, key) and (value is not None or key in nullable_fields):
                setattr(entry, key, value)
        await self.session.flush()
        return entry

    async def record_success(self, entry: ProxyPoolEntry, latency_ms: int | None = None) -> None:
        entry.fail_count = 0
        entry.is_active = True
        entry.last_latency_ms = latency_ms
        entry.last_error = None
        entry.last_used_at = datetime.utcnow()
        entry.last_tested_at = datetime.utcnow()
        await self.session.flush()

    async def record_failure(self, entry: ProxyPoolEntry, error: str) -> None:
        entry.fail_count += 1
        if entry.fail_count >= 5:
            entry.is_active = False
        entry.last_error = error[:1000]
        entry.last_used_at = datetime.utcnow()
        entry.last_tested_at = datetime.utcnow()
        await self.session.flush()

    async def delete(self, entry: ProxyPoolEntry) -> None:
        await self.session.delete(entry)
        await self.session.flush()

    async def groups(self, user_id: int) -> tuple[list[str], list[str]]:
        country_result = await self.session.execute(
            select(ProxyPoolEntry.country)
            .where(ProxyPoolEntry.user_id == user_id, ProxyPoolEntry.country != None)
            .group_by(ProxyPoolEntry.country)
            .order_by(ProxyPoolEntry.country)
        )
        protocol_result = await self.session.execute(
            select(ProxyPoolEntry.protocol)
            .where(ProxyPoolEntry.user_id == user_id)
            .group_by(ProxyPoolEntry.protocol)
            .order_by(ProxyPoolEntry.protocol)
        )
        return (
            [row[0] for row in country_result.all() if row[0]],
            [row[0] for row in protocol_result.all() if row[0]],
        )

    async def count_active(
        self,
        user_id: int,
        country: str | None = None,
        protocol: str | None = None,
    ) -> int:
        query = select(func.count(ProxyPoolEntry.id)).where(
            ProxyPoolEntry.user_id == user_id,
            ProxyPoolEntry.is_active == True,
        )
        if country:
            query = query.where(ProxyPoolEntry.country == country.lower())
        if protocol:
            query = query.where(ProxyPoolEntry.protocol == protocol.lower())
        result = await self.session.execute(query)
        return result.scalar() or 0
