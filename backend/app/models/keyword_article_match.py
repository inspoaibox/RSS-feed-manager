"""Precomputed keyword-to-article matches."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KeywordArticleMatch(Base):
    """Article matched by a keyword subscription."""

    __tablename__ = "keyword_article_matches"
    __table_args__ = (
        Index("ix_keyword_article_matches_article_id", "article_id"),
    )

    keyword_subscription_id: Mapped[int] = mapped_column(
        ForeignKey("keyword_subscriptions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
