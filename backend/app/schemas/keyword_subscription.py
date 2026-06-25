"""Keyword subscription schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class KeywordSubscriptionCreate(BaseModel):
    """Schema for creating a keyword subscription."""

    keyword: str = Field(..., min_length=1, max_length=200)
    name: str | None = Field(None, max_length=100)
    is_active: bool = True
    match_title: bool = True
    match_content: bool = True
    match_author: bool = False
    match_feed_title: bool = False
    excluded_category_ids: list[int] = Field(default_factory=list)
    excluded_feed_ids: list[int] = Field(default_factory=list)


class KeywordSubscriptionUpdate(BaseModel):
    """Schema for updating a keyword subscription."""

    keyword: str | None = Field(None, min_length=1, max_length=200)
    name: str | None = Field(None, max_length=100)
    is_active: bool | None = None
    match_title: bool | None = None
    match_content: bool | None = None
    match_author: bool | None = None
    match_feed_title: bool | None = None
    excluded_category_ids: list[int] | None = None
    excluded_feed_ids: list[int] | None = None
    position: int | None = None


class KeywordSubscriptionResponse(BaseModel):
    """Schema for keyword subscription response."""

    id: int
    name: str
    keyword: str
    is_active: bool
    match_title: bool
    match_content: bool
    match_author: bool
    match_feed_title: bool
    excluded_category_ids: list[int] = Field(default_factory=list)
    excluded_feed_ids: list[int] = Field(default_factory=list)
    position: int
    article_count: int = 0
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class KeywordSubscriptionCountResponse(BaseModel):
    """Schema for keyword subscription article counts."""

    id: int
    article_count: int = 0
    unread_count: int = 0
