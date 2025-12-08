"""Category model for organizing feeds."""
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.custom_rule import CustomRule
    from app.models.feed import Feed
    from app.models.user import User


class Category(BaseModel):
    """Category model for organizing feeds into groups."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_category_user_name"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(default=0)  # For ordering categories

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="categories")
    feeds: Mapped[List["Feed"]] = relationship(
        "Feed", back_populates="category", cascade="all, delete-orphan"
    )
    custom_rules: Mapped[List["CustomRule"]] = relationship(
        "CustomRule", back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name})>"
