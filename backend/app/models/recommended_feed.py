"""Recommended Feed model for admin-curated RSS recommendations."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class RecommendedFeed(BaseModel):
    """Recommended feed model for admin-curated RSS subscriptions."""

    __tablename__ = "recommended_feeds"

    # Feed info
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    
    # Categories (comma-separated tags like "技术,新闻,AI")
    categories: Mapped[str] = mapped_column(String(500), default="")
    
    # Fetch settings
    use_playwright: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Admin who created this
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    
    # Relationships
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<RecommendedFeed(id={self.id}, title={self.title})>"
