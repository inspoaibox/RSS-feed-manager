"""Feed schemas for request/response validation."""
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class FeedCreate(BaseModel):
    """Schema for creating a feed."""
    url: str = Field(..., max_length=2048)
    category_id: int | None = None
    fetch_interval: int = Field(default=3600, ge=60, le=86400)
    use_playwright: bool = False  # Use browser automation for Cloudflare protected sites
    auto_translate: bool = False  # Auto translate articles using AI
    auto_summarize: bool = False  # Auto summarize articles using AI
    target_language: str | None = Field(None, max_length=10)  # Target language for translation


class FeedUpdate(BaseModel):
    """Schema for updating a feed."""
    title: str | None = Field(None, max_length=255)
    category_id: int | None = None
    fetch_interval: int | None = Field(None, ge=60, le=86400)
    auto_translate: bool | None = None
    auto_summarize: bool | None = None
    target_language: str | None = Field(None, max_length=10)
    is_active: bool | None = None
    use_playwright: bool | None = None


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
    is_active: bool
    use_playwright: bool = False
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
