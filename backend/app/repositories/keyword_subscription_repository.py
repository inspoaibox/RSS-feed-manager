"""Keyword subscription repository."""
from typing import Iterable, List

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article, UserArticle
from app.models.feed import Feed
from app.models.keyword_subscription import KeywordSubscription


def build_keyword_conditions(keyword: KeywordSubscription) -> list:
    """Build SQLAlchemy conditions for a keyword subscription."""
    keyword_text = (keyword.keyword or "").strip()
    if not keyword_text or not keyword.is_active:
        return []

    pattern = f"%{keyword_text}%"
    conditions = []

    if keyword.match_title:
        conditions.append(Article.title.ilike(pattern))
    if keyword.match_content:
        conditions.extend([
            Article.content.ilike(pattern),
            Article.full_content.ilike(pattern),
            Article.summary.ilike(pattern),
            Article.translation.ilike(pattern),
        ])
    if keyword.match_author:
        conditions.append(Article.author.ilike(pattern))
    if keyword.match_feed_title:
        conditions.append(Feed.title.ilike(pattern))

    return conditions or [Article.title.ilike(pattern)]


class KeywordSubscriptionRepository:
    """Repository for keyword subscription operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        keyword: str,
        name: str,
        is_active: bool = True,
        match_title: bool = True,
        match_content: bool = True,
        match_author: bool = False,
        match_feed_title: bool = True,
    ) -> KeywordSubscription:
        """Create a keyword subscription."""
        result = await self.session.execute(
            select(func.coalesce(func.max(KeywordSubscription.position), -1))
            .where(KeywordSubscription.user_id == user_id)
        )
        max_position = result.scalar() or -1

        subscription = KeywordSubscription(
            user_id=user_id,
            name=name,
            keyword=keyword,
            is_active=is_active,
            match_title=match_title,
            match_content=match_content,
            match_author=match_author,
            match_feed_title=match_feed_title,
            position=max_position + 1,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def get_by_id(self, keyword_id: int, user_id: int) -> KeywordSubscription | None:
        """Get a keyword subscription by ID for a user."""
        result = await self.session.execute(
            select(KeywordSubscription).where(
                KeywordSubscription.id == keyword_id,
                KeywordSubscription.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_by_user(self, user_id: int) -> List[KeywordSubscription]:
        """Get all keyword subscriptions for a user."""
        result = await self.session.execute(
            select(KeywordSubscription)
            .where(KeywordSubscription.user_id == user_id)
            .order_by(KeywordSubscription.position, KeywordSubscription.created_at)
        )
        return list(result.scalars().all())

    async def update(self, subscription: KeywordSubscription, **kwargs) -> KeywordSubscription:
        """Update keyword subscription fields."""
        for key, value in kwargs.items():
            if hasattr(subscription, key) and value is not None:
                setattr(subscription, key, value)
        await self.session.flush()
        return subscription

    async def delete(self, subscription: KeywordSubscription) -> None:
        """Delete a keyword subscription."""
        await self.session.delete(subscription)
        await self.session.flush()

    async def exists_by_keyword(
        self,
        user_id: int,
        keyword: str,
        exclude_id: int | None = None,
    ) -> bool:
        """Check whether a keyword already exists for a user."""
        query = select(KeywordSubscription.id).where(
            KeywordSubscription.user_id == user_id,
            func.lower(KeywordSubscription.keyword) == keyword.lower(),
        )
        if exclude_id:
            query = query.where(KeywordSubscription.id != exclude_id)

        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def get_article_counts(
        self,
        user_id: int,
        subscriptions: Iterable[KeywordSubscription],
    ) -> dict[int, dict[str, int]]:
        """Get total and unread article counts for keyword subscriptions."""
        counts: dict[int, dict[str, int]] = {}

        for subscription in subscriptions:
            conditions = build_keyword_conditions(subscription)
            if not conditions:
                counts[subscription.id] = {"article_count": 0, "unread_count": 0}
                continue

            base_query = (
                select(Article.id)
                .join(Feed, Article.feed_id == Feed.id)
                .where(
                    Feed.user_id == user_id,
                    or_(*conditions),
                )
            )

            total_result = await self.session.execute(
                select(func.count()).select_from(base_query.subquery())
            )
            unread_result = await self.session.execute(
                select(func.count())
                .select_from(Article)
                .join(Feed, Article.feed_id == Feed.id)
                .outerjoin(
                    UserArticle,
                    and_(
                        UserArticle.article_id == Article.id,
                        UserArticle.user_id == user_id,
                    ),
                )
                .where(
                    Feed.user_id == user_id,
                    or_(*conditions),
                    or_(UserArticle.is_read == False, UserArticle.is_read == None),
                )
            )

            counts[subscription.id] = {
                "article_count": total_result.scalar() or 0,
                "unread_count": unread_result.scalar() or 0,
            }

        return counts
