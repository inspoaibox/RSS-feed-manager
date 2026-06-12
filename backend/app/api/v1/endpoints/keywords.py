"""Keyword subscription API endpoints."""
from typing import List

from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, DbSession
from app.schemas.keyword_subscription import (
    KeywordSubscriptionCountResponse,
    KeywordSubscriptionCreate,
    KeywordSubscriptionResponse,
    KeywordSubscriptionUpdate,
)
from app.services.keyword_subscription_service import KeywordSubscriptionService

router = APIRouter()


@router.get("", response_model=List[KeywordSubscriptionResponse])
async def get_keyword_subscriptions(
    user_id: CurrentUserId,
    db: DbSession,
    include_counts: bool = True,
):
    """Get all keyword subscriptions for the current user."""
    service = KeywordSubscriptionService(db)
    return await service.get_all(user_id, include_counts=include_counts)


@router.post("", response_model=KeywordSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword_subscription(
    data: KeywordSubscriptionCreate,
    user_id: CurrentUserId,
    db: DbSession,
):
    """Create a keyword subscription."""
    service = KeywordSubscriptionService(db)
    return await service.create(user_id, data)


@router.get("/counts", response_model=List[KeywordSubscriptionCountResponse])
async def get_keyword_subscription_counts(user_id: CurrentUserId, db: DbSession):
    """Get article counts for keyword subscriptions."""
    service = KeywordSubscriptionService(db)
    return await service.get_counts(user_id)


@router.get("/{keyword_id}", response_model=KeywordSubscriptionResponse)
async def get_keyword_subscription(keyword_id: int, user_id: CurrentUserId, db: DbSession):
    """Get a keyword subscription by ID."""
    service = KeywordSubscriptionService(db)
    return await service.get_by_id(user_id, keyword_id)


@router.put("/{keyword_id}", response_model=KeywordSubscriptionResponse)
async def update_keyword_subscription(
    keyword_id: int,
    data: KeywordSubscriptionUpdate,
    user_id: CurrentUserId,
    db: DbSession,
):
    """Update a keyword subscription."""
    service = KeywordSubscriptionService(db)
    return await service.update(user_id, keyword_id, data)


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword_subscription(keyword_id: int, user_id: CurrentUserId, db: DbSession):
    """Delete a keyword subscription."""
    service = KeywordSubscriptionService(db)
    await service.delete(user_id, keyword_id)
