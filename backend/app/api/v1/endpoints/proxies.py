"""Proxy pool API endpoints."""
from typing import List

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserId, DbSession
from app.schemas.proxy_pool import (
    ProxyPoolEntryCreate,
    ProxyPoolEntryResponse,
    ProxyPoolEntryUpdate,
    ProxyPoolGroupsResponse,
    ProxyPoolImportRequest,
    ProxyPoolImportResult,
    ProxyPoolTestRequest,
    ProxyPoolTestResult,
)
from app.services.proxy_pool_service import ProxyPoolService

router = APIRouter()


@router.get("", response_model=List[ProxyPoolEntryResponse])
async def list_proxies(
    user_id: CurrentUserId,
    db: DbSession,
    country: str | None = Query(None),
    protocol: str | None = Query(None),
    active: bool | None = Query(None),
):
    """List proxy pool entries."""
    return await ProxyPoolService(db).list(user_id, country, protocol, active)


@router.get("/groups", response_model=ProxyPoolGroupsResponse)
async def get_proxy_groups(user_id: CurrentUserId, db: DbSession):
    """Get available proxy country and protocol groups."""
    return await ProxyPoolService(db).groups(user_id)


@router.post("", response_model=ProxyPoolEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_proxy(data: ProxyPoolEntryCreate, user_id: CurrentUserId, db: DbSession):
    """Create one proxy pool entry."""
    return await ProxyPoolService(db).create(user_id, data)


@router.post("/import", response_model=ProxyPoolImportResult)
async def import_proxies(data: ProxyPoolImportRequest, user_id: CurrentUserId, db: DbSession):
    """Import proxy pool entries from pasted text."""
    return await ProxyPoolService(db).import_many(user_id, data)


@router.post("/test", response_model=ProxyPoolTestResult)
async def test_proxies(data: ProxyPoolTestRequest, user_id: CurrentUserId, db: DbSession):
    """Batch test proxies and update latency/failure state."""
    return await ProxyPoolService(db).test(user_id, data)


@router.put("/{proxy_id}", response_model=ProxyPoolEntryResponse)
async def update_proxy(
    proxy_id: int,
    data: ProxyPoolEntryUpdate,
    user_id: CurrentUserId,
    db: DbSession,
):
    """Update one proxy pool entry."""
    return await ProxyPoolService(db).update(user_id, proxy_id, data)


@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy(proxy_id: int, user_id: CurrentUserId, db: DbSession):
    """Delete one proxy pool entry."""
    await ProxyPoolService(db).delete(user_id, proxy_id)
