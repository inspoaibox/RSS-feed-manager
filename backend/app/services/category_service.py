"""Category service for business logic."""
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.feed import Feed
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate


class CategoryService:
    """Service for category operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CategoryRepository(session)

    async def create(self, user_id: int, data: CategoryCreate) -> CategoryResponse:
        """Create a new category."""
        # Check for duplicate name
        if await self.repo.exists_by_name(user_id, data.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category with this name already exists"
            )
        
        category = await self.repo.create(
            user_id=user_id,
            name=data.name,
            description=data.description
        )
        
        return CategoryResponse(
            id=category.id,
            name=category.name,
            description=category.description,
            position=category.position,
            feed_count=0,
            unread_count=0
        )

    async def get_all(self, user_id: int) -> List[CategoryResponse]:
        """Get all categories for a user with feed counts."""
        categories = await self.repo.get_all_by_user(user_id)
        
        result = []
        for cat in categories:
            feed_count = await self.repo.count_feeds(cat.id)
            # TODO: Calculate unread count when article service is ready
            result.append(CategoryResponse(
                id=cat.id,
                name=cat.name,
                description=cat.description,
                position=cat.position,
                feed_count=feed_count,
                unread_count=0
            ))
        
        return result

    async def get_by_id(self, user_id: int, category_id: int) -> CategoryResponse:
        """Get a category by ID."""
        category = await self.repo.get_by_id(category_id, user_id)
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        feed_count = await self.repo.count_feeds(category.id)
        
        return CategoryResponse(
            id=category.id,
            name=category.name,
            description=category.description,
            position=category.position,
            feed_count=feed_count,
            unread_count=0
        )

    async def update(
        self, user_id: int, category_id: int, data: CategoryUpdate
    ) -> CategoryResponse:
        """Update a category."""
        category = await self.repo.get_by_id(category_id, user_id)
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        # Check for duplicate name if name is being changed
        if data.name and data.name != category.name:
            if await self.repo.exists_by_name(user_id, data.name, exclude_id=category_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Category with this name already exists"
                )
        
        category = await self.repo.update(
            category,
            name=data.name,
            description=data.description
        )
        
        feed_count = await self.repo.count_feeds(category.id)
        
        return CategoryResponse(
            id=category.id,
            name=category.name,
            description=category.description,
            position=category.position,
            feed_count=feed_count,
            unread_count=0
        )

    async def delete(self, user_id: int, category_id: int) -> None:
        """Delete a category and move its feeds to default category."""
        category = await self.repo.get_by_id(category_id, user_id)
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        # Don't allow deleting the default category
        if category.name == "Default":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the default category"
            )
        
        # Move feeds to default category
        default_category = await self.repo.get_default_category(user_id)
        
        await self.session.execute(
            update(Feed)
            .where(Feed.category_id == category_id)
            .values(category_id=default_category.id)
        )
        
        await self.repo.delete(category)
