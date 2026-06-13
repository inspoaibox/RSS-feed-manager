"""Google Translate key schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class GoogleTranslateKeyCreate(BaseModel):
    """Create a Google Translate API key."""

    name: str = Field(..., min_length=1, max_length=100)
    api_key: str = Field(..., min_length=1, max_length=500)
    is_active: bool = True
    limit_days: int | None = Field(None, ge=1)
    limit_articles: int | None = Field(None, ge=1)
    limit_characters: int | None = Field(None, ge=1)


class GoogleTranslateKeyUpdate(BaseModel):
    """Update a Google Translate API key."""

    name: str | None = Field(None, min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1, max_length=500)
    is_active: bool | None = None
    position: int | None = Field(None, ge=0)
    limit_days: int | None = Field(None, ge=1)
    limit_articles: int | None = Field(None, ge=1)
    limit_characters: int | None = Field(None, ge=1)


class GoogleTranslateKeyResponse(BaseModel):
    """Google Translate API key response."""

    id: int
    name: str
    masked_api_key: str
    is_active: bool
    position: int
    limit_days: int | None
    limit_articles: int | None
    limit_characters: int | None
    usage_started_at: datetime | None
    usage_article_count: int
    usage_character_count: int
    last_used_at: datetime | None
    last_error: str | None
    fail_count: int
    is_exhausted: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class GoogleTranslateKeyTestResponse(BaseModel):
    """Google Translate API key test response."""

    success: bool
    message: str
