"""Notification schemas for API request/response."""
from datetime import datetime
from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    """Schema for creating a notification."""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    type: str = Field(default='system', pattern='^(system|update|maintenance)$')
    expires_at: datetime | None = None


class NotificationUpdate(BaseModel):
    """Schema for updating a notification."""
    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1)
    type: str | None = Field(None, pattern='^(system|update|maintenance)$')
    is_active: bool | None = None
    expires_at: datetime | None = None


class NotificationResponse(BaseModel):
    """Schema for notification response."""
    id: int
    title: str
    content: str
    type: str
    is_active: bool
    created_by: int | None
    creator_name: str | None
    expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for notification list response."""
    notifications: list[NotificationResponse]
    total: int


class UnreadCountResponse(BaseModel):
    """Schema for unread notification count."""
    count: int


class MarkReadResponse(BaseModel):
    """Schema for mark as read response."""
    success: bool
    message: str
