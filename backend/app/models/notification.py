"""Notification model for system announcements."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Notification(BaseModel):
    """System notification model for admin announcements."""

    __tablename__ = "notifications"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 通知类型: system(系统公告), update(更新通知), maintenance(维护通知)
    type: Mapped[str] = mapped_column(String(50), default='system')
    
    # 是否启用（管理员可以禁用通知）
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 创建者（管理员）
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    
    # 过期时间（可选，过期后不再显示）
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, title={self.title[:30]}...)>"


class UserNotificationRead(BaseModel):
    """Track which users have read which notifications."""

    __tablename__ = "user_notification_reads"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    notification: Mapped["Notification"] = relationship("Notification")

    def __repr__(self) -> str:
        return f"<UserNotificationRead(user_id={self.user_id}, notification_id={self.notification_id})>"
