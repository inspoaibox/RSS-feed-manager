"""Proxy pool schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProxyProtocol = Literal["http", "https", "socks4", "socks5", "socks5h"]


class ProxyPoolEntryCreate(BaseModel):
    """Create a proxy from a raw proxy string."""

    raw: str = Field(..., min_length=1, max_length=2048)
    default_protocol: ProxyProtocol = "http"
    country: str | None = Field(None, max_length=20)
    is_active: bool = True


class ProxyPoolEntryUpdate(BaseModel):
    """Update a proxy pool entry."""

    raw: str | None = Field(None, min_length=1, max_length=2048)
    default_protocol: ProxyProtocol | None = None
    country: str | None = Field(None, max_length=20)
    is_active: bool | None = None
    fail_count: int | None = Field(None, ge=0)


class ProxyPoolImportRequest(BaseModel):
    """Import many proxies from pasted text."""

    content: str = Field(..., min_length=1)
    default_protocol: ProxyProtocol = "http"
    default_country: str | None = Field(None, max_length=20)
    is_active: bool = True


class ProxyPoolEntryResponse(BaseModel):
    """Proxy pool entry response."""

    id: int
    protocol: str
    host: str
    port: int
    username: str | None
    password: str | None
    country: str | None
    source_format: str
    proxy_url: str
    is_active: bool
    fail_count: int
    last_used_at: datetime | None
    last_tested_at: datetime | None
    last_latency_ms: int | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class ProxyPoolImportResult(BaseModel):
    """Import result."""

    imported: int
    skipped: int
    errors: list[str]
    items: list[ProxyPoolEntryResponse]


class ProxyPoolTestRequest(BaseModel):
    """Batch test proxies."""

    ids: list[int] | None = None
    country: str | None = Field(None, max_length=20)
    protocol: ProxyProtocol | None = None
    active_only: bool = False
    test_url: str = Field(default="https://www.gstatic.com/generate_204", max_length=2048)
    timeout: float = Field(default=10.0, ge=1.0, le=60.0)


class ProxyPoolTestItem(BaseModel):
    """Single proxy test result."""

    id: int
    success: bool
    latency_ms: int | None = None
    error: str | None = None
    is_active: bool
    fail_count: int


class ProxyPoolTestResult(BaseModel):
    """Batch proxy test result."""

    total: int
    success: int
    failed: int
    results: list[ProxyPoolTestItem]


class ProxyPoolGroupsResponse(BaseModel):
    """Available proxy groups."""

    countries: list[str]
    protocols: list[str]
