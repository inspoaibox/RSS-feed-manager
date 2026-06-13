"""Feed model for RSS/Atom subscriptions."""
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.category import Category
    from app.models.custom_rule import CustomRule
    from app.models.user import User


class Feed(BaseModel):
    """Feed model representing an RSS/Atom subscription."""

    __tablename__ = "feeds"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    # Feed metadata
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    
    # Fetch settings
    fetch_interval: Mapped[int] = mapped_column(Integer, default=3600)  # seconds
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    use_playwright: Mapped[bool] = mapped_column(Boolean, default=False)  # Use browser for Cloudflare sites
    browser_engine: Mapped[str] = mapped_column(String(20), default="http")  # http, playwright, cloakbrowser
    proxy_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proxy_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    proxy_mode: Mapped[str] = mapped_column(String(20), default="none", nullable=False)  # none, single, pool
    proxy_pool_country: Mapped[str | None] = mapped_column(String(20), nullable=True)
    proxy_pool_protocol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # AI settings
    auto_translate: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_summarize: Mapped[bool] = mapped_column(Boolean, default=False)
    target_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    translate_method: Mapped[str] = mapped_column(String(20), default='none')  # none, ai, google
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # For ordering

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="feeds")
    category: Mapped["Category | None"] = relationship("Category", back_populates="feeds")
    articles: Mapped[List["Article"]] = relationship(
        "Article", back_populates="feed", cascade="all, delete-orphan"
    )
    custom_rule: Mapped["CustomRule | None"] = relationship(
        "CustomRule", back_populates="feed", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Feed(id={self.id}, title={self.title})>"
