"""Feed schemas for request/response validation."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

FeedBrowserEngine = Literal["http", "playwright", "cloakbrowser"]


class FeedCreate(BaseModel):
    """Schema for creating a feed."""
    url: str = Field(..., max_length=2048)
    category_id: int | None = None
    fetch_interval: int = Field(default=3600, ge=60, le=86400)
    use_playwright: bool = False  # Use browser automation for Cloudflare protected sites
    browser_engine: FeedBrowserEngine | None = None
    auto_translate: bool = False  # Auto translate articles using AI
    auto_summarize: bool = False  # Auto summarize articles using AI
    target_language: str | None = Field(None, max_length=10)  # Target language for translation
    translate_method: str = Field(default='none', pattern='^(none|ai|google)$')  # Translation method

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
    target_language: str | None = Field(None, max_length=10)
    translate_method: str | None = Field(None, pattern='^(none|ai|google)$')
    is_active: bool | None = None
    use_playwright: bool | None = None
    browser_engine: FeedBrowserEngine | None = None
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
    target_language: str | None
    translate_method: str = 'none'
    is_active: bool
    use_playwright: bool = False
    browser_engine: FeedBrowserEngine = "http"
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
