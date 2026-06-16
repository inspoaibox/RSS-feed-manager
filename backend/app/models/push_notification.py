"""Push notification models."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.article import Article


class NotificationSubscription(BaseModel):
    """用户的推送通知订阅规则"""

    __tablename__ = "notification_subscriptions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 订阅名称
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 订阅类型: feed(单个订阅源), category(分组), keyword(关键词)
    subscription_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # 根据类型，存储对应的 ID 或关键词
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    keyword: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)

    # 是否启用
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # 通知方式
    browser_notification: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    desktop_notification: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # 静默时间段（JSON 格式存储，例如: {"start": "23:00", "end": "07:00"}）
    quiet_hours: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="push_subscriptions")

    def __repr__(self) -> str:
        return f"<NotificationSubscription(id={self.id}, name={self.name}, type={self.subscription_type})>"


class NotificationPush(BaseModel):
    """已推送的通知记录"""

    __tablename__ = "notification_pushes"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("notification_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 推送状态: sent(已发送), failed(发送失败), read(已读), clicked(已点击)
    status: Mapped[str] = mapped_column(String(50), default="sent", server_default="sent", index=True)

    # 推送时间
    pushed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    # 已读时间
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 点击时间
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    subscription: Mapped["NotificationSubscription"] = relationship("NotificationSubscription")
    article: Mapped["Article"] = relationship("Article")

    def __repr__(self) -> str:
        return f"<NotificationPush(id={self.id}, user_id={self.user_id}, article_id={self.article_id})>"


class WebPushSubscription(BaseModel):
    """Web Push 订阅信息"""

    __tablename__ = "web_push_subscriptions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Web Push 订阅信息
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)

    # 用户代理（可选，用于识别设备）
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="web_push_subscriptions")

    def __repr__(self) -> str:
        return f"<WebPushSubscription(id={self.id}, user_id={self.user_id})>"
