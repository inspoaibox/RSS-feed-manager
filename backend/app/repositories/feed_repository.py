"""Feed repository for database operations."""
from datetime import datetime
from typing import List

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.article import Article, UserArticle
from app.models.feed import Feed


class FeedRepository:
    """Repository for Feed database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        url: str,
        title: str,
        description: str | None = None,
        site_url: str | None = None,
        icon_url: str | None = None,
        category_id: int | None = None,
        fetch_interval: int = 3600,
        use_playwright: bool = False,
        auto_translate: bool = False,
        auto_summarize: bool = False,
        target_language: str | None = None
    ) -> Feed:
        """Create a new feed."""
        # Get max position
        result = await self.session.execute(
            select(func.coalesce(func.max(Feed.position), -1))
            .where(Feed.user_id == user_id)
        )
        max_position = result.scalar() or -1
        
        feed = Feed(
            user_id=user_id,
            url=url,
            title=title,
            description=description,
            site_url=site_url,
            icon_url=icon_url,
            category_id=category_id,
            fetch_interval=fetch_interval,
            use_playwright=use_playwright,
            auto_translate=auto_translate,
            auto_summarize=auto_summarize,
            target_language=target_language,
            position=max_position + 1
        )
        self.session.add(feed)
        await self.session.flush()
        return feed

    async def get_by_id(self, feed_id: int, user_id: int) -> Feed | None:
        """Get feed by ID for a specific user."""
        result = await self.session.execute(
            select(Feed).where(Feed.id == feed_id, Feed.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all_by_user(self, user_id: int) -> List[Feed]:
        """Get all feeds for a user."""
        result = await self.session.execute(
            select(Feed)
            .where(Feed.user_id == user_id)
            .order_by(Feed.position)
        )
        return list(result.scalars().all())

    async def get_by_category(self, user_id: int, category_id: int) -> List[Feed]:
        """Get feeds by category."""
        result = await self.session.execute(
            select(Feed)
            .where(Feed.user_id == user_id, Feed.category_id == category_id)
            .order_by(Feed.position)
        )
        return list(result.scalars().all())

    async def get_with_articles(self, feed_id: int, user_id: int) -> Feed | None:
        """Get feed with articles loaded."""
        result = await self.session.execute(
            select(Feed)
            .options(selectinload(Feed.articles))
            .where(Feed.id == feed_id, Feed.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_active_feeds(self) -> List[Feed]:
        """Get all active feeds for refresh."""
        result = await self.session.execute(
            select(Feed).where(Feed.is_active == True)
        )
        return list(result.scalars().all())

    async def get_feeds_due_for_refresh(self) -> List[Feed]:
        """Get feeds that are due for refresh based on fetch_interval."""
        now = datetime.utcnow()
        result = await self.session.execute(
            select(Feed).where(
                Feed.is_active == True,
                (Feed.last_fetched_at == None) | 
                (func.extract('epoch', now - Feed.last_fetched_at) >= Feed.fetch_interval)
            )
        )
        return list(result.scalars().all())

    async def update(self, feed: Feed, **kwargs) -> Feed:
        """Update feed fields."""
        for key, value in kwargs.items():
            if hasattr(feed, key) and value is not None:
                setattr(feed, key, value)
        await self.session.flush()
        return feed

    async def update_fetch_status(
        self,
        feed: Feed,
        success: bool,
        error: str | None = None
    ) -> Feed:
        """Update feed fetch status."""
        feed.last_fetched_at = datetime.utcnow()
        if success:
            feed.last_error = None
            feed.error_count = 0
        else:
            feed.last_error = error
            feed.error_count += 1
        await self.session.flush()
        return feed

    async def delete(self, feed: Feed) -> None:
        """Delete a feed."""
        await self.session.delete(feed)
        await self.session.flush()

    async def exists_by_url(self, user_id: int, url: str, exclude_id: int | None = None) -> bool:
        """Check if feed URL exists for user."""
        query = select(Feed.id).where(Feed.user_id == user_id, Feed.url == url)
        if exclude_id:
            query = query.where(Feed.id != exclude_id)
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def count_by_user(self, user_id: int) -> int:
        """Count feeds for a user."""
        result = await self.session.execute(
            select(func.count(Feed.id)).where(Feed.user_id == user_id)
        )
        return result.scalar() or 0

    async def get_article_counts(self, user_id: int, feed_ids: List[int]) -> dict[int, dict]:
        """Get article counts and unread counts for feeds."""
        if not feed_ids:
            return {}
        
        # Get total article counts
        article_counts_result = await self.session.execute(
            select(Article.feed_id, func.count(Article.id))
            .where(Article.feed_id.in_(feed_ids))
            .group_by(Article.feed_id)
        )
        article_counts = {row[0]: row[1] for row in article_counts_result.all()}
        
        # Get unread counts (articles without UserArticle or with is_read=False)
        from sqlalchemy import and_, or_
        unread_counts_result = await self.session.execute(
            select(Article.feed_id, func.count(Article.id))
            .outerjoin(
                UserArticle,
                and_(
                    UserArticle.article_id == Article.id,
                    UserArticle.user_id == user_id
                )
            )
            .where(
                Article.feed_id.in_(feed_ids),
                or_(UserArticle.is_read == False, UserArticle.is_read == None)
            )
            .group_by(Article.feed_id)
        )
        unread_counts = {row[0]: row[1] for row in unread_counts_result.all()}
        
        result = {}
        for feed_id in feed_ids:
            result[feed_id] = {
                'article_count': article_counts.get(feed_id, 0),
                'unread_count': unread_counts.get(feed_id, 0)
            }
        return result
