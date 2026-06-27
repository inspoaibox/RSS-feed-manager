"""Keyword subscription repository."""
from typing import Iterable, List

from sqlalchemy import and_, case, func, or_, select
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
    is_numeric_keyword = keyword_text.isdigit()
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
    if keyword.match_feed_title and not is_numeric_keyword:
        conditions.append(Feed.title.ilike(pattern))

    return conditions or [Article.title.ilike(pattern)]


def build_keyword_source_conditions(keyword: KeywordSubscription) -> list:
    """Build source-scope conditions for a keyword subscription."""
    excluded_feed_ids = list(getattr(keyword, "excluded_feed_ids", None) or [])
    excluded_category_ids = list(getattr(keyword, "excluded_category_ids", None) or [])
    conditions = []

    if excluded_feed_ids:
        conditions.append(~Article.feed_id.in_(excluded_feed_ids))
    if excluded_category_ids:
        conditions.append(
            or_(Feed.category_id.is_(None), ~Feed.category_id.in_(excluded_category_ids))
        )

    return conditions


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
        match_feed_title: bool = False,
        excluded_category_ids: list[int] | None = None,
        excluded_feed_ids: list[int] | None = None,
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
            excluded_category_ids=list(excluded_category_ids or []),
            excluded_feed_ids=list(excluded_feed_ids or []),
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
        sub_list = list(subscriptions)

        if not sub_list:
            return counts

        aggregate_columns = []
        active_subscription_ids: list[int] = []
        unread_condition = or_(UserArticle.is_read == False, UserArticle.is_read == None)

        for subscription in sub_list:
            conditions = build_keyword_conditions(subscription)
            source_conditions = build_keyword_source_conditions(subscription)
            counts[subscription.id] = {"article_count": 0, "unread_count": 0}
            if not conditions:
                continue

            match_condition = or_(*conditions)
            if source_conditions:
                match_condition = and_(match_condition, *source_conditions)

            aggregate_columns.extend(
                [
                    func.coalesce(
                        func.sum(case((match_condition, 1), else_=0)),
                        0,
                    ).label(f"article_count_{subscription.id}"),
                    func.coalesce(
                        func.sum(
                            case((and_(match_condition, unread_condition), 1), else_=0)
                        ),
                        0,
                    ).label(f"unread_count_{subscription.id}"),
                ]
            )
            active_subscription_ids.append(subscription.id)

        if not aggregate_columns:
            return counts

        result = await self.session.execute(
            select(*aggregate_columns)
            .select_from(Article)
            .join(Feed, Article.feed_id == Feed.id)
            .outerjoin(
                UserArticle,
                and_(
                    UserArticle.article_id == Article.id,
                    UserArticle.user_id == user_id,
                ),
            )
            .where(Feed.user_id == user_id)
        )
        row = result.one_or_none()
        if not row:
            return counts

        mapping = row._mapping
        for subscription_id in active_subscription_ids:
            counts[subscription_id] = {
                "article_count": int(mapping[f"article_count_{subscription_id}"] or 0),
                "unread_count": int(mapping[f"unread_count_{subscription_id}"] or 0),
            }

        return counts
