"""Keyword subscription model for saved article filters."""
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class KeywordSubscription(BaseModel):
    """Saved keyword filter for articles across a user's feeds."""

    __tablename__ = "keyword_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "keyword", name="uq_keyword_subscription_user_keyword"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    match_title: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    match_content: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    match_author: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    match_feed_title: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="keyword_subscriptions")

    def __repr__(self) -> str:
        return f"<KeywordSubscription(id={self.id}, keyword={self.keyword})>"
