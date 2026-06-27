"""Keyword subscription repository."""
from datetime import datetime
from typing import Iterable, List

from sqlalchemy import and_, case, delete, func, insert, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article, UserArticle
from app.models.feed import Feed
from app.models.keyword_article_match import KeywordArticleMatch
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
        await self.session.refresh(subscription)
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

    async def rebuild_article_matches(
        self,
        user_id: int,
        subscription: KeywordSubscription,
    ) -> None:
        """Rebuild persisted article matches for one keyword subscription."""
        await self.session.execute(
            delete(KeywordArticleMatch).where(
                KeywordArticleMatch.keyword_subscription_id == subscription.id
            )
        )

        conditions = build_keyword_conditions(subscription)
        source_conditions = build_keyword_source_conditions(subscription)
        if conditions:
            await self.session.execute(
                insert(KeywordArticleMatch).from_select(
                    ["keyword_subscription_id", "article_id"],
                    select(literal(subscription.id), Article.id)
                    .join(Feed, Article.feed_id == Feed.id)
                    .where(
                        Feed.user_id == user_id,
                        or_(*conditions),
                        *source_conditions,
                    ),
                )
            )

        subscription.matches_built_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(subscription)

    async def ensure_article_matches(
        self,
        user_id: int,
        subscriptions: Iterable[KeywordSubscription],
    ) -> None:
        """Build keyword article matches for subscriptions that have not been backfilled."""
        for subscription in subscriptions:
            if getattr(subscription, "matches_built_at", None) is None:
                await self.rebuild_article_matches(user_id, subscription)

    async def sync_article_matches(
        self,
        user_id: int,
        article_ids: Iterable[int],
    ) -> None:
        """Refresh keyword matches for newly inserted or content-updated articles."""
        unique_article_ids = list(dict.fromkeys(article_id for article_id in article_ids if article_id))
        if not unique_article_ids:
            return

        subscriptions = await self.get_all_by_user(user_id)
        subscription_ids = [subscription.id for subscription in subscriptions]
        if not subscription_ids:
            return

        await self.session.execute(
            delete(KeywordArticleMatch).where(
                KeywordArticleMatch.article_id.in_(unique_article_ids),
                KeywordArticleMatch.keyword_subscription_id.in_(subscription_ids),
            )
        )

        for subscription in subscriptions:
            conditions = build_keyword_conditions(subscription)
            source_conditions = build_keyword_source_conditions(subscription)
            if not conditions:
                continue

            await self.session.execute(
                insert(KeywordArticleMatch).from_select(
                    ["keyword_subscription_id", "article_id"],
                    select(literal(subscription.id), Article.id)
                    .join(Feed, Article.feed_id == Feed.id)
                    .where(
                        Feed.user_id == user_id,
                        Article.id.in_(unique_article_ids),
                        or_(*conditions),
                        *source_conditions,
                    ),
                )
            )

        await self.session.flush()

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

        await self.ensure_article_matches(user_id, sub_list)

        subscription_ids = [subscription.id for subscription in sub_list]
        for subscription_id in subscription_ids:
            counts[subscription_id] = {"article_count": 0, "unread_count": 0}

        unread_condition = or_(UserArticle.is_read == False, UserArticle.is_read == None)
        result = await self.session.execute(
            select(
                KeywordArticleMatch.keyword_subscription_id,
                func.count(Article.id).label("article_count"),
                func.coalesce(
                    func.sum(case((unread_condition, 1), else_=0)),
                    0,
                ).label("unread_count"),
            )
            .select_from(KeywordArticleMatch)
            .join(Article, KeywordArticleMatch.article_id == Article.id)
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
                KeywordArticleMatch.keyword_subscription_id.in_(subscription_ids),
            )
            .group_by(KeywordArticleMatch.keyword_subscription_id)
        )
        for row in result.all():
            counts[row.keyword_subscription_id] = {
                "article_count": int(row.article_count or 0),
                "unread_count": int(row.unread_count or 0),
            }

        return counts
