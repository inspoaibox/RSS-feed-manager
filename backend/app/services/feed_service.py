"""Feed service for business logic."""
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feed import Feed
from app.repositories.article_repository import ArticleRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.feed_repository import FeedRepository
from app.schemas.feed import FeedCreate, FeedReorder, FeedResponse, FeedUpdate, OPMLImportResult
from app.utils.feed_parser import FeedParserError, ParsedFeed, parse_feed
from app.utils.opml import OPMLFeed, OPMLParseError, generate_opml, parse_opml


class FeedService:
    """Service for feed operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FeedRepository(session)
        self.category_repo = CategoryRepository(session)
        self.article_repo = ArticleRepository(session)

    async def create(self, user_id: int, data: FeedCreate) -> FeedResponse:
        """Create a new feed by parsing the URL."""
        # Check for duplicate URL
        if await self.repo.exists_by_url(user_id, data.url):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Feed with this URL already exists"
            )
        
        # Validate category if provided
        if data.category_id:
            category = await self.category_repo.get_by_id(data.category_id, user_id)
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Category not found"
                )
        
        # Parse the feed
        try:
            parsed = await parse_feed(data.url, use_playwright=data.use_playwright)
        except FeedParserError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        
        # Create feed
        feed = await self.repo.create(
            user_id=user_id,
            url=data.url,
            title=parsed.title,
            description=parsed.description,
            site_url=parsed.site_url,
            icon_url=parsed.icon_url,
            category_id=data.category_id,
            fetch_interval=data.fetch_interval,
            use_playwright=data.use_playwright,
            auto_translate=data.auto_translate,
            auto_summarize=data.auto_summarize,
            target_language=data.target_language
        )
        
        # Save articles from the feed
        article_count = await self._save_articles(feed.id, parsed)
        
        return self._to_response(feed, article_count=article_count)

    async def get_all(self, user_id: int) -> List[FeedResponse]:
        """Get all feeds for a user."""
        feeds = await self.repo.get_all_by_user(user_id)
        
        # Get article counts for all feeds
        feed_ids = [f.id for f in feeds]
        counts = await self.repo.get_article_counts(user_id, feed_ids)
        
        return [
            self._to_response(
                f,
                article_count=counts.get(f.id, {}).get('article_count', 0),
                unread_count=counts.get(f.id, {}).get('unread_count', 0)
            )
            for f in feeds
        ]

    async def get_by_id(self, user_id: int, feed_id: int) -> FeedResponse:
        """Get a feed by ID."""
        feed = await self.repo.get_by_id(feed_id, user_id)
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed not found"
            )
        counts = await self.repo.get_article_counts(user_id, [feed_id])
        return self._to_response(
            feed,
            article_count=counts.get(feed_id, {}).get('article_count', 0),
            unread_count=counts.get(feed_id, {}).get('unread_count', 0)
        )

    async def update(self, user_id: int, feed_id: int, data: FeedUpdate) -> FeedResponse:
        """Update a feed."""
        feed = await self.repo.get_by_id(feed_id, user_id)
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed not found"
            )
        
        # Validate category if provided
        if data.category_id is not None:
            if data.category_id:
                category = await self.category_repo.get_by_id(data.category_id, user_id)
                if not category:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Category not found"
                    )
        
        update_data = data.model_dump(exclude_unset=True)
        feed = await self.repo.update(feed, **update_data)
        
        counts = await self.repo.get_article_counts(user_id, [feed_id])
        return self._to_response(
            feed,
            article_count=counts.get(feed_id, {}).get('article_count', 0),
            unread_count=counts.get(feed_id, {}).get('unread_count', 0)
        )

    async def delete(self, user_id: int, feed_id: int) -> None:
        """Delete a feed."""
        feed = await self.repo.get_by_id(feed_id, user_id)
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed not found"
            )
        await self.repo.delete(feed)

    async def refresh(self, user_id: int, feed_id: int) -> FeedResponse:
        """Manually refresh a feed."""
        from sqlalchemy import select
        from app.models.custom_rule import CustomRule
        
        feed = await self.repo.get_by_id(feed_id, user_id)
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed not found"
            )
        
        # Check if this feed has an associated custom rule
        result = await self.session.execute(
            select(CustomRule).where(CustomRule.feed_id == feed_id)
        )
        custom_rule = result.scalar_one_or_none()
        
        if custom_rule:
            # Use custom rule service to refresh
            from app.services.custom_rule_service import CustomRuleService
            rule_service = CustomRuleService(self.session)
            try:
                await rule_service.execute_rule(custom_rule)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(e)
                )
        else:
            # Normal RSS feed refresh
            try:
                parsed = await parse_feed(feed.url, use_playwright=feed.use_playwright)
                await self.repo.update_fetch_status(feed, success=True)
                # Save new articles
                await self._save_articles(feed_id, parsed)
            except FeedParserError as e:
                await self.repo.update_fetch_status(feed, success=False, error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(e)
                )
        
        counts = await self.repo.get_article_counts(user_id, [feed_id])
        return self._to_response(
            feed,
            article_count=counts.get(feed_id, {}).get('article_count', 0),
            unread_count=counts.get(feed_id, {}).get('unread_count', 0)
        )

    async def refresh_all(self, user_id: int, category_id: int | None = None) -> dict:
        """Refresh all feeds for a user, optionally filtered by category."""
        feeds = await self.repo.get_all_by_user(user_id)
        
        if category_id:
            feeds = [f for f in feeds if f.category_id == category_id]
        
        total = len(feeds)
        success = 0
        failed = 0
        new_articles = 0
        
        for feed in feeds:
            try:
                parsed = await parse_feed(feed.url, use_playwright=feed.use_playwright)
                await self.repo.update_fetch_status(feed, success=True)
                count = await self._save_articles(feed.id, parsed)
                new_articles += count
                success += 1
            except FeedParserError:
                await self.repo.update_fetch_status(feed, success=False, error=str(e))
                failed += 1
            except Exception:
                failed += 1
        
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "new_articles": new_articles
        }

    async def import_opml(self, user_id: int, content: str) -> OPMLImportResult:
        """Import feeds from OPML content."""
        try:
            opml_feeds = parse_opml(content)
        except OPMLParseError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        
        imported = 0
        skipped = 0
        errors = []
        
        # Cache categories
        category_cache: dict[str, int] = {}
        
        for opml_feed in opml_feeds:
            # Skip if URL already exists
            if await self.repo.exists_by_url(user_id, opml_feed.url):
                skipped += 1
                continue
            
            # Get or create category
            category_id = None
            if opml_feed.category:
                if opml_feed.category in category_cache:
                    category_id = category_cache[opml_feed.category]
                else:
                    # Check if category exists
                    categories = await self.category_repo.get_all_by_user(user_id)
                    existing = next((c for c in categories if c.name == opml_feed.category), None)
                    if existing:
                        category_id = existing.id
                    else:
                        # Create category
                        new_cat = await self.category_repo.create(user_id, opml_feed.category)
                        category_id = new_cat.id
                    category_cache[opml_feed.category] = category_id
            
            # Try to parse and add feed
            try:
                parsed = await parse_feed(opml_feed.url)
                await self.repo.create(
                    user_id=user_id,
                    url=opml_feed.url,
                    title=parsed.title or opml_feed.title,
                    description=parsed.description,
                    site_url=parsed.site_url or opml_feed.site_url,
                    icon_url=parsed.icon_url,
                    category_id=category_id
                )
                imported += 1
            except FeedParserError as e:
                errors.append(f"{opml_feed.url}: {str(e)}")
        
        return OPMLImportResult(imported=imported, skipped=skipped, errors=errors)

    async def export_opml(self, user_id: int) -> str:
        """Export feeds to OPML format."""
        feeds = await self.repo.get_all_by_user(user_id)
        categories = await self.category_repo.get_all_by_user(user_id)
        
        # Build category name lookup
        cat_names = {c.id: c.name for c in categories}
        
        feed_data = []
        for feed in feeds:
            feed_data.append({
                "title": feed.title,
                "url": feed.url,
                "site_url": feed.site_url,
                "category": cat_names.get(feed.category_id) if feed.category_id else None
            })
        
        return generate_opml(feed_data)

    async def _save_articles(self, feed_id: int, parsed: ParsedFeed) -> int:
        """Save articles from parsed feed. Returns count of new articles."""
        count = 0
        for article in parsed.articles:
            # Check if article already exists
            existing = await self.article_repo.get_by_guid(feed_id, article.guid)
            if existing:
                continue
            
            await self.article_repo.create(
                feed_id=feed_id,
                guid=article.guid,
                title=article.title,
                link=article.link,
                content=article.content,
                author=article.author,
                published_at=article.published_at
            )
            count += 1
        
        return count

    async def reorder(self, user_id: int, data: FeedReorder) -> List[FeedResponse]:
        """Reorder feeds by updating their positions."""
        # Update positions based on order in feed_ids
        for position, feed_id in enumerate(data.feed_ids):
            feed = await self.repo.get_by_id(feed_id, user_id)
            if feed:
                await self.repo.update(feed, position=position)
        
        return await self.get_all(user_id)

    def _to_response(self, feed: Feed, article_count: int = 0, unread_count: int = 0) -> FeedResponse:
        """Convert feed model to response schema."""
        return FeedResponse(
            id=feed.id,
            url=feed.url,
            title=feed.title,
            description=feed.description,
            site_url=feed.site_url,
            icon_url=feed.icon_url,
            category_id=feed.category_id,
            fetch_interval=feed.fetch_interval,
            last_fetched_at=feed.last_fetched_at,
            auto_translate=feed.auto_translate,
            auto_summarize=feed.auto_summarize,
            target_language=feed.target_language,
            is_active=feed.is_active,
            use_playwright=feed.use_playwright,
            position=feed.position,
            unread_count=unread_count,
            article_count=article_count
        )
