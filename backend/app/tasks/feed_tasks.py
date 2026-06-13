"""Feed-related background tasks."""
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.article import Article
from app.models.feed import Feed
from app.models.custom_rule import CustomRule
from app.models.proxy_pool import ProxyPoolEntry
from app.models.ai_provider import AIModel, AIProvider
from app.utils.feed_parser import FeedParserError, parse_feed, ParsedFeed


# Create sync engine for Celery tasks
# Read DATABASE_URL directly from environment to avoid caching issues
def get_sync_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./rss_manager.db")
    if "postgresql+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    elif "sqlite+aiosqlite" in url:
        return url.replace("sqlite+aiosqlite", "sqlite")
    return url


# Lazy initialization of database engine
_sync_engine = None
_SyncSessionLocal = None
FEED_REFRESH_QUEUE_LOCK_TTL = int(os.environ.get("FEED_REFRESH_QUEUE_LOCK_TTL", "14400"))


def get_sync_session():
    """Get a sync database session, initializing engine if needed."""
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        _sync_engine = create_engine(get_sync_database_url())
        _SyncSessionLocal = sessionmaker(bind=_sync_engine)
    return _SyncSessionLocal()


def get_redis_client():
    """Get a Redis client for Celery coordination locks."""
    import redis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


def _feed_refresh_slot_key(feed_id: int) -> str:
    return f"refresh_feed_{feed_id}_queued_or_running"


def _redis_value_matches(value, expected: str) -> bool:
    if value is None:
        return False
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace") == expected
    return str(value) == expected


def _acquire_feed_refresh_slot(redis_client, feed_id: int, owner: str) -> bool:
    return bool(
        redis_client.set(
            _feed_refresh_slot_key(feed_id),
            owner,
            nx=True,
            ex=FEED_REFRESH_QUEUE_LOCK_TTL,
        )
    )


def _refresh_feed_slot_for_worker(redis_client, feed_id: int, owner: str) -> bool:
    key = _feed_refresh_slot_key(feed_id)
    current_owner = redis_client.get(key)

    if current_owner is None:
        return _acquire_feed_refresh_slot(redis_client, feed_id, owner)

    if _redis_value_matches(current_owner, owner):
        redis_client.expire(key, FEED_REFRESH_QUEUE_LOCK_TTL)
        return True

    return False


