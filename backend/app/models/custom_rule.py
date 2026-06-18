"""CustomRule model for custom web scraping rules."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.feed import Feed
    from app.models.user import User


class CustomRule(BaseModel):
    """Custom scraping rule for websites without RSS feeds."""

    __tablename__ = "custom_rules"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    feed_id: Mapped[int | None] = mapped_column(
        ForeignKey("feeds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    # Rule identification
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False, default='general')  # general, telegram, twitter
    cookies: Mapped[str | None] = mapped_column(Text, nullable=True)  # Cookies for authenticated requests
    
    # CSS selectors for content extraction
    list_selector: Mapped[str] = mapped_column(String(500), nullable=False)  # Selector for article list
    title_selector: Mapped[str] = mapped_column(String(500), nullable=False)  # Selector for title
    link_selector: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Selector for link
    content_selector: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Selector for content
    date_selector: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Selector for date
    
    # Fetch settings
    fetch_interval: Mapped[int] = mapped_column(Integer, default=3600)  # seconds
    use_playwright: Mapped[bool] = mapped_column(Boolean, default=False)  # Use browser for JS sites
    proxy_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proxy_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    proxy_mode: Mapped[str] = mapped_column(String(20), default="none", nullable=False)  # none, single, pool
    proxy_pool_country: Mapped[str | None] = mapped_column(String(20), nullable=True)
    proxy_pool_protocol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # AI settings
    auto_translate: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_summarize: Mapped[bool] = mapped_column(Boolean, default=False)
    source_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    target_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    translate_method: Mapped[str] = mapped_column(String(20), default='none')  # none, ai, google, argos, mc_translation
    translate_title: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    translate_content: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="custom_rules")
    category: Mapped["Category | None"] = relationship("Category", back_populates="custom_rules")
    feed: Mapped["Feed | None"] = relationship("Feed", back_populates="custom_rule")

    def __repr__(self) -> str:
        return f"<CustomRule(id={self.id}, name={self.name})>"
