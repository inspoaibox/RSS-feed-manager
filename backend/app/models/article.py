"""Article and UserArticle models for feed content."""
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModel

if TYPE_CHECKING:
    from app.models.feed import Feed
    from app.models.user import User


class Article(BaseModel):
    """Article model representing a single feed entry."""

    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("feed_id", "guid", name="uq_article_feed_guid"),
    )

    feed_id: Mapped[int] = mapped_column(
        ForeignKey("feeds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Article identifiers
    guid: Mapped[str] = mapped_column(String(2048), nullable=False)
    link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    
    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # Original RSS content
    full_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # Extracted full text
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI-generated summary
    translation: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI translation
    translation_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    translation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    translation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    author: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Cached images (JSON array of local paths)
    cached_images: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Vector embedding for semantic search (1536 dimensions for OpenAI text-embedding-3-small)
    embedding: Mapped[Any | None] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    feed: Mapped["Feed"] = relationship("Feed", back_populates="articles")

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title={self.title[:30]}...)>"


class UserArticle(Base):
    """Association table for user-specific article state (read, favorite)."""

    __tablename__ = "user_articles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    
    # User-specific state
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    favorited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    article: Mapped["Article"] = relationship("Article")

    def __repr__(self) -> str:
        return f"<UserArticle(user_id={self.user_id}, article_id={self.article_id})>"
