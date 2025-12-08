"""Custom rule schemas."""
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class CustomRuleBase(BaseModel):
    """Base custom rule schema."""
    name: str = Field(..., min_length=1, max_length=100)
    target_url: str = Field(..., max_length=2048)
    rule_type: str = Field(default='general', max_length=20)  # general, telegram
    list_selector: str = Field(..., max_length=500)
    title_selector: str = Field(..., max_length=500)
    link_selector: str | None = Field(None, max_length=500)
    content_selector: str | None = Field(None, max_length=500)
    date_selector: str | None = Field(None, max_length=500)
    fetch_interval: int = Field(default=3600, ge=300, le=86400)
    use_playwright: bool = False
    auto_translate: bool = False
    auto_summarize: bool = False
    target_language: str | None = Field(None, max_length=10)
    is_active: bool = True


class CustomRuleCreate(CustomRuleBase):
    """Schema for creating a custom rule."""
    category_id: int | None = None


class CustomRuleUpdate(BaseModel):
    """Schema for updating a custom rule."""
    name: str | None = Field(None, min_length=1, max_length=100)
    target_url: str | None = Field(None, max_length=2048)
    rule_type: str | None = Field(None, max_length=20)
    category_id: int | None = None
    list_selector: str | None = Field(None, max_length=500)
    title_selector: str | None = Field(None, max_length=500)
    link_selector: str | None = Field(None, max_length=500)
    content_selector: str | None = Field(None, max_length=500)
    date_selector: str | None = Field(None, max_length=500)
    fetch_interval: int | None = Field(None, ge=300, le=86400)
    use_playwright: bool | None = None
    auto_translate: bool | None = None
    auto_summarize: bool | None = None
    target_language: str | None = Field(None, max_length=10)
    is_active: bool | None = None


class CustomRuleResponse(CustomRuleBase):
    """Schema for custom rule response."""
    id: int
    user_id: int
    category_id: int | None
    feed_id: int | None
    last_fetched_at: datetime | None
    last_error: str | None
    error_count: int
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class CustomRuleTestRequest(BaseModel):
    """Schema for testing a custom rule."""
    target_url: str = Field(..., max_length=2048)
    list_selector: str = Field(..., max_length=500)
    title_selector: str = Field(..., max_length=500)
    link_selector: str | None = Field(None, max_length=500)
    content_selector: str | None = Field(None, max_length=500)
    date_selector: str | None = Field(None, max_length=500)
    use_playwright: bool = False


class CustomRuleTestResult(BaseModel):
    """Schema for custom rule test result."""
    success: bool
    items_found: int
    sample_items: list[dict]
    error: str | None = None


class AIGenerateRuleRequest(BaseModel):
    """Schema for AI-generated rule request."""
    target_url: str = Field(..., max_length=2048)


class AIGenerateRuleResponse(BaseModel):
    """Schema for AI-generated rule response."""
    success: bool
    name: str | None = None
    list_selector: str | None = None
    title_selector: str | None = None
    link_selector: str | None = None
    content_selector: str | None = None
    error: str | None = None
