"""Keyword subscription service."""
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword_subscription import KeywordSubscription
from app.repositories.category_repository import CategoryRepository
from app.repositories.feed_repository import FeedRepository
from app.repositories.keyword_subscription_repository import KeywordSubscriptionRepository
from app.schemas.keyword_subscription import (
    KeywordSubscriptionCountResponse,
    KeywordSubscriptionCreate,
    KeywordSubscriptionResponse,
    KeywordSubscriptionUpdate,
)


class KeywordSubscriptionService:
    """Service for keyword subscription operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = KeywordSubscriptionRepository(session)
        self.category_repo = CategoryRepository(session)
        self.feed_repo = FeedRepository(session)

    async def get_all(
        self,
        user_id: int,
        include_counts: bool = True,
    ) -> List[KeywordSubscriptionResponse]:
        """Get all keyword subscriptions for a user."""
        subscriptions = await self.repo.get_all_by_user(user_id)
        counts = await self.repo.get_article_counts(user_id, subscriptions) if include_counts else {}
        return [
            self._to_response(
                subscription,
                counts.get(subscription.id, {}).get("article_count", 0),
                counts.get(subscription.id, {}).get("unread_count", 0),
            )
            for subscription in subscriptions
        ]

    async def get_counts(self, user_id: int) -> List[KeywordSubscriptionCountResponse]:
        """Get article counts for all keyword subscriptions."""
        subscriptions = await self.repo.get_all_by_user(user_id)
        counts = await self.repo.get_article_counts(user_id, subscriptions)
        return [
            KeywordSubscriptionCountResponse(
                id=subscription.id,
                article_count=counts.get(subscription.id, {}).get("article_count", 0),
                unread_count=counts.get(subscription.id, {}).get("unread_count", 0),
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

        excluded_category_ids, excluded_feed_ids = await self._validate_source_filters(
            user_id,
            data.excluded_category_ids,
            data.excluded_feed_ids,
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
            excluded_category_ids=excluded_category_ids,
            excluded_feed_ids=excluded_feed_ids,
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
        if "excluded_category_ids" in update_data or "excluded_feed_ids" in update_data:
            excluded_category_ids, excluded_feed_ids = await self._validate_source_filters(
                user_id,
                update_data.get(
                    "excluded_category_ids",
                    getattr(subscription, "excluded_category_ids", []) or [],
                ),
                update_data.get(
                    "excluded_feed_ids",
                    getattr(subscription, "excluded_feed_ids", []) or [],
                ),
            )
            update_data["excluded_category_ids"] = excluded_category_ids
            update_data["excluded_feed_ids"] = excluded_feed_ids

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
            excluded_category_ids=list(getattr(subscription, "excluded_category_ids", []) or []),
            excluded_feed_ids=list(getattr(subscription, "excluded_feed_ids", []) or []),
            position=subscription.position,
            article_count=article_count,
            unread_count=unread_count,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )

    def _normalize_id_list(self, values: list[int] | None) -> list[int]:
        """Normalize ID lists by removing duplicates while preserving order."""
        normalized: list[int] = []
        seen: set[int] = set()
        for raw_value in values or []:
            value = int(raw_value)
            if value <= 0 or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    async def _validate_source_filters(
        self,
        user_id: int,
        excluded_category_ids: list[int] | None,
        excluded_feed_ids: list[int] | None,
    ) -> tuple[list[int], list[int]]:
        """Validate that excluded categories and feeds belong to the user."""
        normalized_category_ids = self._normalize_id_list(excluded_category_ids)
        normalized_feed_ids = self._normalize_id_list(excluded_feed_ids)

        if normalized_category_ids:
            categories = await self.category_repo.get_all_by_user(user_id)
            allowed_category_ids = {category.id for category in categories}
            invalid_category_ids = [
                category_id
                for category_id in normalized_category_ids
                if category_id not in allowed_category_ids
            ]
            if invalid_category_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="来源筛选包含无效的分类",
                )

        if normalized_feed_ids:
            feeds = await self.feed_repo.get_all_by_user(user_id)
            allowed_feed_ids = {feed.id for feed in feeds}
            invalid_feed_ids = [
                feed_id for feed_id in normalized_feed_ids if feed_id not in allowed_feed_ids
            ]
            if invalid_feed_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="来源筛选包含无效的订阅源",
                )

        return normalized_category_ids, normalized_feed_ids
