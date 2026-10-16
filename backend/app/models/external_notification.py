"""User-owned external notification channels, routing rules and delivery outbox."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModel

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.user import User


class NotificationChannel(BaseModel):
    __tablename__ = "notification_channels"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_notification_channel_name"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(20))
    encrypted_config: Mapped[str] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped["User"] = relationship(back_populates="notification_channels")
    rule_links: Mapped[list["NotificationRuleChannel"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )
    deliveries: Mapped[list["NotificationDelivery"]] = relationship(back_populates="channel")


class NotificationRule(BaseModel):
    __tablename__ = "notification_rules"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "name", "source_type", "source_id", name="uq_notification_rule_name_source"
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[int] = mapped_column(Integer)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped["User"] = relationship(back_populates="notification_rules")
    channel_links: Mapped[list["NotificationRuleChannel"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class NotificationRuleChannel(Base):
    __tablename__ = "notification_rule_channels"

    rule_id: Mapped[int] = mapped_column(
        ForeignKey("notification_rules.id", ondelete="CASCADE"),
        primary_key=True,
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rule: Mapped["NotificationRule"] = relationship(back_populates="channel_links")
    channel: Mapped["NotificationChannel"] = relationship(back_populates="rule_links")


class NotificationDelivery(BaseModel):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("channel_id", "article_id", name="uq_notification_delivery"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="SET NULL"),
        nullable=True,
    )
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel_name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(20))
    article_title: Mapped[str] = mapped_column(String(500))
    message: Mapped[str] = mapped_column(Text)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    failure_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped["User"] = relationship(back_populates="notification_deliveries")
    channel: Mapped["NotificationChannel | None"] = relationship(back_populates="deliveries")
    article: Mapped["Article | None"] = relationship(back_populates="external_deliveries")
