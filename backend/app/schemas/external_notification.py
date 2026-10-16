"""Request and response validation for external notifications."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Provider = Literal[
    "feishu", "telegram", "wecom", "email", "bark", "pushplus", "serverchan", "webhook"
]
SourceType = Literal["feed", "category"]
DeliveryStatus = Literal["pending", "queued", "sending", "sent", "failed", "skipped"]


class ChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    webhook_url: str | None = Field(None, max_length=2048)
    signing_secret: str | None = Field(None, max_length=256)
    bot_token: str | None = Field(None, max_length=256)
    chat_id: str | None = Field(None, max_length=100)
    message_thread_id: int | None = Field(None, ge=1)
    server_url: str | None = Field(None, max_length=2048)
    device_key: str | None = Field(None, max_length=256)
    bark_group: str | None = Field(None, max_length=100)
    pushplus_token: str | None = Field(None, max_length=256)
    pushplus_channel: (
        Literal["wechat", "app", "mail", "webhook", "cp", "extension", "qq"] | None
    ) = None
    pushplus_topic: str | None = Field(None, max_length=100)
    pushplus_option: str | None = Field(None, max_length=100)
    serverchan_send_key: str | None = Field(None, max_length=256)
    smtp_host: str | None = Field(None, max_length=253)
    smtp_port: int | None = Field(None, ge=1, le=65535)
    smtp_security: Literal["ssl", "starttls"] | None = None
    smtp_username: str | None = Field(None, max_length=320)
    smtp_password: str | None = Field(None, max_length=512)
    smtp_from: str | None = Field(None, max_length=320)
    smtp_to: list[str] | None = Field(None, min_length=1, max_length=20)
    webhook_method: Literal["POST", "PUT"] | None = None
    webhook_headers: dict[str, str] | None = None
    webhook_body: dict[str, Any] | None = None


class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider: Provider
    config: ChannelConfig
    is_enabled: bool = True


class ChannelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    config: ChannelConfig | None = None
    is_enabled: bool | None = None


class ChannelResponse(BaseModel):
    id: int
    name: str
    provider: Provider
    is_enabled: bool
    has_webhook: bool
    has_signing_secret: bool
    has_bot_token: bool
    chat_id: str | None
    message_thread_id: int | None
    has_server_url: bool = False
    has_device_key: bool = False
    has_pushplus_token: bool = False
    has_serverchan_send_key: bool = False
    has_smtp_password: bool = False
    has_webhook_headers: bool = False
    has_webhook_body: bool = False
    bark_group: str | None = None
    pushplus_channel: str | None = None
    pushplus_topic: str | None = None
    pushplus_option: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_security: str | None = None
    smtp_username: str | None = None
    smtp_from: str | None = None
    smtp_to: list[str] = Field(default_factory=list)
    webhook_method: str | None = None
    created_at: datetime


class RulePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    source_type: SourceType
    source_id: int = Field(..., ge=1)
    channel_ids: list[int] = Field(..., min_length=1, max_length=20)
    is_enabled: bool = True


class RuleResponse(RulePayload):
    channel_ids: list[int] = Field(default_factory=list)
    id: int
    source_name: str | None


class RestoredRulePayload(RulePayload):
    """A saved orphan rule can be restored; ordinary API writes still need a destination."""

    channel_ids: list[int] = Field(..., max_length=20)


class DeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel_name: str
    provider: Provider
    article_title: str
    is_test: bool
    status: DeliveryStatus
    attempts: int
    error: str | None
    created_at: datetime
    sent_at: datetime | None


class DeliveryList(BaseModel):
    items: list[DeliveryResponse]
    total: int
    page: int
    page_size: int
