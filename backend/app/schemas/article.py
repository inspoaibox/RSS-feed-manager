"""Article schemas for request/response validation."""
from datetime import datetime

from pydantic import BaseModel, Field


class ArticleResponse(BaseModel):
    """Schema for article response."""
    id: int
    feed_id: int
    title: str
    link: str
    content: str | None
    full_content: str | None
    summary: str | None
    translation: str | None
    author: str | None
    published_at: datetime | None
    is_read: bool = False
    is_favorite: bool = False
    read_at: datetime | None = None

    class Config:
        from_attributes = True


class ArticleListResponse(BaseModel):
    """Schema for paginated article list."""
    items: list[ArticleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ArticleFilter(BaseModel):
    """Schema for article filtering."""
    feed_id: int | None = None
    category_id: int | None = None
    is_read: bool | None = None
    is_favorite: bool | None = None
    sort_by: str = Field(default="published_at", pattern="^(published_at|created_at|title)$")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ArticleSearchRequest(BaseModel):
    """Schema for article search."""
    query: str = Field(..., min_length=1, max_length=200)
    feed_id: int | None = None
    category_id: int | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class MarkAllReadRequest(BaseModel):
    """Schema for marking all articles as read."""
    feed_id: int | None = None
    category_id: int | None = None


class FavoriteResponse(BaseModel):
    """Schema for favorite toggle response."""
    is_favorite: bool
