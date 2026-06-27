"""Tests for proxy pool behavior."""

import pytest

from app.models.user import User
from app.schemas.proxy_pool import ProxyPoolEntryCreate, ProxyPoolTestRequest
from app.services.proxy_pool_service import ProxyPoolService


@pytest.mark.asyncio
async def test_proxy_test_failure_does_not_disable_proxy(db_session):
    """Proxy test failures should record failure state without changing is_active."""
    user = User(
        username="proxy-user",
        email="proxy-user@example.com",
        password_hash="test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    service = ProxyPoolService(db_session)
    created = await service.create(
        user.id,
        ProxyPoolEntryCreate(raw="http://user:pass@1.2.3.4:8080", is_active=True),
    )

    async def always_fail(*_args, **_kwargs):
        return False, None, "proxy failed"

    service._test_entry = always_fail

    for _ in range(6):
        result = await service.test(
            user.id,
            ProxyPoolTestRequest(ids=[created.id], timeout=1),
        )
        assert result.results[0].is_active is True

    proxies = await service.list(user.id)
    assert proxies[0].id == created.id
    assert proxies[0].is_active is True
    assert proxies[0].fail_count == 6
