"""Feed service for business logic."""
import json
from typing import List
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feed import Feed
from app.repositories.article_repository import ArticleRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.feed_repository import FeedRepository
from app.repositories.proxy_pool_repository import ProxyPoolRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.schemas.feed import FeedCreate, FeedReorder, FeedResponse, FeedUpdate, OPMLImportResult
from app.utils.feed_parser import (
    FeedParserError,
    ParsedFeed,
    is_browser_engine_enabled,
    normalize_browser_engine,
    parse_feed,
)
from app.utils.opml import OPMLFeed, OPMLParseError, generate_opml, parse_opml


# 默认的同步间隔选项（秒）
DEFAULT_SYNC_INTERVALS = [300, 900, 1800, 3600, 7200, 14400, 43200, 86400]


class FeedService:
    """Service for feed operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FeedRepository(session)
        self.category_repo = CategoryRepository(session)
        self.article_repo = ArticleRepository(session)
        self.settings_repo = SystemSettingsRepository(session)
        self.proxy_repo = ProxyPoolRepository(session)

    async def _get_allowed_intervals(self) -> list[int]:
        """Get allowed sync intervals from system settings."""
        intervals_str = await self.settings_repo.get('sync_intervals')
        if intervals_str:
            try:
                data = json.loads(intervals_str)
                return [item['value'] for item in data]
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        return DEFAULT_SYNC_INTERVALS

    async def _validate_fetch_interval(self, interval: int) -> int:
        """Validate and adjust fetch interval to allowed values."""
        allowed = await self._get_allowed_intervals()
        if not allowed:
            return interval
        
        if interval in allowed:
            return interval
        
        # Find the closest allowed interval that is >= requested
        for allowed_interval in sorted(allowed):
            if allowed_interval >= interval:
                return allowed_interval
        
        # If requested is larger than all allowed, use the largest allowed
        return max(allowed)

    def _normalize_proxy_config(
        self,
        proxy_mode: str | None,
        proxy_enabled: bool | None,
        proxy_url: str | None,
        proxy_pool_country: str | None = None,
        proxy_pool_protocol: str | None = None,
    ) -> tuple[str, bool, str | None, str | None, str | None]:
        """Normalize and validate per-feed proxy settings."""
        mode = (proxy_mode or ("single" if proxy_enabled else "none")).strip().lower()
        if mode not in {"none", "single", "pool"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="代理模式无效",
            )

        normalized_url = proxy_url.strip() if proxy_url else None
        normalized_country = proxy_pool_country.strip().lower() if proxy_pool_country else None
        normalized_protocol = proxy_pool_protocol.strip().lower() if proxy_pool_protocol else None

        if normalized_protocol and normalized_protocol not in {
            "http",
            "https",
            "socks4",
            "socks5",
            "socks5h",
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="代理池协议筛选无效",
            )

        if mode == "none":
            return "none", False, None, None, None

        if mode == "pool":
            return "pool", True, None, normalized_country, normalized_protocol

        if not normalized_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="使用单个代理时必须填写代理地址",
            )

        parsed = urlparse(normalized_url)
        if parsed.scheme not in {"http", "https", "socks4", "socks5", "socks5h"} or not parsed.netloc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="代理地址格式无效，请使用 http://host:port 或 socks5://host:port",
            )

        return "single", True, normalized_url, None, None

    async def _parse_feed_with_proxy(
        self,
        user_id: int,
        url: str,
        browser_engine: str | None,
        proxy_mode: str,
        proxy_url: str | None,
        proxy_pool_country: str | None,
        proxy_pool_protocol: str | None,
        use_playwright: bool = False,
    ) -> ParsedFeed:
        """Parse a feed, rotating through proxy pool candidates when configured."""
        if proxy_mode == "pool":
            candidates = await self.proxy_repo.get_candidates(
                user_id,
                country=proxy_pool_country,
                protocol=proxy_pool_protocol,
            )
            if not candidates:
                raise FeedParserError("代理池没有可用代理")

            last_error = ""
            for proxy in candidates:
                try:
                    parsed = await parse_feed(
                        url,
                        use_playwright=use_playwright,
                        browser_engine=browser_engine,
                        proxy_url=proxy.proxy_url,
                    )
                    await self.proxy_repo.record_success(proxy)
                    await self.session.commit()
                    return parsed
                except Exception as exc:
                    last_error = str(exc)
                    await self.proxy_repo.record_failure(proxy, last_error)
                    await self.session.commit()

            raise FeedParserError(f"代理池全部失败: {last_error or '未知错误'}")

        return await parse_feed(
            url,
            use_playwright=use_playwright,
            browser_engine=browser_engine,
            proxy_url=proxy_url if proxy_mode == "single" else None,
        )

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
        
        browser_engine = data.resolved_browser_engine
        (
            proxy_mode,
            proxy_enabled,
            proxy_url,
            proxy_pool_country,
            proxy_pool_protocol,
        ) = self._normalize_proxy_config(
            data.proxy_mode,
            data.proxy_enabled,
            data.proxy_url,
            data.proxy_pool_country,
            data.proxy_pool_protocol,
        )

        # Parse the feed
        try:
            parsed = await self._parse_feed_with_proxy(
                user_id,
                data.url,
                browser_engine=browser_engine,
                proxy_mode=proxy_mode,
                proxy_url=proxy_url,
                proxy_pool_country=proxy_pool_country,
                proxy_pool_protocol=proxy_pool_protocol,
            )
        except FeedParserError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        
        # Validate fetch interval
        validated_interval = await self._validate_fetch_interval(data.fetch_interval)
        
        # Create feed
        feed = await self.repo.create(
            user_id=user_id,
            url=data.url,
            title=parsed.title,
            description=parsed.description,
            site_url=parsed.site_url,
            icon_url=parsed.icon_url,
            category_id=data.category_id,
            fetch_interval=validated_interval,
            use_playwright=is_browser_engine_enabled(browser_engine),
            browser_engine=browser_engine,
            proxy_enabled=proxy_enabled,
            proxy_url=proxy_url,
            proxy_mode=proxy_mode,
            proxy_pool_country=proxy_pool_country,
            proxy_pool_protocol=proxy_pool_protocol,
            auto_translate=data.auto_translate,
            auto_summarize=data.auto_summarize,
            target_language=data.target_language,
            translate_method=data.translate_method
        )
        
        # Save articles from the feed
        article_count = await self._save_articles(user_id, feed, parsed)
        
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

        if "browser_engine" in update_data:
            update_data["browser_engine"] = normalize_browser_engine(update_data["browser_engine"])
            update_data["use_playwright"] = is_browser_engine_enabled(
                update_data["browser_engine"]
            )
        elif "use_playwright" in update_data:
            update_data["browser_engine"] = normalize_browser_engine(
                None,
                update_data["use_playwright"],
            )

        if any(
            key in update_data
            for key in [
                "proxy_mode",
                "proxy_enabled",
                "proxy_url",
                "proxy_pool_country",
                "proxy_pool_protocol",
            ]
        ):
            (
                proxy_mode,
                proxy_enabled,
                proxy_url,
                proxy_pool_country,
                proxy_pool_protocol,
            ) = self._normalize_proxy_config(
                update_data.get("proxy_mode", getattr(feed, "proxy_mode", None)),
                update_data.get("proxy_enabled", feed.proxy_enabled),
                update_data.get("proxy_url", feed.proxy_url),
                update_data.get("proxy_pool_country", getattr(feed, "proxy_pool_country", None)),
                update_data.get("proxy_pool_protocol", getattr(feed, "proxy_pool_protocol", None)),
            )
            update_data["proxy_mode"] = proxy_mode
            update_data["proxy_enabled"] = proxy_enabled
            update_data["proxy_url"] = proxy_url
            update_data["proxy_pool_country"] = proxy_pool_country
            update_data["proxy_pool_protocol"] = proxy_pool_protocol
        
        # Validate fetch interval if provided
        if 'fetch_interval' in update_data:
            update_data['fetch_interval'] = await self._validate_fetch_interval(update_data['fetch_interval'])
        
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
                parsed = await self._parse_feed_with_proxy(
                    user_id,
                    feed.url,
                    use_playwright=feed.use_playwright,
                    browser_engine=getattr(feed, "browser_engine", None),
                    proxy_mode=getattr(
                        feed,
                        "proxy_mode",
                        "single" if feed.proxy_enabled else "none",
                    ),
                    proxy_url=feed.proxy_url,
                    proxy_pool_country=getattr(feed, "proxy_pool_country", None),
                    proxy_pool_protocol=getattr(feed, "proxy_pool_protocol", None),
                )
                await self.repo.update_fetch_status(feed, success=True)
                # Save new articles
                await self._save_articles(user_id, feed, parsed)
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
                parsed = await self._parse_feed_with_proxy(
                    user_id,
                    feed.url,
                    use_playwright=feed.use_playwright,
                    browser_engine=getattr(feed, "browser_engine", None),
                    proxy_mode=getattr(
                        feed,
                        "proxy_mode",
                        "single" if feed.proxy_enabled else "none",
                    ),
                    proxy_url=feed.proxy_url,
                    proxy_pool_country=getattr(feed, "proxy_pool_country", None),
                    proxy_pool_protocol=getattr(feed, "proxy_pool_protocol", None),
                )
                await self.repo.update_fetch_status(feed, success=True)
                count = await self._save_articles(user_id, feed, parsed)
                new_articles += count
                success += 1
            except FeedParserError as e:
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

    async def _save_articles(self, user_id: int, feed: Feed, parsed: ParsedFeed) -> int:
        """Save articles from parsed feed. Returns count of new articles."""
        count = 0
        for article in parsed.articles:
            # Check if article already exists
            existing = await self.article_repo.get_by_guid(feed.id, article.guid)
            if existing:
                continue
            
            saved_article = await self.article_repo.create(
                feed_id=feed.id,
                guid=article.guid,
                title=article.title,
                link=article.link,
                content=article.content,
                author=article.author,
                published_at=article.published_at
            )
            await self._auto_translate_article(user_id, feed, saved_article.id)
            count += 1
        
        return count

    async def _auto_translate_article(self, user_id: int, feed: Feed, article_id: int) -> None:
        """Translate a newly saved article when the feed has translation enabled."""
        translate_method = getattr(feed, 'translate_method', None) or (
            'ai' if feed.auto_translate else 'none'
        )
        if translate_method == 'none' or not feed.target_language:
            return

        try:
            from app.services.article_service import ArticleService

            await ArticleService(self.session).translate_article(
                user_id,
                article_id,
                feed.target_language,
            )
        except Exception as e:
            print(f"[FeedService] Auto translation failed for article {article_id}: {e}")

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
            translate_method=getattr(feed, 'translate_method', 'none'),
            is_active=feed.is_active,
            use_playwright=feed.use_playwright,
            browser_engine=getattr(
                feed,
                'browser_engine',
                "playwright" if feed.use_playwright else "http",
            ),
            proxy_enabled=getattr(feed, 'proxy_enabled', False),
            proxy_url=getattr(feed, 'proxy_url', None),
            proxy_mode=getattr(
                feed,
                'proxy_mode',
                "single" if getattr(feed, 'proxy_enabled', False) else "none",
            ),
            proxy_pool_country=getattr(feed, 'proxy_pool_country', None),
            proxy_pool_protocol=getattr(feed, 'proxy_pool_protocol', None),
            position=feed.position,
            unread_count=unread_count,
            article_count=article_count
        )
