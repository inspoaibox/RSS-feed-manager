"""Keyword subscription service."""
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword_subscription import KeywordSubscription
from app.repositories.keyword_subscription_repository import KeywordSubscriptionRepository
from app.schemas.keyword_subscription import (
    KeywordSubscriptionCreate,
    KeywordSubscriptionResponse,
    KeywordSubscriptionUpdate,
)


class KeywordSubscriptionService:
    """Service for keyword subscription operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = KeywordSubscriptionRepository(session)

    async def get_all(self, user_id: int) -> List[KeywordSubscriptionResponse]:
        """Get all keyword subscriptions for a user."""
        subscriptions = await self.repo.get_all_by_user(user_id)
        counts = await self.repo.get_article_counts(user_id, subscriptions)
        return [
            self._to_response(
                subscription,
                counts.get(subscription.id, {}).get("article_count", 0),
                counts.get(subscription.id, {}).get("unread_count", 0),
            )
            for subscription in subscriptions
        ]

    async def get_by_id(self, user_id: int, keyword_id: int) -> KeywordSubscriptionResponse:
        """Get a keyword subscription by ID."""
        subscription = await self.repo.get_by_id(keyword_id, user_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Keyword subscription not found",
            )

        counts = await self.repo.get_article_counts(user_id, [subscription])
        return self._to_response(
            subscription,
            counts.get(subscription.id, {}).get("article_count", 0),
            counts.get(subscription.id, {}).get("unread_count", 0),
        )

    async def create(
        self,
        user_id: int,
        data: KeywordSubscriptionCreate,
    ) -> KeywordSubscriptionResponse:
        """Create a keyword subscription."""
        keyword = data.keyword.strip()
        name = (data.name or keyword).strip() or keyword

        if await self.repo.exists_by_keyword(user_id, keyword):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Keyword subscription already exists",
            )

        subscription = await self.repo.create(
            user_id=user_id,
            keyword=keyword,
            name=name,
            is_active=data.is_active,
            match_title=data.match_title,
            match_content=data.match_content,
            match_author=data.match_author,
            match_feed_title=data.match_feed_title,
        )
        counts = await self.repo.get_article_counts(user_id, [subscription])
        return self._to_response(
            subscription,
            counts.get(subscription.id, {}).get("article_count", 0),
            counts.get(subscription.id, {}).get("unread_count", 0),
        )

    async def update(
        self,
        user_id: int,
        keyword_id: int,
        data: KeywordSubscriptionUpdate,
    ) -> KeywordSubscriptionResponse:
        """Update a keyword subscription."""
        subscription = await self.repo.get_by_id(keyword_id, user_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Keyword subscription not found",
            )

        update_data = data.model_dump(exclude_unset=True)
        if "keyword" in update_data and update_data["keyword"] is not None:
            update_data["keyword"] = update_data["keyword"].strip()
            if await self.repo.exists_by_keyword(
                user_id,
                update_data["keyword"],
                exclude_id=keyword_id,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Keyword subscription already exists",
                )
        if "name" in update_data and update_data["name"] is not None:
            update_data["name"] = update_data["name"].strip()

        subscription = await self.repo.update(subscription, **update_data)
        counts = await self.repo.get_article_counts(user_id, [subscription])
        return self._to_response(
            subscription,
            counts.get(subscription.id, {}).get("article_count", 0),
            counts.get(subscription.id, {}).get("unread_count", 0),
        )

    async def delete(self, user_id: int, keyword_id: int) -> None:
        """Delete a keyword subscription."""
        subscription = await self.repo.get_by_id(keyword_id, user_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Keyword subscription not found",
            )
        await self.repo.delete(subscription)

    def _to_response(
        self,
        subscription: KeywordSubscription,
        article_count: int = 0,
        unread_count: int = 0,
    ) -> KeywordSubscriptionResponse:
        """Convert a keyword subscription model to response schema."""
        return KeywordSubscriptionResponse(
            id=subscription.id,
            name=subscription.name,
            keyword=subscription.keyword,
            is_active=subscription.is_active,
            match_title=subscription.match_title,
            match_content=subscription.match_content,
            match_author=subscription.match_author,
            match_feed_title=subscription.match_feed_title,
            position=subscription.position,
            article_count=article_count,
            unread_count=unread_count,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )
