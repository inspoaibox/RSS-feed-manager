"""Article repository for database operations."""
from datetime import datetime
from typing import List, Tuple

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article, UserArticle
from app.models.feed import Feed
from app.models.keyword_subscription import KeywordSubscription
from app.repositories.keyword_subscription_repository import build_keyword_conditions


def build_article_search_conditions(query: str) -> list:
    """Build AND search conditions from whitespace-separated terms."""
    terms = query.strip().split()
    fields = (
        Article.title,
        Article.content,
        Article.full_content,
        Article.summary,
        Article.translation,
        Article.author,
        Feed.title,
    )

    return [
        or_(*(field.ilike(f"%{term}%") for field in fields))
        for term in terms
    ]


class ArticleRepository:
    """Repository for Article database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        feed_id: int,
        guid: str,
        title: str,
        link: str,
        content: str | None = None,
        author: str | None = None,
        published_at: datetime | None = None
    ) -> Article:
        """Create a new article."""
        article = Article(
            feed_id=feed_id,
            guid=guid,
            title=title,
            link=link,
            content=content,
            author=author,
            published_at=published_at or datetime.utcnow()
        )
        self.session.add(article)
        await self.session.flush()
        return article

    async def get_by_id(self, article_id: int) -> Article | None:
        """Get article by ID."""
        result = await self.session.execute(
            select(Article).where(Article.id == article_id)
        )
        return result.scalar_one_or_none()

    async def get_by_guid(self, feed_id: int, guid: str) -> Article | None:
        """Get article by feed ID and GUID."""
        result = await self.session.execute(
            select(Article).where(
                Article.feed_id == feed_id,
                Article.guid == guid
            )
        )
        return result.scalar_one_or_none()

    async def get_articles_paginated(
        self,
        user_id: int,
        feed_id: int | None = None,
        category_id: int | None = None,
        keyword: KeywordSubscription | None = None,
        is_read: bool | None = None,
        is_favorite: bool | None = None,
        sort_by: str = "published_at",
        sort_order: str = "desc",
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[dict], int]:
        """Get paginated articles with user state."""
        # Base query joining articles with feeds
        base_query = (
            select(Article, UserArticle, Feed.title.label('feed_title'))
            .join(Feed, Article.feed_id == Feed.id)
            .outerjoin(
                UserArticle,
                and_(
                    UserArticle.article_id == Article.id,
                    UserArticle.user_id == user_id
                )
            )
            .where(Feed.user_id == user_id)
        )
        
        # Apply filters
        if feed_id is not None:
            base_query = base_query.where(Article.feed_id == feed_id)
        
        if category_id is not None:
            base_query = base_query.where(Feed.category_id == category_id)

        if keyword is not None:
            conditions = build_keyword_conditions(keyword)
            if conditions:
                base_query = base_query.where(or_(*conditions))
            else:
                base_query = base_query.where(False)
        
        if is_read is not None:
            if is_read:
                base_query = base_query.where(UserArticle.is_read == True)
            else:
                base_query = base_query.where(
                    or_(UserArticle.is_read == False, UserArticle.is_read == None)
                )
        
        if is_favorite is not None:
            if is_favorite:
                base_query = base_query.where(UserArticle.is_favorite == True)
            else:
                base_query = base_query.where(
                    or_(UserArticle.is_favorite == False, UserArticle.is_favorite == None)
                )
        
        # Date filter - expects ISO format datetime strings from frontend
        if date_from:
            from datetime import datetime, timezone, timedelta
            from dateutil import parser as date_parser
            try:
                date_start = date_parser.isoparse(date_from)
                # Ensure timezone-aware UTC datetime
                if date_start.tzinfo is None:
                    date_start = date_start.replace(tzinfo=timezone.utc)
                base_query = base_query.where(Article.published_at >= date_start)
            except (ValueError, Exception):
                pass
        
        if date_to:
            from datetime import datetime, timezone, timedelta
            from dateutil import parser as date_parser
            try:
                date_end = date_parser.isoparse(date_to)
                # Ensure timezone-aware UTC datetime
                if date_end.tzinfo is None:
                    date_end = date_end.replace(tzinfo=timezone.utc)
                # Add 1 second to include the end time (23:59:59 -> 24:00:00)
                date_end = date_end + timedelta(seconds=1)
                base_query = base_query.where(Article.published_at < date_end)
            except (ValueError, Exception):
                pass
        
        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply sorting
        sort_column = getattr(Article, sort_by, Article.published_at)
        if sort_order == "asc":
            order_clause = sort_column.asc()
        else:
            order_clause = sort_column.desc()
        
        # Get paginated results
        query = (
            base_query
            .order_by(order_clause)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        articles = []
        for article, user_article, feed_title in rows:
            articles.append({
                "article": article,
                "feed_title": feed_title,
                "is_read": user_article.is_read if user_article else False,
                "is_favorite": user_article.is_favorite if user_article else False,
                "read_at": user_article.read_at if user_article else None
            })
        
        return articles, total

    async def search(
        self,
        user_id: int,
        query: str,
        feed_id: int | None = None,
        category_id: int | None = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[dict], int]:
        """Search articles by title and content."""
        search_conditions = build_article_search_conditions(query)
        
        base_query = (
            select(Article, UserArticle, Feed.title.label('feed_title'))
            .join(Feed, Article.feed_id == Feed.id)
            .outerjoin(
                UserArticle,
                and_(
                    UserArticle.article_id == Article.id,
                    UserArticle.user_id == user_id
                )
            )
            .where(
                Feed.user_id == user_id,
                and_(*search_conditions) if search_conditions else False
            )
        )
        
        if feed_id is not None:
            base_query = base_query.where(Article.feed_id == feed_id)
        
        if category_id is not None:
            base_query = base_query.where(Feed.category_id == category_id)
        
        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated results
        query_stmt = (
            base_query
            .order_by(Article.published_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = await self.session.execute(query_stmt)
        rows = result.all()
        
        articles = []
        for article, user_article, feed_title in rows:
            articles.append({
                "article": article,
                "feed_title": feed_title,
                "is_read": user_article.is_read if user_article else False,
                "is_favorite": user_article.is_favorite if user_article else False
            })
        
        return articles, total

    async def get_user_article(self, user_id: int, article_id: int) -> UserArticle | None:
        """Get user article state."""
        result = await self.session.execute(
            select(UserArticle).where(
                UserArticle.user_id == user_id,
                UserArticle.article_id == article_id
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_user_article(self, user_id: int, article_id: int) -> UserArticle:
        """Get or create user article state."""
        user_article = await self.get_user_article(user_id, article_id)
        if not user_article:
            user_article = UserArticle(user_id=user_id, article_id=article_id)
            self.session.add(user_article)
            await self.session.flush()
        return user_article

    async def mark_read(self, user_id: int, article_id: int) -> None:
        """Mark article as read."""
        user_article = await self.get_or_create_user_article(user_id, article_id)
        user_article.is_read = True
        user_article.read_at = datetime.utcnow()
        await self.session.flush()

    async def mark_unread(self, user_id: int, article_id: int) -> None:
        """Mark article as unread."""
        user_article = await self.get_or_create_user_article(user_id, article_id)
        user_article.is_read = False
        user_article.read_at = None
        await self.session.flush()

    async def toggle_favorite(self, user_id: int, article_id: int) -> bool:
        """Toggle article favorite status. Returns new status."""
        user_article = await self.get_or_create_user_article(user_id, article_id)
        user_article.is_favorite = not user_article.is_favorite
        user_article.favorited_at = datetime.utcnow() if user_article.is_favorite else None
        await self.session.flush()
        return user_article.is_favorite

    async def mark_all_read_by_feed(self, user_id: int, feed_id: int) -> int:
        """Mark all articles in a feed as read."""
        # Get all article IDs for the feed
        article_ids_result = await self.session.execute(
            select(Article.id).where(Article.feed_id == feed_id)
        )
        article_ids = [row[0] for row in article_ids_result.all()]
        
        if not article_ids:
            return 0
        
        count = 0
        for article_id in article_ids:
            user_article = await self.get_or_create_user_article(user_id, article_id)
            if not user_article.is_read:
                user_article.is_read = True
                user_article.read_at = datetime.utcnow()
                count += 1
        
        await self.session.flush()
        return count

    async def mark_all_read_by_category(self, user_id: int, category_id: int) -> int:
        """Mark all articles in a category as read."""
        # Get all article IDs for feeds in the category
        article_ids_result = await self.session.execute(
            select(Article.id)
            .join(Feed, Article.feed_id == Feed.id)
            .where(Feed.category_id == category_id, Feed.user_id == user_id)
        )
        article_ids = [row[0] for row in article_ids_result.all()]
        
        if not article_ids:
            return 0
        
        count = 0
        for article_id in article_ids:
            user_article = await self.get_or_create_user_article(user_id, article_id)
            if not user_article.is_read:
                user_article.is_read = True
                user_article.read_at = datetime.utcnow()
                count += 1
        
        await self.session.flush()
        return count

    async def mark_all_read_by_keyword(
        self,
        user_id: int,
        keyword: KeywordSubscription
    ) -> int:
        """Mark all articles matching a keyword subscription as read."""
        conditions = build_keyword_conditions(keyword)
        if not conditions:
            return 0

        article_ids_result = await self.session.execute(
            select(Article.id)
            .join(Feed, Article.feed_id == Feed.id)
            .where(Feed.user_id == user_id, or_(*conditions))
        )
        article_ids = [row[0] for row in article_ids_result.all()]

        if not article_ids:
            return 0

        count = 0
        for article_id in article_ids:
            user_article = await self.get_or_create_user_article(user_id, article_id)
            if not user_article.is_read:
                user_article.is_read = True
                user_article.read_at = datetime.utcnow()
                count += 1

        await self.session.flush()
        return count

    async def count_unread_by_feed(self, user_id: int, feed_id: int) -> int:
        """Count unread articles in a feed."""
        result = await self.session.execute(
            select(func.count(Article.id))
            .outerjoin(
                UserArticle,
                and_(
                    UserArticle.article_id == Article.id,
                    UserArticle.user_id == user_id
                )
            )
            .where(
                Article.feed_id == feed_id,
                or_(UserArticle.is_read == False, UserArticle.is_read == None)
            )
        )
        return result.scalar() or 0

    async def update_content(
        self,
        article: Article,
        full_content: str | None = None,
        summary: str | None = None,
        translation: str | None = None
    ) -> Article:
        """Update article content fields."""
        if full_content is not None:
            article.full_content = full_content
        if summary is not None:
            article.summary = summary
        if translation is not None:
            article.translation = translation
        await self.session.flush()
        return article

    async def update_embedding(
        self,
        article_id: int,
        embedding: list[float] | None
    ) -> bool:
        """
        Update article embedding.
        
        Args:
            article_id: The article ID
            embedding: The embedding vector
            
        Returns:
            True if updated, False if article not found
        """
        article = await self.get_by_id(article_id)
        if not article:
            return False
        
        article.embedding = embedding
        await self.session.flush()
        return True

    async def get_articles_without_embedding(
        self,
        user_id: int,
        limit: int = 100
    ) -> List[Article]:
        """
        Get articles without embedding for a user.
        
        Args:
            user_id: The user ID
            limit: Maximum number of articles to return
            
        Returns:
            List of articles without embedding
        """
        result = await self.session.execute(
            select(Article)
            .join(Feed, Article.feed_id == Feed.id)
            .where(
                Feed.user_id == user_id,
                Article.embedding == None
            )
            .order_by(Article.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
