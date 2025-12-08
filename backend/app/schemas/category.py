"""Category schemas for request/response validation."""
from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    """Schema for creating a category."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class CategoryResponse(BaseModel):
    """Schema for category response."""
    id: int
    name: str
    description: str | None
    position: int
    feed_count: int = 0
    unread_count: int = 0

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    """Schema for list of categories."""
    items: list[CategoryResponse]
    total: int
