"""Category API endpoints."""
from typing import List

from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, DbSession
from app.schemas.category import CategoryCreate, CategoryReorder, CategoryResponse, CategoryUpdate
from app.services.category_service import CategoryService

router = APIRouter()


@router.get("", response_model=List[CategoryResponse])
async def get_categories(user_id: CurrentUserId, db: DbSession):
    """Get all categories for the current user."""
    service = CategoryService(db)
    return await service.get_all(user_id)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, user_id: CurrentUserId, db: DbSession):
    """Create a new category."""
    service = CategoryService(db)
    return await service.create(user_id, data)


@router.put("/reorder", response_model=List[CategoryResponse])
async def reorder_categories(data: CategoryReorder, user_id: CurrentUserId, db: DbSession):
    """Reorder categories by providing category IDs in desired order."""
    service = CategoryService(db)
    return await service.reorder(user_id, data)


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: int, user_id: CurrentUserId, db: DbSession):
    """Get a category by ID."""
    service = CategoryService(db)
    return await service.get_by_id(user_id, category_id)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int, data: CategoryUpdate, user_id: CurrentUserId, db: DbSession
):
    """Update a category."""
    service = CategoryService(db)
    return await service.update(user_id, category_id, data)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, user_id: CurrentUserId, db: DbSession):
    """Delete a category (feeds will be moved to default category)."""
    service = CategoryService(db)
    await service.delete(user_id, category_id)
