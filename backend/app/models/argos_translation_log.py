"""Argos local translation execution logs."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import BaseModel


class ArgosTranslationLog(BaseModel):
    """A persisted log entry for one local Argos article translation."""

    __tablename__ = "argos_translation_logs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feed_id: Mapped[int | None] = mapped_column(
        ForeignKey("feeds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    feed_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    article_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_language: Mapped[str] = mapped_column(String(10), nullable=False)
    target_language: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="translating", nullable=False, index=True)
    title_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ArgosTranslationLog(id={self.id}, article_id={self.article_id}, status={self.status})>"
