"""Push notification schemas for API request/response."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# ============ Subscription Schemas ============

class SubscriptionCreate(BaseModel):
    """Schema for creating a push notification subscription."""
    name: str = Field(..., min_length=1, max_length=200, description="订阅名称")
    subscription_type: Literal['feed', 'category', 'keyword'] = Field(..., description="订阅类型")
    target_id: int | None = Field(None, description="订阅源或分组 ID")
    keyword: str | None = Field(None, max_length=500, description="关键词")
    browser_notification: bool = Field(True, description="是否启用浏览器通知")
    desktop_notification: bool = Field(True, description="是否启用桌面通知")
    quiet_hours: dict | None = Field(None, description="静默时间段，格式: {start: '23:00', end: '07:00'}")


class SubscriptionUpdate(BaseModel):
    """Schema for updating a push notification subscription."""
    name: str | None = Field(None, min_length=1, max_length=200)
    is_enabled: bool | None = None
    browser_notification: bool | None = None
    desktop_notification: bool | None = None
    quiet_hours: dict | None = None


class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""
    id: int
    user_id: int
    name: str
    subscription_type: str
    target_id: int | None
    keyword: str | None
    is_enabled: bool
    browser_notification: bool
    desktop_notification: bool
    quiet_hours: str | None
    created_at: datetime
    updated_at: datetime

    # 额外的显示信息
    target_name: str | None = None  # Feed/Category 名称

    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    """Schema for subscription list response."""
    subscriptions: list[SubscriptionResponse]
    total: int


# ============ Push Record Schemas ============

class PushResponse(BaseModel):
    """Schema for push record response."""
    id: int
    user_id: int
    subscription_id: int
    article_id: int
    status: str
    pushed_at: datetime
    read_at: datetime | None
    clicked_at: datetime | None

    # 关联信息
    subscription_name: str
    article_title: str
    article_link: str | None

    class Config:
        from_attributes = True


class PushListResponse(BaseModel):
    """Schema for push list response."""
    pushes: list[PushResponse]
    total: int
    page: int
    size: int


class PushStatsResponse(BaseModel):
    """Schema for push statistics response."""
    total_pushes: int
    unread_pushes: int
    clicked_pushes: int


# ============ Web Push Schemas ============

class WebPushSubscriptionCreate(BaseModel):
    """Schema for creating Web Push subscription."""
    endpoint: str = Field(..., description="Push service endpoint")
    keys: dict = Field(..., description="Push subscription keys (p256dh, auth)")
    user_agent: str | None = Field(None, max_length=500, description="User agent string")


class WebPushSubscriptionResponse(BaseModel):
    """Schema for Web Push subscription response."""
    id: int
    user_id: int
    endpoint: str
    created_at: datetime

    class Config:
        from_attributes = True


class VAPIDPublicKeyResponse(BaseModel):
    """Schema for VAPID public key response."""
    public_key: str
