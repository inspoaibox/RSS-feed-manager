"""Feed schemas for request/response validation."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

FeedBrowserEngine = Literal["http", "playwright", "cloakbrowser"]
FeedProxyMode = Literal["none", "single", "pool"]
FeedProxyProtocol = Literal["http", "https", "socks4", "socks5", "socks5h"]
FeedTranslateMethod = Literal["none", "ai", "google", "argos"]


class FeedCreate(BaseModel):
    """Schema for creating a feed."""
    url: str = Field(..., max_length=2048)
    category_id: int | None = None
    fetch_interval: int = Field(default=3600, ge=60, le=86400)
    use_playwright: bool = False  # Use browser automation for Cloudflare protected sites
    browser_engine: FeedBrowserEngine | None = None
    proxy_enabled: bool = False
    proxy_url: str | None = Field(None, max_length=2048)
    proxy_mode: FeedProxyMode | None = None
    proxy_pool_country: str | None = Field(None, max_length=20)
    proxy_pool_protocol: FeedProxyProtocol | None = None
    auto_translate: bool = False  # Auto translate articles using AI
    auto_summarize: bool = False  # Auto summarize articles using AI
    source_language: str | None = Field(None, max_length=10)  # Source language for local translation
    target_language: str | None = Field(None, max_length=10)  # Target language for translation
    translate_method: FeedTranslateMethod = "none"  # Translation method
    translate_title: bool = True
    translate_content: bool = False

    @property
    def resolved_browser_engine(self) -> FeedBrowserEngine:
        if self.browser_engine:
            return self.browser_engine
        return "playwright" if self.use_playwright else "http"


class FeedUpdate(BaseModel):
    """Schema for updating a feed."""
    title: str | None = Field(None, max_length=255)
    category_id: int | None = None
    fetch_interval: int | None = Field(None, ge=60, le=86400)
    auto_translate: bool | None = None
    auto_summarize: bool | None = None
    source_language: str | None = Field(None, max_length=10)
    target_language: str | None = Field(None, max_length=10)
    translate_method: FeedTranslateMethod | None = None
    translate_title: bool | None = None
    translate_content: bool | None = None
    is_active: bool | None = None
    use_playwright: bool | None = None
    browser_engine: FeedBrowserEngine | None = None
    proxy_enabled: bool | None = None
    proxy_url: str | None = Field(None, max_length=2048)
    proxy_mode: FeedProxyMode | None = None
    proxy_pool_country: str | None = Field(None, max_length=20)
    proxy_pool_protocol: FeedProxyProtocol | None = None
    position: int | None = None


class FeedReorder(BaseModel):
    """Schema for reordering feeds."""
    feed_ids: list[int] = Field(..., description="Feed IDs in desired order")


class FeedResponse(BaseModel):
    """Schema for feed response."""
    id: int
    url: str
    title: str
    description: str | None
    site_url: str | None
    icon_url: str | None
    category_id: int | None
    fetch_interval: int
    last_fetched_at: datetime | None
    auto_translate: bool
    auto_summarize: bool
    source_language: str | None
    target_language: str | None
    translate_method: FeedTranslateMethod = "none"
    translate_title: bool = True
    translate_content: bool = False
    is_active: bool
    use_playwright: bool = False
    browser_engine: FeedBrowserEngine = "http"
    proxy_enabled: bool = False
    proxy_url: str | None = None
    proxy_mode: FeedProxyMode = "none"
    proxy_pool_country: str | None = None
    proxy_pool_protocol: FeedProxyProtocol | None = None
    position: int = 0
    unread_count: int = 0
    article_count: int = 0

    class Config:
        from_attributes = True


class FeedListResponse(BaseModel):
    """Schema for list of feeds."""
    items: list[FeedResponse]
    total: int


class OPMLImportResult(BaseModel):
    """Schema for OPML import result."""
    imported: int
    skipped: int
    errors: list[str]
