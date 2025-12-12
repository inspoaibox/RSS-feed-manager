"""AI Provider and Model models for AI integration."""
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class AIProvider(BaseModel):
    """AI Provider model for managing AI service configurations."""

    __tablename__ = "ai_providers"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Provider configuration
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # openai, gemini, openai_compatible
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)  # For custom endpoints
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="ai_providers")
    models: Mapped[List["AIModel"]] = relationship(
        "AIModel", back_populates="provider", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AIProvider(id={self.id}, name={self.name}, type={self.type})>"


class AIModel(BaseModel):
    """AI Model model for managing available models per provider."""

    __tablename__ = "ai_models"
    __table_args__ = (
        # Unique constraint to prevent duplicate models per provider
        UniqueConstraint('provider_id', 'model_id', name='uq_ai_models_provider_model'),
    )

    provider_id: Mapped[int] = mapped_column(
        ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Model configuration
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., gpt-4, gemini-pro
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # Display name
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Default model flag (only one per user should be true)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    provider: Mapped["AIProvider"] = relationship("AIProvider", back_populates="models")

    def __repr__(self) -> str:
        return f"<AIModel(id={self.id}, model_id={self.model_id})>"
