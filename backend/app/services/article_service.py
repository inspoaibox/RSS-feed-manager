"""Article service for business logic."""
import math
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.repositories.article_repository import ArticleRepository
from app.repositories.feed_repository import FeedRepository
from app.schemas.article import (
    ArticleFilter,
    ArticleListResponse,
    ArticleResponse,
    ArticleSearchRequest,
)


class ArticleService:
    """Service for article operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ArticleRepository(session)
        self.feed_repo = FeedRepository(session)

    async def get_articles(
        self, user_id: int, filters: ArticleFilter
    ) -> ArticleListResponse:
        """Get paginated articles with filters."""
        articles_data, total = await self.repo.get_articles_paginated(
            user_id=user_id,
            feed_id=filters.feed_id,
            category_id=filters.category_id,
            is_read=filters.is_read,
            is_favorite=filters.is_favorite,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
            page=filters.page,
            page_size=filters.page_size
        )
        
        items = [self._to_response(data) for data in articles_data]
        total_pages = math.ceil(total / filters.page_size) if total > 0 else 1
        
        return ArticleListResponse(
            items=items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages
        )

    async def get_by_id(self, user_id: int, article_id: int) -> ArticleResponse:
        """Get article by ID and mark as read."""
        article = await self.repo.get_by_id(article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        # Verify user owns the feed
        feed = await self.feed_repo.get_by_id(article.feed_id, user_id)
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        # Mark as read
        await self.repo.mark_read(user_id, article_id)
        
        user_article = await self.repo.get_user_article(user_id, article_id)
        
        return ArticleResponse(
            id=article.id,
            feed_id=article.feed_id,
            title=article.title,
            link=article.link,
            content=article.content,
            full_content=article.full_content,
            summary=article.summary,
            translation=article.translation,
            author=article.author,
            published_at=article.published_at,
            is_read=user_article.is_read if user_article else True,
            is_favorite=user_article.is_favorite if user_article else False,
            read_at=user_article.read_at if user_article else None
        )

    async def mark_read(self, user_id: int, article_id: int) -> None:
        """Mark article as read."""
        article = await self._verify_article_access(user_id, article_id)
        await self.repo.mark_read(user_id, article_id)

    async def mark_unread(self, user_id: int, article_id: int) -> None:
        """Mark article as unread."""
        article = await self._verify_article_access(user_id, article_id)
        await self.repo.mark_unread(user_id, article_id)

    async def toggle_favorite(self, user_id: int, article_id: int) -> bool:
        """Toggle article favorite status."""
        article = await self._verify_article_access(user_id, article_id)
        return await self.repo.toggle_favorite(user_id, article_id)

    async def mark_all_read(
        self,
        user_id: int,
        feed_id: int | None = None,
        category_id: int | None = None
    ) -> int:
        """Mark all articles as read."""
        if feed_id:
            # Verify feed access
            feed = await self.feed_repo.get_by_id(feed_id, user_id)
            if not feed:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Feed not found"
                )
            return await self.repo.mark_all_read_by_feed(user_id, feed_id)
        elif category_id:
            return await self.repo.mark_all_read_by_category(user_id, category_id)
        else:
            # Mark all user's articles as read
            feeds = await self.feed_repo.get_all_by_user(user_id)
            count = 0
            for feed in feeds:
                count += await self.repo.mark_all_read_by_feed(user_id, feed.id)
            return count

    async def search(
        self, user_id: int, request: ArticleSearchRequest
    ) -> ArticleListResponse:
        """Search articles."""
        articles_data, total = await self.repo.search(
            user_id=user_id,
            query=request.query,
            feed_id=request.feed_id,
            category_id=request.category_id,
            page=request.page,
            page_size=request.page_size
        )
        
        items = [self._to_response(data) for data in articles_data]
        total_pages = math.ceil(total / request.page_size) if total > 0 else 1
        
        return ArticleListResponse(
            items=items,
            total=total,
            page=request.page,
            page_size=request.page_size,
            total_pages=total_pages
        )

    async def _verify_article_access(self, user_id: int, article_id: int) -> Article:
        """Verify user has access to article."""
        article = await self.repo.get_by_id(article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        feed = await self.feed_repo.get_by_id(article.feed_id, user_id)
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        return article

    def _to_response(self, data: dict) -> ArticleResponse:
        """Convert article data to response."""
        article = data["article"]
        return ArticleResponse(
            id=article.id,
            feed_id=article.feed_id,
            title=article.title,
            link=article.link,
            content=article.content,
            full_content=article.full_content,
            summary=article.summary,
            translation=article.translation,
            author=article.author,
            published_at=article.published_at,
            is_read=data.get("is_read", False),
            is_favorite=data.get("is_favorite", False),
            read_at=data.get("read_at")
        )
