"""Proxy pool service."""
import time
from typing import List

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proxy_pool import ProxyPoolEntry
from app.repositories.proxy_pool_repository import ProxyPoolRepository
from app.schemas.proxy_pool import (
    ProxyPoolEntryCreate,
    ProxyPoolEntryResponse,
    ProxyPoolEntryUpdate,
    ProxyPoolGroupsResponse,
    ProxyPoolImportRequest,
    ProxyPoolImportResult,
    ProxyPoolTestItem,
    ProxyPoolTestRequest,
    ProxyPoolTestResult,
)
from app.utils.proxy_parser import ProxyParseError, iter_proxy_lines, parse_proxy_line


class ProxyPoolService:
    """Service for proxy pool operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProxyPoolRepository(session)

    async def list(
        self,
        user_id: int,
        country: str | None = None,
        protocol: str | None = None,
        active: bool | None = None,
    ) -> List[ProxyPoolEntryResponse]:
        entries = await self.repo.list(
            user_id,
            country=country,
            protocol=protocol,
            active=active,
        )
        return [self._to_response(entry) for entry in entries]

    async def groups(self, user_id: int) -> ProxyPoolGroupsResponse:
        countries, protocols = await self.repo.groups(user_id)
        return ProxyPoolGroupsResponse(countries=countries, protocols=protocols)

    async def create(
        self,
        user_id: int,
        data: ProxyPoolEntryCreate,
    ) -> ProxyPoolEntryResponse:
        try:
            parsed = parse_proxy_line(
                data.raw,
                default_protocol=data.default_protocol,
                default_country=data.country,
            )
        except ProxyParseError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        if await self.repo.exists_by_url(user_id, parsed.proxy_url):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="代理已存在",
            )

        entry = await self.repo.create(user_id, parsed, is_active=data.is_active)
        return self._to_response(entry)

    async def import_many(
        self,
        user_id: int,
        data: ProxyPoolImportRequest,
    ) -> ProxyPoolImportResult:
        imported: list[ProxyPoolEntry] = []
        skipped = 0
        errors: list[str] = []

        for line in iter_proxy_lines(data.content):
            try:
                parsed = parse_proxy_line(
                    line,
                    default_protocol=data.default_protocol,
                    default_country=data.default_country,
                )
                if await self.repo.exists_by_url(user_id, parsed.proxy_url):
                    skipped += 1
                    continue
                imported.append(await self.repo.create(user_id, parsed, data.is_active))
            except ProxyParseError as exc:
                errors.append(f"{line}: {exc}")
            except Exception as exc:
                errors.append(f"{line}: {exc}")

        return ProxyPoolImportResult(
            imported=len(imported),
            skipped=skipped,
            errors=errors,
            items=[self._to_response(entry) for entry in imported],
        )

    async def update(
        self,
        user_id: int,
        proxy_id: int,
        data: ProxyPoolEntryUpdate,
    ) -> ProxyPoolEntryResponse:
        entry = await self.repo.get_by_id(user_id, proxy_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="代理不存在")

        update_data = data.model_dump(exclude_unset=True)
        raw = update_data.pop("raw", None)
        default_protocol = update_data.pop("default_protocol", None) or entry.protocol
        has_country = "country" in update_data
        country = update_data.pop("country", None) if has_country else entry.country
        normalized_country = country.strip().lower() if country else None

        if raw is not None:
            try:
                parsed = parse_proxy_line(
                    raw,
                    default_protocol=default_protocol,
                    default_country=normalized_country,
                )
            except ProxyParseError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc

            if parsed.proxy_url != entry.proxy_url and await self.repo.exists_by_url(
                user_id,
                parsed.proxy_url,
                exclude_id=proxy_id,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="代理已存在",
                )

            update_data.update(
                protocol=parsed.protocol,
                host=parsed.host,
                port=parsed.port,
                username=parsed.username,
                password=parsed.password,
                country=normalized_country if has_country else parsed.country,
                source_format=parsed.source_format,
                proxy_url=parsed.proxy_url,
            )
        elif has_country:
            update_data["country"] = normalized_country

        entry = await self.repo.update(entry, **update_data)
        await self.session.refresh(entry)
        return self._to_response(entry)

    async def delete(self, user_id: int, proxy_id: int) -> None:
        entry = await self.repo.get_by_id(user_id, proxy_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="代理不存在")
        await self.repo.delete(entry)

    async def test(
        self,
        user_id: int,
        data: ProxyPoolTestRequest,
    ) -> ProxyPoolTestResult:
        if data.ids:
            entries = await self.repo.get_many_by_ids(user_id, data.ids)
        else:
            entries = await self.repo.list(
                user_id,
                country=data.country,
                protocol=data.protocol,
                active=True if data.active_only else None,
            )

        results: list[ProxyPoolTestItem] = []
        for entry in entries:
            success, latency_ms, error = await self._test_entry(entry, data.test_url, data.timeout)
            if success:
                await self.repo.record_success(entry, latency_ms)
            else:
                await self.repo.record_failure(entry, error or "代理测试失败")
            results.append(
                ProxyPoolTestItem(
                    id=entry.id,
                    success=success,
                    latency_ms=latency_ms,
                    error=error,
                    is_active=entry.is_active,
                    fail_count=entry.fail_count,
                )
            )

        success_count = sum(1 for item in results if item.success)
        return ProxyPoolTestResult(
            total=len(results),
            success=success_count,
            failed=len(results) - success_count,
            results=results,
        )

    async def _test_entry(
        self,
        entry: ProxyPoolEntry,
        test_url: str,
        timeout: float,
    ) -> tuple[bool, int | None, str | None]:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                proxy=entry.proxy_url,
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(test_url)
                response.raise_for_status()
            latency_ms = int((time.perf_counter() - started) * 1000)
            return True, latency_ms, None
        except Exception as exc:
            return False, None, str(exc)

    def _to_response(self, entry: ProxyPoolEntry) -> ProxyPoolEntryResponse:
        return ProxyPoolEntryResponse(
            id=entry.id,
            protocol=entry.protocol,
            host=entry.host,
            port=entry.port,
            username=entry.username,
            password=entry.password,
            country=entry.country,
            source_format=entry.source_format,
            proxy_url=entry.proxy_url,
            is_active=entry.is_active,
            fail_count=entry.fail_count,
            last_used_at=entry.last_used_at,
            last_tested_at=entry.last_tested_at,
            last_latency_ms=entry.last_latency_ms,
            last_error=entry.last_error,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )
