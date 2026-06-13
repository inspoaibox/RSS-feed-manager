"""Article service for business logic."""
import math
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.repositories.article_repository import ArticleRepository
from app.repositories.feed_repository import FeedRepository
from app.repositories.keyword_subscription_repository import KeywordSubscriptionRepository
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
        self.keyword_repo = KeywordSubscriptionRepository(session)

    async def get_articles(
        self, user_id: int, filters: ArticleFilter
    ) -> ArticleListResponse:
        """Get paginated articles with filters."""
        keyword = None
        if filters.keyword_id is not None:
            keyword = await self.keyword_repo.get_by_id(filters.keyword_id, user_id)
            if not keyword:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Keyword subscription not found"
                )

        articles_data, total = await self.repo.get_articles_paginated(
            user_id=user_id,
            feed_id=filters.feed_id,
            category_id=filters.category_id,
            keyword=keyword,
            is_read=filters.is_read,
            is_favorite=filters.is_favorite,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
            date_from=filters.date_from,
            date_to=filters.date_to,
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
        category_id: int | None = None,
        keyword_id: int | None = None
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
        elif keyword_id:
            keyword = await self.keyword_repo.get_by_id(keyword_id, user_id)
            if not keyword:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Keyword subscription not found"
                )
            return await self.repo.mark_all_read_by_keyword(user_id, keyword)
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
            feed_title=data.get("feed_title"),
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

    def _extract_text_from_html(self, html_content: str) -> str:
        """Extract plain text from HTML content, preserving paragraph structure."""
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove script and style elements
        for tag in soup(["script", "style"]):
            tag.decompose()
        
        # Add newlines for block elements to preserve structure
        for br in soup.find_all("br"):
            br.replace_with("\n")
        for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"]):
            tag.insert_before("\n")
            tag.insert_after("\n")
        
        text = soup.get_text()
        # Clean up multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    async def translate_article(self, user_id: int, article_id: int, target_language: str) -> dict:
        """Translate article title and content using AI or Google Translate based on feed settings."""
        import json
        
        article = await self._verify_article_access(user_id, article_id)
        
        content = article.content or ""
        title = article.title or ""
        
        if not content and not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Article has no content to translate"
            )
        
        # Keep HTML content for translation (let AI preserve formatting)
        content_text = content
        
        # Get feed's translate_method
        from app.models.feed import Feed
        from sqlalchemy import select
        feed_result = await self.session.execute(select(Feed).where(Feed.id == article.feed_id))
        feed = feed_result.scalar_one_or_none()
        translate_method = getattr(feed, 'translate_method', 'none') if feed else 'none'
        
        # Check if translation is enabled
        if translate_method == 'none':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请先在订阅源设置中启用 Google 翻译或 AI 翻译"
            )
        
        # Get user info
        from app.models.user import User
        user_result = await self.session.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        translated_title = ""
        translated_content = ""
        
        if translate_method == 'google':
            # Use Google Translate
            print(f"[Translate] Using Google Translate for article {article_id}")
            from app.services.google_translate_key_service import GoogleTranslateKeyService
            from app.services.google_translate_service import GoogleTranslateError
            
            try:
                translated_title, translated_content = await GoogleTranslateKeyService(
                    self.session
                ).translate_article(
                    user_id,
                    title,
                    content_text,
                    target_language,
                )
            except GoogleTranslateError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Google translation failed: {str(e)}"
                )
        else:
            # Use AI translation (default)
            print(f"[Translate] Using AI Translate for article {article_id}")
            from app.repositories.ai_repository import AIModelRepository, AIProviderRepository
            model_repo = AIModelRepository(self.session)
            provider_repo = AIProviderRepository(self.session)
            default_model = await model_repo.get_default_model(user_id)
            
            if not default_model:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No default AI model configured"
                )
            
            provider = await provider_repo.get_by_id(default_model.provider_id, user_id)
            if not provider:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AI provider not found"
                )
            
            custom_prompt = user.translate_prompt if user and user.translate_prompt else None
            
            from app.services.ai_client import create_ai_client, AIClientError
            try:
                client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
                
                if title:
                    translated_title = await client.translate(title, target_language, custom_prompt)
                if content_text:
                    translated_content = await client.translate(content_text, target_language, custom_prompt)
            except AIClientError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"AI translation failed: {str(e)}"
                )
        
        # Store as JSON
        translation_data = json.dumps({
            "title": translated_title,
            "content": translated_content
        }, ensure_ascii=False)
        
        article.translation = translation_data
        await self.session.commit()
        
        return {"translation": translation_data, "title": translated_title, "content": translated_content, "method": translate_method}

    async def summarize_article(self, user_id: int, article_id: int) -> dict:
        """Summarize article using AI."""
        article = await self._verify_article_access(user_id, article_id)
        
        content = article.content or article.title
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Article has no content to summarize"
            )
        
        # Extract plain text from HTML
        content = self._extract_text_from_html(content)
        
        # Get default AI model
        from app.repositories.ai_repository import AIModelRepository, AIProviderRepository
        model_repo = AIModelRepository(self.session)
        provider_repo = AIProviderRepository(self.session)
        default_model = await model_repo.get_default_model(user_id)
        
        if not default_model:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No default AI model configured"
            )
        
        provider = await provider_repo.get_by_id(default_model.provider_id, user_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI provider not found"
            )
        
        # Get user's custom prompt
        from app.models.user import User
        from sqlalchemy import select
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        custom_prompt = user.summarize_prompt if user and user.summarize_prompt else None
        
        from app.services.ai_client import create_ai_client, AIClientError
        try:
            client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
            summary = await client.summarize(content, custom_prompt)
            
            # Save summary
            article.summary = summary
            await self.session.commit()
            
            return {"summary": summary}
        except AIClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI summarization failed: {str(e)}"
            )
