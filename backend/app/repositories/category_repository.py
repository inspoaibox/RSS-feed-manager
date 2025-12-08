"""Category repository for database operations."""
from typing import List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category import Category


class CategoryRepository:
    """Repository for Category database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, name: str, description: str | None = None) -> Category:
        """Create a new category."""
        # Get max position for ordering
        result = await self.session.execute(
            select(func.coalesce(func.max(Category.position), -1))
            .where(Category.user_id == user_id)
        )
        max_position = result.scalar() or -1
        
        category = Category(
            user_id=user_id,
            name=name,
            description=description,
            position=max_position + 1
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def get_by_id(self, category_id: int, user_id: int) -> Category | None:
        """Get category by ID for a specific user."""
        result = await self.session.execute(
            select(Category)
            .where(Category.id == category_id, Category.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all_by_user(self, user_id: int) -> List[Category]:
        """Get all categories for a user, ordered by position."""
        result = await self.session.execute(
            select(Category)
            .where(Category.user_id == user_id)
            .order_by(Category.position)
        )
        return list(result.scalars().all())

    async def get_with_feeds(self, user_id: int) -> List[Category]:
        """Get all categories with their feeds loaded."""
        result = await self.session.execute(
            select(Category)
            .options(selectinload(Category.feeds))
            .where(Category.user_id == user_id)
            .order_by(Category.position)
        )
        return list(result.scalars().all())

    async def update(
        self,
        category: Category,
        name: str | None = None,
        description: str | None = None
    ) -> Category:
        """Update category fields."""
        if name is not None:
            category.name = name
        if description is not None:
            category.description = description
        await self.session.flush()
        return category

    async def delete(self, category: Category) -> None:
        """Delete a category."""
        await self.session.delete(category)
        await self.session.flush()

    async def exists_by_name(self, user_id: int, name: str, exclude_id: int | None = None) -> bool:
        """Check if category name exists for user."""
        query = select(Category.id).where(
            Category.user_id == user_id,
            Category.name == name
        )
        if exclude_id:
            query = query.where(Category.id != exclude_id)
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def get_default_category(self, user_id: int) -> Category | None:
        """Get or create default category for user."""
        result = await self.session.execute(
            select(Category)
            .where(Category.user_id == user_id, Category.name == "Default")
        )
        category = result.scalar_one_or_none()
        
        if not category:
            category = await self.create(user_id, "Default", "Default category")
        
        return category

    async def count_feeds(self, category_id: int) -> int:
        """Count feeds in a category."""
        from app.models.feed import Feed
        result = await self.session.execute(
            select(func.count(Feed.id)).where(Feed.category_id == category_id)
        )
        return result.scalar() or 0
