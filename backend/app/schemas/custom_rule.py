"""Custom rule schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

TranslateMethod = str
CustomRuleProxyMode = Literal["none", "single", "pool"]
CustomRuleProxyProtocol = Literal["http", "https", "socks4", "socks5", "socks5h"]
TRANSLATE_METHOD_PATTERN = "^(none|ai|google|argos)$"


class CustomRuleBase(BaseModel):
    """Base custom rule schema."""
    name: str = Field(..., min_length=1, max_length=100)
    target_url: str = Field(..., max_length=2048)
    rule_type: str = Field(default='general', max_length=20)  # general, telegram, twitter
    cookies: str | None = Field(None, max_length=10000)  # Cookies for authenticated requests
    list_selector: str = Field(..., max_length=500)
    title_selector: str = Field(..., max_length=500)
    link_selector: str | None = Field(None, max_length=500)
    content_selector: str | None = Field(None, max_length=500)
    date_selector: str | None = Field(None, max_length=500)
    fetch_interval: int = Field(default=3600, ge=300, le=86400)
    use_playwright: bool = False
    proxy_enabled: bool = False
    proxy_url: str | None = Field(None, max_length=2048)
    proxy_mode: CustomRuleProxyMode | None = None
    proxy_pool_country: str | None = Field(None, max_length=20)
    proxy_pool_protocol: CustomRuleProxyProtocol | None = None
    auto_translate: bool = False
    auto_summarize: bool = False
    source_language: str | None = Field(None, max_length=10)
    target_language: str | None = Field(None, max_length=10)
    translate_method: TranslateMethod = Field(default='none', pattern=TRANSLATE_METHOD_PATTERN)
    is_active: bool = True


class CustomRuleCreate(CustomRuleBase):
    """Schema for creating a custom rule."""
    category_id: int | None = None


class CustomRuleUpdate(BaseModel):
    """Schema for updating a custom rule."""
    name: str | None = Field(None, min_length=1, max_length=100)
    target_url: str | None = Field(None, max_length=2048)
    rule_type: str | None = Field(None, max_length=20)
    cookies: str | None = Field(None, max_length=10000)
    category_id: int | None = None
    list_selector: str | None = Field(None, max_length=500)
    title_selector: str | None = Field(None, max_length=500)
    link_selector: str | None = Field(None, max_length=500)
    content_selector: str | None = Field(None, max_length=500)
    date_selector: str | None = Field(None, max_length=500)
    fetch_interval: int | None = Field(None, ge=300, le=86400)
    use_playwright: bool | None = None
    proxy_enabled: bool | None = None
    proxy_url: str | None = Field(None, max_length=2048)
    proxy_mode: CustomRuleProxyMode | None = None
    proxy_pool_country: str | None = Field(None, max_length=20)
    proxy_pool_protocol: CustomRuleProxyProtocol | None = None
    auto_translate: bool | None = None
    auto_summarize: bool | None = None
    source_language: str | None = Field(None, max_length=10)
    target_language: str | None = Field(None, max_length=10)
    translate_method: TranslateMethod | None = Field(None, pattern=TRANSLATE_METHOD_PATTERN)
    is_active: bool | None = None


class CustomRuleResponse(BaseModel):
    """Schema for custom rule response."""
    id: int
    user_id: int
    category_id: int | None
    feed_id: int | None
    name: str
    target_url: str
    rule_type: str
    cookies: str | None
    list_selector: str
    title_selector: str
    link_selector: str | None
    content_selector: str | None
    date_selector: str | None
    fetch_interval: int
    use_playwright: bool
    proxy_enabled: bool = False
    proxy_url: str | None = None
    proxy_mode: CustomRuleProxyMode = "none"
    proxy_pool_country: str | None = None
    proxy_pool_protocol: CustomRuleProxyProtocol | None = None
    auto_translate: bool
    auto_summarize: bool
    source_language: str | None
    target_language: str | None
    translate_method: str = 'none'
    is_active: bool
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
    proxy_enabled: bool = False
    proxy_url: str | None = Field(None, max_length=2048)
    proxy_mode: CustomRuleProxyMode | None = None
    proxy_pool_country: str | None = Field(None, max_length=20)
    proxy_pool_protocol: CustomRuleProxyProtocol | None = None


class CustomRuleTestResult(BaseModel):
    """Schema for custom rule test result."""
    success: bool
    items_found: int
    sample_items: list[dict]
    error: str | None = None


class AIGenerateRuleRequest(BaseModel):
    """Schema for AI-generated rule request."""
    target_url: str = Field(..., max_length=2048)
    custom_prompt: str | None = Field(None, max_length=10000)  # Custom prompt for AI generation


class AIGenerateRuleResponse(BaseModel):
    """Schema for AI-generated rule response."""
    success: bool
    name: str | None = None
    list_selector: str | None = None
    title_selector: str | None = None
    link_selector: str | None = None
    content_selector: str | None = None
    date_selector: str | None = None
    error: str | None = None
