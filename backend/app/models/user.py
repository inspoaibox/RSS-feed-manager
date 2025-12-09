"""User model for authentication and user management."""
from typing import TYPE_CHECKING, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.core.security import get_password_hash, verify_password

if TYPE_CHECKING:
    from app.models.ai_provider import AIProvider
    from app.models.category import Category
    from app.models.custom_rule import CustomRule
    from app.models.feed import Feed


class User(BaseModel):
    """User model for authentication."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    
    # Token version for invalidating tokens on password change
    token_version: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # AI Prompt settings
    translate_prompt: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    summarize_prompt: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Relationships
    categories: Mapped[List["Category"]] = relationship(
        "Category", back_populates="user", cascade="all, delete-orphan"
    )
    feeds: Mapped[List["Feed"]] = relationship(
        "Feed", back_populates="user", cascade="all, delete-orphan"
    )
    ai_providers: Mapped[List["AIProvider"]] = relationship(
        "AIProvider", back_populates="user", cascade="all, delete-orphan"
    )
    custom_rules: Mapped[List["CustomRule"]] = relationship(
        "CustomRule", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        """Hash and set the user's password."""
        self.password_hash = get_password_hash(password)
        # Invalidate existing tokens (handle None for new users)
        current_version = getattr(self, 'token_version', None)
        if current_version is None:
            self.token_version = 0
        else:
            self.token_version = current_version + 1

    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        return verify_password(password, self.password_hash)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
