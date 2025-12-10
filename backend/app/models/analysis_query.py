"""AnalysisQuery model for storing user query history."""
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class AnalysisQuery(BaseModel):
    """Model for storing user AI analysis query history."""

    __tablename__ = "analysis_queries"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="analysis_queries")

    def __repr__(self) -> str:
        return f"<AnalysisQuery(id={self.id}, query={self.query[:30]}...)>"