def _release_feed_refresh_slot(redis_client, feed_id: int, owner: str) -> None:
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """
    try:
        redis_client.eval(script, 1, _feed_refresh_slot_key(feed_id), owner)
    except Exception:
        pass


def _generate_article_embedding_sync(db: Session, article: Article, user_id: int) -> None:
    """Generate embedding for a single article (sync version, non-blocking on failure)."""
    from app.models.user import User
    
    try:
        # Get user's embedding configuration
        user = db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        
        if not user or not user.embedding_provider_id or not user.embedding_model:
            # No embedding config, skip silently
            return
        
        provider = db.execute(
            select(AIProvider).where(AIProvider.id == user.embedding_provider_id)
        ).scalar_one_or_none()
        
        if not provider:
            return
        
        # Generate embedding
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.services.embedding_service import EmbeddingService
            
            service = EmbeddingService(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=user.embedding_model
            )
            
            # Combine title and content for embedding
            text = f"{article.title} {article.content or ''}"
            embedding = loop.run_until_complete(service.generate_embedding(text))
            
            if embedding:
                article.embedding = embedding
                db.flush()
                print(f"Generated embedding for article {article.id}: {article.title[:50]}...")
        finally:
            loop.close()
    except Exception as e:
        # Don't fail the article save if embedding generation fails
        print(f"Failed to generate embedding for article {article.id}: {e}")


def _process_article_with_ai(db: Session, article: Article, feed: Feed) -> None:
    """Process article with AI/Google translate and summarize if enabled."""
    from app.models.user import User
    
    # Get translate_method, default to checking auto_translate for backward compatibility
    translate_method = getattr(feed, 'translate_method', None) or ('ai' if feed.auto_translate else 'none')
    
    if translate_method == 'none' and not feed.auto_summarize:
        return
    
    title = article.title or ""
    content = article.content or ""
    content_for_ai = content or title
    if not content_for_ai:
        return
    
    # Get user info
    user = db.execute(
        select(User).where(User.id == feed.user_id)
    ).scalar_one_or_none()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Handle translation based on method
        if translate_method == 'google' and feed.target_language:
            # Use Google Translate
            try:
                from app.services.google_translate_key_service import (
                    translate_google_article_sync,
                )
                from app.services.google_translate_service import GoogleTranslateError
                translated_title, translated_content = translate_google_article_sync(
                    db,
                    feed.user_id,
                    title,
                    content,
                    feed.target_language,
                    loop,
                )
                article.translation = json.dumps(
                    {"title": translated_title, "content": translated_content},
                    ensure_ascii=False,
                )
                print(f"Google translated article {article.id}: {article.title[:50]}...")
            except GoogleTranslateError as e:
                print(f"Google translate error for article {article.id}: {e}")
        
        elif translate_method == 'ai' and feed.target_language:
            # Use AI translation
            default_model = db.execute(
                select(AIModel)
                .join(AIProvider, AIModel.provider_id == AIProvider.id)
                .where(
                    AIProvider.user_id == feed.user_id,
                    AIModel.is_default == True
                )
            ).scalar_one_or_none()
            
            if not default_model:
                print(f"No default AI model set for user {feed.user_id}, skipping AI translation")
            else:
                provider = db.execute(
                    select(AIProvider).where(AIProvider.id == default_model.provider_id)
                ).scalar_one_or_none()
                
                if provider:
                    translate_prompt = user.translate_prompt if user and user.translate_prompt else None
                    
                    try:
                        from app.services.ai_client import create_ai_client, AIClientError
                        client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
                        translated_title = (
                            loop.run_until_complete(client.translate(title, feed.target_language, translate_prompt))
                            if title
                            else ""
                        )
                        translated_content = (
                            loop.run_until_complete(client.translate(content, feed.target_language, translate_prompt))
                            if content
                            else ""
                        )
                        article.translation = json.dumps(
                            {"title": translated_title, "content": translated_content},
                            ensure_ascii=False,
                        )
                    except AIClientError as e:
                        print(f"AI translate error for article {article.id}: {e}")
        
        # Handle AI summarization (always uses AI model)
        if feed.auto_summarize:
            default_model = db.execute(
                select(AIModel)
                .join(AIProvider, AIModel.provider_id == AIProvider.id)
                .where(
                    AIProvider.user_id == feed.user_id,
                    AIModel.is_default == True
                )
            ).scalar_one_or_none()
            
            if not default_model:
                print(f"No default AI model set for user {feed.user_id}, skipping AI summarization")
            else:
                provider = db.execute(
                    select(AIProvider).where(AIProvider.id == default_model.provider_id)
                ).scalar_one_or_none()
                
                if provider:
                    summarize_prompt = user.summarize_prompt if user and user.summarize_prompt else None
                    
                    try:
                        from app.services.ai_client import create_ai_client, AIClientError
                        client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
                        summary = loop.run_until_complete(client.summarize(content_for_ai, summarize_prompt))
                        article.summary = summary
                    except AIClientError as e:
                        print(f"AI summarize error for article {article.id}: {e}")
        
        db.commit()
    except Exception as e:
        print(f"Article processing error: {e}")
    finally:
        loop.close()


def _translation_has_title(translation: str | None) -> bool:
    """Return whether a stored translation already contains a translated title."""
    if not translation:
        return False
    try:
        data = json.loads(translation)
    except (TypeError, json.JSONDecodeError):
        return False
    return bool(data.get("title"))


def _record_proxy_success_sync(db: Session, proxy: ProxyPoolEntry) -> None:
    proxy.fail_count = 0
    proxy.is_active = True
    proxy.last_error = None
    proxy.last_used_at = datetime.utcnow()
    proxy.last_tested_at = datetime.utcnow()
    db.flush()


def _record_proxy_failure_sync(db: Session, proxy: ProxyPoolEntry, error: str) -> None:
    proxy.fail_count += 1
    if proxy.fail_count >= 5:
        proxy.is_active = False
    proxy.last_error = error[:1000]
    proxy.last_used_at = datetime.utcnow()
    proxy.last_tested_at = datetime.utcnow()
    db.flush()


def _get_proxy_candidates_sync(db: Session, feed: Feed) -> list[ProxyPoolEntry]:
    query = select(ProxyPoolEntry).where(
        ProxyPoolEntry.user_id == feed.user_id,
        ProxyPoolEntry.is_active == True,
    )
    country = getattr(feed, "proxy_pool_country", None)
    protocol = getattr(feed, "proxy_pool_protocol", None)
    if country:
        query = query.where(ProxyPoolEntry.country == country)
    if protocol:
        query = query.where(ProxyPoolEntry.protocol == protocol)
    query = query.order_by(
        ProxyPoolEntry.fail_count,
        ProxyPoolEntry.last_used_at.is_not(None),
        ProxyPoolEntry.last_used_at,
        ProxyPoolEntry.last_latency_ms.is_(None),
        ProxyPoolEntry.last_latency_ms,
        ProxyPoolEntry.id,
    )
    return list(db.execute(query).scalars().all())


def _parse_feed_for_sync_refresh(db: Session, feed: Feed) -> ParsedFeed:
    """Parse a feed for Celery refresh, rotating pool proxies when configured."""
    proxy_mode = getattr(
        feed,
        "proxy_mode",
        "single" if getattr(feed, "proxy_enabled", False) else "none",
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        if proxy_mode == "pool":
            candidates = _get_proxy_candidates_sync(db, feed)
            if not candidates:
                raise FeedParserError("代理池没有可用代理")

            last_error = ""
            for proxy in candidates:
                try:
                    parsed = loop.run_until_complete(
                        parse_feed(
                            feed.url,
                            use_playwright=feed.use_playwright,
                            browser_engine=getattr(feed, "browser_engine", None),
                            proxy_url=proxy.proxy_url,
                        )
                    )
                    _record_proxy_success_sync(db, proxy)
                    return parsed
                except Exception as exc:
                    last_error = str(exc)
                    _record_proxy_failure_sync(db, proxy, last_error)

            raise FeedParserError(f"代理池全部失败: {last_error or '未知错误'}")

        proxy_url = (
            getattr(feed, "proxy_url", None)
            if proxy_mode == "single" and getattr(feed, "proxy_enabled", False)
            else None
        )
        return loop.run_until_complete(
            parse_feed(
                feed.url,
                use_playwright=feed.use_playwright,
                browser_engine=getattr(feed, "browser_engine", None),
                proxy_url=proxy_url,
            )
        )
    finally:
        loop.close()


def _refresh_feed_sync(db: Session, feed: Feed) -> int:
    """Refresh a single feed and return number of new articles (sync version)."""
    try:
        parsed: Optional[ParsedFeed] = _parse_feed_for_sync_refresh(db, feed)
        
        if not parsed:
            feed.last_error = "Failed to parse feed"
            feed.error_count += 1
            db.commit()
            return 0
        
        new_count = 0
        for article_data in parsed.articles:
            # Check if article already exists
            guid = article_data.guid
            if not guid:
                continue
            
            existing = db.execute(
                select(Article).where(
                    Article.feed_id == feed.id,
                    Article.guid == guid
                )
            ).scalar_one_or_none()
            
            if existing:
                continue
            
            # Create new article
            article = Article(
                feed_id=feed.id,
                guid=guid,
                title=article_data.title or "Untitled",
                link=article_data.link,
                content=article_data.content,
                summary=None,  # Only set by AI if auto_summarize is enabled
                author=article_data.author,
                published_at=article_data.published_at,
            )
            db.add(article)
            db.flush()  # Get article ID
            
            # Process with AI if enabled
            _process_article_with_ai(db, article, feed)
            
            # Generate embedding for the new article (async, non-blocking)
            _generate_article_embedding_sync(db, article, feed.user_id)
            
            new_count += 1
        
        feed.last_fetched_at = datetime.utcnow()
        feed.last_error = None
        feed.error_count = 0
        db.commit()
        
        return new_count
    except Exception as e:
        feed.last_error = str(e)[:500]
        feed.error_count += 1
        db.commit()
        return 0


def _execute_custom_rule_sync(db: Session, rule: CustomRule) -> list[dict]:
    """Execute a custom rule and save articles (sync version for Celery)."""
    from urllib.parse import urljoin
    from hashlib import md5
    import httpx
    from bs4 import BeautifulSoup
    
    # Ensure rule has associated feed
    feed_id = rule.feed_id
    if not feed_id:
        # Create feed for legacy rule without feed_id
        feed = Feed(
            user_id=rule.user_id,
            category_id=rule.category_id,
            url=rule.target_url,
            title=rule.name,
            description=f"自定义抓取规则: {rule.name}",
            fetch_interval=rule.fetch_interval,
            auto_translate=rule.auto_translate,
            auto_summarize=rule.auto_summarize,
            target_language=rule.target_language,
            translate_method=getattr(rule, 'translate_method', 'none'),
            is_active=rule.is_active,
        )
        db.add(feed)
        db.flush()
        rule.feed_id = feed.id
        feed_id = feed.id
        db.commit()
    
    try:
        # Parse cookies if provided
        cookies_dict = {}
        if hasattr(rule, 'cookies') and rule.cookies:
            for item in rule.cookies.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookies_dict[key.strip()] = value.strip()
        
        # Fetch page content
        print(f"[CustomRule] use_playwright={rule.use_playwright} for rule {rule.id}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if rule.use_playwright:
                async def _fetch_with_playwright():
                    from playwright.async_api import async_playwright
                    print(f"[CustomRule] Starting Playwright for {rule.target_url}")
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        context = await browser.new_context()
                        if cookies_dict:
                            cookie_list = [{"name": k, "value": v, "domain": rule.target_url.split('/')[2], "path": "/"} for k, v in cookies_dict.items()]
                            await context.add_cookies(cookie_list)
                        page = await context.new_page()
                        await page.goto(rule.target_url, wait_until="networkidle", timeout=30000)
                        content = await page.content()
                        await browser.close()
                    return content
                html_content = loop.run_until_complete(_fetch_with_playwright())
                print(f"[CustomRule] Playwright loaded {len(html_content)} bytes")
            else:
                async def _fetch_with_httpx():
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    async with httpx.AsyncClient(timeout=30.0, cookies=cookies_dict if cookies_dict else None) as client:
                        response = await client.get(rule.target_url, headers=headers)
                        response.raise_for_status()
                    return response.text
                html_content = loop.run_until_complete(_fetch_with_httpx())
                print(f"[CustomRule] HTTP loaded {len(html_content)} bytes")
        finally:
            loop.close()
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Use specialized parser for telegram/twitter
        rule_type = getattr(rule, 'rule_type', 'general') or 'general'
        print(f"[CustomRule] rule_type={rule_type}")
        
        if rule_type == 'telegram':
            items = soup.select('.tgme_widget_message_wrap')
        elif rule_type == 'twitter':
            items = soup.select('.timeline-item')
        else:
            items = soup.select(rule.list_selector)
        
        print(f"[CustomRule] Found {len(items)} items")
        
        new_articles = []
        skipped_no_title_link = 0
        skipped_existing = 0
        
        for idx, item in enumerate(items):
            title = None
            link = None
            content = None
            published_at = None
            
            if rule_type == 'telegram':
                text_elem = item.select_one('.tgme_widget_message_text')
                if text_elem:
                    content = str(text_elem)
                    title = text_elem.get_text(strip=True)[:100]
                    if len(text_elem.get_text(strip=True)) > 100:
                        title += '...'
                
                link_elem = item.select_one('.tgme_widget_message_date')
                if link_elem:
                    link = link_elem.get('href')
                
                time_elem = item.select_one('time[datetime]')
                if time_elem:
                    try:
                        from dateutil import parser as date_parser
                        published_at = date_parser.parse(time_elem.get('datetime'))
                    except:
                        pass
                
                if not title:
                    fwd = item.select_one('.tgme_widget_message_forwarded_from')
                    if fwd:
                        title = f"[转发] {fwd.get_text(strip=True)}"
                    else:
                        skipped_no_title_link += 1
                        continue
            
            elif rule_type == 'twitter':
                text_elem = item.select_one('.tweet-content')
                if text_elem:
                    content = str(text_elem)
                    title = text_elem.get_text(strip=True)[:100]
                    if len(text_elem.get_text(strip=True)) > 100:
                        title += '...'
                
                link_elem = item.select_one('.tweet-link')
                if link_elem:
                    link = link_elem.get('href')
                    if link and not link.startswith('http'):
                        link = urljoin(rule.target_url, link)
                
                time_elem = item.select_one('.tweet-date a')
                if time_elem:
                    try:
                        from dateutil import parser as date_parser
                        title_attr = time_elem.get('title')
                        if title_attr:
                            published_at = date_parser.parse(title_attr)
                    except:
                        pass
                
                if not title:
                    skipped_no_title_link += 1
                    continue
            
            else:
                # General rule parsing
                title_elem = item.select_one(rule.title_selector)
                
                if not rule.link_selector or rule.link_selector.lower() in ('self', '.', 'this'):
                    link_elem = item if item.name == 'a' else item.find('a')
                else:
                    link_elem = item.select_one(rule.link_selector)
                
                if link_elem:
                    link = link_elem.get("href")
                    if not link and link_elem.name != 'a':
                        inner_a = link_elem.find('a')
                        if inner_a:
                            link = inner_a.get('href')
                
                if not title_elem:
                    skipped_no_title_link += 1
                    continue
                
                title = title_elem.get_text(strip=True)
                
                if rule.content_selector:
                    content_elem = item.select_one(rule.content_selector)
                    content = content_elem.get_text(strip=True) if content_elem else None
            
            if not title:
                skipped_no_title_link += 1
                continue
            
            # Make link absolute
            if link and not link.startswith("http"):
                link = urljoin(rule.target_url, link)
            
            # Generate guid
            if link:
                guid = md5(link.encode()).hexdigest()
            else:
                guid = md5(title.encode()).hexdigest()
            
            if idx == 0:
                print(f"[CustomRule] First item: title={title[:50]}..., link={link}, guid={guid[:8]}")
            
            # Check if article exists
            existing = db.execute(
                select(Article).where(
                    Article.feed_id == feed_id,
                    Article.guid == guid
                )
            ).scalar_one_or_none()
            
            if existing:
                skipped_existing += 1
                continue
            
            # Create article
            article = Article(
                feed_id=feed_id,
                guid=guid,
                link=link,
                title=title,
                content=content,
                published_at=published_at or datetime.utcnow(),
            )
            db.add(article)
            new_articles.append({"title": title, "link": link, "content": content})
        
        print(f"[CustomRule] Skipped {skipped_no_title_link} (no title/link), {skipped_existing} (existing), added {len(new_articles)} new")
        
        # Update rule and feed status
        now = datetime.utcnow()
        rule.last_fetched_at = now
        rule.last_error = None
        rule.error_count = 0
        
        feed = db.execute(
            select(Feed).where(Feed.id == feed_id)
        ).scalar_one_or_none()
        if feed:
            feed.last_fetched_at = now
            feed.last_error = None
            feed.error_count = 0
        
        db.commit()
        return new_articles
        
    except Exception as e:
        rule.last_error = str(e)[:500]
        rule.error_count += 1
        if feed_id:
            feed = db.execute(
                select(Feed).where(Feed.id == feed_id)
            ).scalar_one_or_none()
            if feed:
                feed.last_error = str(e)[:500]
                feed.error_count += 1
        db.commit()
        raise


@shared_task(name="app.tasks.feed_tasks.refresh_feed")
def refresh_feed(feed_id: int) -> dict:
    """Refresh a single feed."""
    with get_sync_session() as db:
        feed = db.execute(select(Feed).where(Feed.id == feed_id)).scalar_one_or_none()
        if not feed:
            return {"success": False, "error": "Feed not found"}
        
        new_count = _refresh_feed_sync(db, feed)
        return {"success": True, "new_articles": new_count}


@shared_task(name="app.tasks.feed_tasks.refresh_all_feeds")
def refresh_all_feeds() -> dict:
    """Refresh all active feeds."""
    with get_sync_session() as db:
        feeds = db.execute(
            select(Feed).where(Feed.is_active == True)
        ).scalars().all()
        
        total_new = 0
        errors = 0
        for feed in feeds:
            try:
                new_count = _refresh_feed_sync(db, feed)
                total_new += new_count
            except Exception:
                errors += 1
        
        return {
            "success": True,
            "feeds_processed": len(feeds),
            "new_articles": total_new,
            "errors": errors
        }


@shared_task(name="app.tasks.feed_tasks.refresh_due_feeds", bind=True)
def refresh_due_feeds(self) -> dict:
    """Dispatch feed refresh tasks for feeds that are due."""
    # Use Redis lock to prevent concurrent dispatch
    redis_client = get_redis_client()
    lock = redis_client.lock("refresh_due_feeds_dispatch_lock", timeout=60)
    
    if not lock.acquire(blocking=False):
        return {"success": True, "message": "Another dispatch is running", "skipped": True}
    
    try:
        with get_sync_session() as db:
            now = datetime.utcnow()
            
            # Get all active feeds
            feeds = db.execute(
                select(Feed).where(Feed.is_active == True)
            ).scalars().all()
            
            dispatched = 0
            skipped = 0
            skipped_queued = 0
            
            for feed in feeds:
                # Check if feed is due for refresh
                if feed.last_fetched_at:
                    last_fetched = feed.last_fetched_at.replace(tzinfo=None) if feed.last_fetched_at.tzinfo else feed.last_fetched_at
                    next_fetch = last_fetched + timedelta(seconds=feed.fetch_interval)
                    if now < next_fetch:
                        skipped += 1
                        continue
                
                owner = f"refresh_due_feeds:{self.request.id}:{feed.id}:{int(now.timestamp())}"
                if not _acquire_feed_refresh_slot(redis_client, feed.id, owner):
                    skipped_queued += 1
                    continue

                try:
                    # Dispatch individual feed refresh task after reserving its queue slot.
                    refresh_single_feed.delay(feed.id, owner)
                except Exception:
                    _release_feed_refresh_slot(redis_client, feed.id, owner)
                    raise
                dispatched += 1
            
            if skipped_queued:
                print(
                    "[FeedRefreshDedup] "
                    f"Skipped {skipped_queued} feeds already queued/running "
                    f"during dispatch task {self.request.id}"
                )

            return {
                "success": True,
                "feeds_checked": len(feeds),
                "feeds_dispatched": dispatched,
                "feeds_skipped": skipped,
                "feeds_skipped_queued": skipped_queued,
            }
    finally:
        try:
            lock.release()
        except Exception:
            pass


@shared_task(name="app.tasks.feed_tasks.refresh_single_feed", bind=True)
def refresh_single_feed(self, feed_id: int, refresh_owner: str | None = None) -> dict:
    """Refresh a single feed - designed for parallel execution."""
    redis_client = get_redis_client()
    owner = refresh_owner or f"refresh_single_feed:{self.request.id}:{feed_id}"

    if not _refresh_feed_slot_for_worker(redis_client, feed_id, owner):
        print(f"[FeedRefreshDedup] Skipped feed {feed_id}: already queued or processing")
        return {
            "success": True,
            "feed_id": feed_id,
            "skipped": True,
            "reason": "already queued or processing",
        }
    
    try:
        with get_sync_session() as db:
            feed = db.execute(
                select(Feed).where(Feed.id == feed_id)
            ).scalar_one_or_none()
            
            if not feed:
                return {"success": False, "feed_id": feed_id, "error": "Feed not found"}
            
            if not feed.is_active:
                return {"success": True, "feed_id": feed_id, "skipped": True, "reason": "inactive"}
            
            try:
                new_count = _refresh_feed_sync(db, feed)
                print(f"Refreshed feed {feed.id} ({feed.title}): {new_count} new articles")
                return {
                    "success": True,
                    "feed_id": feed_id,
                    "new_articles": new_count
                }
            except Exception as e:
                db.rollback()
                print(f"Error refreshing feed {feed.id}: {e}")
                return {
                    "success": False,
                    "feed_id": feed_id,
                    "error": str(e)
                }
    finally:
        _release_feed_refresh_slot(redis_client, feed_id, owner)



@shared_task(name="app.tasks.feed_tasks.execute_custom_rule")
def execute_custom_rule(rule_id: int) -> dict:
    """Execute a single custom rule."""
    # Use sync session to avoid asyncpg concurrent operation issues
    with get_sync_session() as db:
        rule = db.execute(
            select(CustomRule).where(CustomRule.id == rule_id)
        ).scalar_one_or_none()
        
        if not rule:
            return {"success": False, "error": "Rule not found"}
        
        try:
            articles = _execute_custom_rule_sync(db, rule)
            return {"success": True, "articles_found": len(articles)}
        except Exception as e:
            return {"success": False, "error": str(e)}


@shared_task(name="app.tasks.feed_tasks.execute_all_custom_rules", bind=True)
def execute_all_custom_rules(self) -> dict:
    """Dispatch custom rule execution tasks for rules that are due."""
    import redis
    import os
    
    # Use Redis lock to prevent concurrent dispatch
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url)
    lock = redis_client.lock("execute_all_custom_rules_dispatch_lock", timeout=60)
    
    if not lock.acquire(blocking=False):
        return {"success": True, "message": "Another dispatch is running", "skipped": True}
    
    try:
        with get_sync_session() as db:
            now = datetime.utcnow()
            
            rules = db.execute(
                select(CustomRule).where(CustomRule.is_active == True)
            ).scalars().all()
            
            dispatched = 0
            skipped = 0
            
            for rule in rules:
                # Check if rule is due for fetch
                if rule.last_fetched_at:
                    last_fetched = rule.last_fetched_at.replace(tzinfo=None) if rule.last_fetched_at.tzinfo else rule.last_fetched_at
                    next_fetch = last_fetched + timedelta(seconds=rule.fetch_interval)
                    if now < next_fetch:
                        skipped += 1
                        continue
                
                # Dispatch individual rule execution task
                execute_single_custom_rule.delay(rule.id)
                dispatched += 1
            
            return {
                "success": True,
                "rules_checked": len(rules),
                "rules_dispatched": dispatched,
                "rules_skipped": skipped
            }
    finally:
        try:
            lock.release()
        except Exception:
            pass


@shared_task(name="app.tasks.feed_tasks.execute_single_custom_rule", bind=True)
def execute_single_custom_rule(self, rule_id: int) -> dict:
    """Execute a single custom rule - designed for parallel execution."""
    import redis
    import os
    
    # Per-rule lock to prevent duplicate processing
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url)
    lock = redis_client.lock(f"execute_rule_{rule_id}_lock", timeout=300)
    
    if not lock.acquire(blocking=False):
        return {"success": True, "rule_id": rule_id, "skipped": True, "reason": "already processing"}
    
    try:
        # Use sync session to avoid asyncpg concurrent operation issues
        with get_sync_session() as db:
            rule = db.execute(
                select(CustomRule).where(CustomRule.id == rule_id)
            ).scalar_one_or_none()
            
            if not rule:
                return {"success": False, "rule_id": rule_id, "error": "Rule not found"}
            
            if not rule.is_active:
                return {"success": True, "rule_id": rule_id, "skipped": True, "reason": "inactive"}
            
            try:
                articles = _execute_custom_rule_sync(db, rule)
                print(f"Executed custom rule {rule.id} ({rule.name}): {len(articles)} articles")
                return {
                    "success": True,
                    "rule_id": rule_id,
                    "articles_found": len(articles)
                }
            except Exception as e:
                db.rollback()
                print(f"Error executing custom rule {rule.id}: {e}")
                import traceback
                traceback.print_exc()
                return {
                    "success": False,
                    "rule_id": rule_id,
                    "error": str(e)
                }
    finally:
        try:
            lock.release()
        except Exception:
            pass


@shared_task(name="app.tasks.feed_tasks.translate_feed_articles")
def translate_feed_articles(feed_id: int) -> dict:
    """Translate all untranslated articles in a feed using configured method (AI or Google)."""
    from app.models.user import User
    
    with get_sync_session() as db:
        feed = db.execute(select(Feed).where(Feed.id == feed_id)).scalar_one_or_none()
        if not feed:
            return {"success": False, "error": "Feed not found"}
        
        # Get translate_method, default to checking auto_translate for backward compatibility
        translate_method = getattr(feed, 'translate_method', None) or ('ai' if feed.auto_translate else 'none')
        
        if translate_method == 'none' or not feed.target_language:
            return {"success": False, "error": "Feed does not have translation enabled"}
        
        # Get user info
        user = db.execute(
            select(User).where(User.id == feed.user_id)
        ).scalar_one_or_none()
        
        # Get articles without translation, or legacy plain-text translations without a title.
        candidate_articles = db.execute(
            select(Article).where(
                Article.feed_id == feed_id
            )
        ).scalars().all()
        articles = [
            article
            for article in candidate_articles
            if not _translation_has_title(article.translation)
        ]
        
        if not articles:
            return {"success": True, "translated": 0, "message": "No articles to translate"}
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        translated_count = 0
        errors = 0
        
        try:
            if translate_method == 'google':
                # Use Google Translate
                from app.services.google_translate_key_service import (
                    translate_google_article_sync,
                )
                from app.services.google_translate_service import GoogleTranslateError
                
                for article in articles:
                    title = article.title or ""
                    content = article.content or ""
                    if not title and not content:
                        continue
                    
                    try:
                        translated_title, translated_content = translate_google_article_sync(
                            db,
                            feed.user_id,
                            title,
                            content,
                            feed.target_language,
                            loop,
                        )
                        article.translation = json.dumps(
                            {"title": translated_title, "content": translated_content},
                            ensure_ascii=False,
                        )
                        db.commit()
                        translated_count += 1
                        print(f"Google translated article {article.id}: {article.title[:50]}...")
                    except GoogleTranslateError as e:
                        print(f"Google translate error for article {article.id}: {e}")
                        errors += 1
                    except Exception as e:
                        print(f"Error translating article {article.id}: {e}")
                        errors += 1
            
            elif translate_method == 'ai':
                # Use AI translation
                default_model = db.execute(
                    select(AIModel)
                    .join(AIProvider, AIModel.provider_id == AIProvider.id)
                    .where(
                        AIProvider.user_id == feed.user_id,
                        AIModel.is_default == True
                    )
                ).scalar_one_or_none()
                
                if not default_model:
                    return {"success": False, "error": "请先在 AI 设置中设置默认模型"}
                
                provider = db.execute(
                    select(AIProvider).where(AIProvider.id == default_model.provider_id)
                ).scalar_one_or_none()
                
                if not provider:
                    return {"success": False, "error": "AI provider not found"}
                
                translate_prompt = user.translate_prompt if user and user.translate_prompt else None
                
                from app.services.ai_client import create_ai_client, AIClientError
                client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
                
                for article in articles:
                    title = article.title or ""
                    content = article.content or ""
                    if not title and not content:
                        continue
                    
                    try:
                        translated_title = (
                            loop.run_until_complete(client.translate(title, feed.target_language, translate_prompt))
                            if title
                            else ""
                        )
                        translated_content = (
                            loop.run_until_complete(client.translate(content, feed.target_language, translate_prompt))
                            if content
                            else ""
                        )
                        article.translation = json.dumps(
                            {"title": translated_title, "content": translated_content},
                            ensure_ascii=False,
                        )
                        db.commit()
                        translated_count += 1
                        print(f"AI translated article {article.id}: {article.title[:50]}...")
                    except AIClientError as e:
                        print(f"AI translate error for article {article.id}: {e}")
                        errors += 1
                    except Exception as e:
                        print(f"Error translating article {article.id}: {e}")
                        errors += 1
        finally:
            loop.close()
        
        return {
            "success": True,
            "translated": translated_count,
            "errors": errors,
            "total": len(articles),
            "method": translate_method
        }


@shared_task(name="app.tasks.feed_tasks.cleanup_old_articles")
def cleanup_old_articles(days: int = 90) -> dict:
    """Clean up articles older than specified days (excluding favorites)."""
    from app.models.article import UserArticle
    
    with get_sync_session() as db:
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get IDs of favorited articles
        favorited = db.execute(
            select(UserArticle.article_id).where(UserArticle.is_favorite == True)
        )
        favorited_ids = {row[0] for row in favorited.fetchall()}
        
        # Delete old articles that are not favorited
        if favorited_ids:
            old_articles = db.execute(
                select(Article).where(
                    Article.created_at < cutoff,
                    ~Article.id.in_(favorited_ids)
                )
            ).scalars().all()
        else:
            old_articles = db.execute(
                select(Article).where(Article.created_at < cutoff)
            ).scalars().all()
        
        count = len(old_articles)
        for article in old_articles:
            db.delete(article)
        
        db.commit()
        return {"success": True, "deleted": count}


@shared_task(name="app.tasks.feed_tasks.generate_article_embedding")
def generate_article_embedding(article_id: int) -> dict:
    """Generate embedding for a single article."""
    from app.models.user import User
    
    with get_sync_session() as db:
        article = db.execute(
            select(Article).where(Article.id == article_id)
        ).scalar_one_or_none()
        
        if not article:
            return {"success": False, "error": "Article not found"}
        
        if article.embedding is not None:
            return {"success": True, "message": "Embedding already exists"}
        
        # Get the feed to find the user
        feed = db.execute(
            select(Feed).where(Feed.id == article.feed_id)
        ).scalar_one_or_none()
        
        if not feed:
            return {"success": False, "error": "Feed not found"}
        
        # Get user's embedding configuration
        user = db.execute(
            select(User).where(User.id == feed.user_id)
        ).scalar_one_or_none()
        
        if not user or not user.embedding_provider_id or not user.embedding_model:
            return {"success": False, "error": "No embedding model configured"}
        
        provider = db.execute(
            select(AIProvider).where(AIProvider.id == user.embedding_provider_id)
        ).scalar_one_or_none()
        
        if not provider:
            return {"success": False, "error": "Embedding provider not found"}
        
        # Generate embedding
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.services.embedding_service import EmbeddingService
            
            service = EmbeddingService(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=user.embedding_model
            )
            
            # Combine title and content for embedding
            text = f"{article.title} {article.content or ''}"
            embedding = loop.run_until_complete(service.generate_embedding(text))
            
            if embedding:
                article.embedding = embedding
                db.commit()
                return {"success": True, "article_id": article_id}
            else:
                return {"success": False, "error": "Failed to generate embedding"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            loop.close()


@shared_task(name="app.tasks.feed_tasks.generate_embeddings_batch", bind=True)
def generate_embeddings_batch(self, user_id: int, limit: int = 500) -> dict:
    """Generate embeddings for articles without embeddings for a user.
    
    Uses batch API calls for efficiency - processes up to 50 articles per API call.
    Supports task cancellation via Celery revoke.
    """
    from app.models.user import User
    import time
    
    with get_sync_session() as db:
        # Get articles without embeddings
        articles = db.execute(
            select(Article)
            .join(Feed, Article.feed_id == Feed.id)
            .where(
                Feed.user_id == user_id,
                Article.embedding == None
            )
            .order_by(Article.created_at.desc())
            .limit(limit)
        ).scalars().all()
        
        if not articles:
            return {"success": True, "processed": 0, "message": "No articles need embeddings"}
        
        # Get user's embedding configuration
        user = db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        
        if not user or not user.embedding_provider_id or not user.embedding_model:
            return {"success": False, "error": "No embedding model configured"}
        
        provider = db.execute(
            select(AIProvider).where(AIProvider.id == user.embedding_provider_id)
        ).scalar_one_or_none()
        
        if not provider:
            return {"success": False, "error": "Embedding provider not found"}
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        processed = 0
        errors = 0
        batch_size = 50  # Process 50 articles per API call for better throughput
        total_batches = (len(articles) + batch_size - 1) // batch_size
        
        try:
            from app.services.embedding_service import EmbeddingService
            
            service = EmbeddingService(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=user.embedding_model
            )
            
            # Process in batches
            for batch_num, i in enumerate(range(0, len(articles), batch_size)):
                # Check if task was revoked/cancelled
                if self.request.id:
                    from app.tasks.celery_app import celery_app
                    # Check revoked tasks
                    revoked = celery_app.control.inspect().revoked() or {}
                    for worker_revoked in revoked.values():
                        if self.request.id in worker_revoked:
                            print(f"Task {self.request.id} was cancelled, stopping...")
                            return {
                                "success": False,
                                "cancelled": True,
                                "processed": processed,
                                "errors": errors,
                                "message": "任务已被取消"
                            }
                
                batch_articles = articles[i:i + batch_size]
                texts = [f"{a.title} {a.content or ''}" for a in batch_articles]
                
                # Generate embeddings in batch
                try:
                    embeddings = loop.run_until_complete(
                        service.batch_generate_embeddings(texts)
                    )
                    
                    # Update articles with embeddings one by one to handle errors
                    batch_processed = 0
                    for article, embedding in zip(batch_articles, embeddings):
                        if embedding:
                            try:
                                article.embedding = embedding
                                db.flush()  # Try to flush this single update
                                batch_processed += 1
                            except Exception as update_error:
                                db.rollback()  # Rollback on error
                                print(f"Error updating article {article.id}: {update_error}")
                                errors += 1
                        else:
                            errors += 1
                    
                    # Commit successful updates
                    db.commit()
                    processed += batch_processed
                    
                    # Update task state for progress tracking
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current_batch': batch_num + 1,
                            'total_batches': total_batches,
                            'processed': processed,
                            'errors': errors,
                            'total': len(articles)
                        }
                    )
                    
                    print(f"Batch {batch_num + 1}/{total_batches} completed: processed {processed}, errors {errors}")
                    
                    # Small delay between batches to avoid rate limiting
                    if batch_num < total_batches - 1:
                        time.sleep(0.5)
                        
                except Exception as batch_error:
                    db.rollback()  # Rollback on batch error
                    print(f"Error in batch {batch_num + 1}: {batch_error}")
                    errors += len(batch_articles)
                    # Continue with next batch instead of failing completely
                    continue
            
            return {
                "success": True,
                "processed": processed,
                "errors": errors,
                "total": len(articles)
            }
        except Exception as e:
            print(f"Error in batch embedding generation: {e}")
            return {"success": False, "error": str(e), "processed": processed, "errors": errors}
        finally:
            loop.close()
