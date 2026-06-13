"""Google Translate key pool model."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class GoogleTranslateKey(BaseModel):
    """A paid Google Translate API key with rotation limits."""

    __tablename__ = "google_translate_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "api_key", name="uq_google_translate_key_user_api_key"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    limit_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_articles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_characters: Mapped[int | None] = mapped_column(Integer, nullable=True)

    usage_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_article_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage_character_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="google_translate_keys")

    def __repr__(self) -> str:
        return f"<GoogleTranslateKey(id={self.id}, name={self.name})>"
