"""Custom rule service."""
import json
from datetime import datetime
from hashlib import md5
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.custom_rule import CustomRule
from app.models.feed import Feed
from app.repositories.custom_rule_repository import CustomRuleRepository
from app.repositories.keyword_subscription_repository import KeywordSubscriptionRepository
from app.repositories.proxy_pool_repository import ProxyPoolRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.schemas.custom_rule import (
    AIGenerateRuleResponse,
    CustomRuleCreate,
    CustomRuleTestRequest,
    CustomRuleTestResult,
    CustomRuleUpdate,
)
from app.services.browser_fetch_settings import load_browser_fetch_settings
from app.utils.feed_parser import _apply_browser_resource_blocking, _build_playwright_proxy
from app.utils.whmcs_monitor import (
    build_whmcs_status_content,
    extract_whmcs_status_from_content,
    parse_whmcs_product_state,
)


# 默认的同步间隔选项（秒）
DEFAULT_SYNC_INTERVALS = [300, 900, 1800, 3600, 7200, 14400, 43200, 86400]


class CustomRuleService:
    """Service for custom rule operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = CustomRuleRepository(db)
        self.keyword_repo = KeywordSubscriptionRepository(db)
        self.proxy_repo = ProxyPoolRepository(db)
        self.settings_repo = SystemSettingsRepository(db)

    def _normalize_proxy_config(
        self,
        proxy_mode: str | None,
        proxy_enabled: bool | None,
        proxy_url: str | None,
        proxy_pool_country: str | None = None,
        proxy_pool_protocol: str | None = None,
    ) -> tuple[str, bool, str | None, str | None, str | None]:
        """Normalize and validate per-rule proxy settings."""
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

    async def _fetch_html(
        self,
        url: str,
        use_playwright: bool,
        cookies_dict: dict[str, str],
        proxy_url: str | None = None,
    ) -> str:
        """Fetch custom-rule target HTML with optional proxy support."""
        if use_playwright:
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise RuntimeError(
                    "Playwright runtime is not installed in the API image. "
                    "Enable the browser worker/profile for browser-backed fetching."
                ) from exc

            from app.core.config import settings as app_settings

            browser_settings = await load_browser_fetch_settings(self.settings_repo)
            launch_kwargs = {
                "headless": app_settings.FEED_BROWSER_HEADLESS,
                "args": [
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            }
            playwright_proxy = _build_playwright_proxy(proxy_url)
            if playwright_proxy:
                launch_kwargs["proxy"] = playwright_proxy

            browser = None
            context = None
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(**launch_kwargs)
                    context = await browser.new_context(
                        user_agent=browser_settings.user_agent,
                        viewport={
                            "width": browser_settings.viewport_width,
                            "height": browser_settings.viewport_height,
                        },
                        locale="en-US",
                        extra_http_headers={
                            "Accept-Language": "en-US,en;q=0.9",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        },
                    )
                    if cookies_dict:
                        host = urlparse(url).hostname or ""
                        cookie_list = [
                            {"name": key, "value": value, "domain": host, "path": "/"}
                            for key, value in cookies_dict.items()
                        ]
                        await context.add_cookies(cookie_list)
                    await _apply_browser_resource_blocking(context, browser_settings)
                    page = await context.new_page()
                    await page.goto(
                        url,
                        wait_until=browser_settings.playwright_wait_until,
                        timeout=browser_settings.playwright_timeout_seconds * 1000,
                    )
                    return await page.content()
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        async with httpx.AsyncClient(
            timeout=30.0,
            cookies=cookies_dict if cookies_dict else None,
            proxy=proxy_url,
            follow_redirects=True,
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        return response.text

    async def _fetch_html_with_proxy(
        self,
        user_id: int,
        url: str,
        use_playwright: bool,
        cookies_dict: dict[str, str],
        proxy_mode: str,
        proxy_url: str | None,
        proxy_pool_country: str | None,
        proxy_pool_protocol: str | None,
    ) -> str:
        """Fetch target HTML, rotating through proxy pool candidates when configured."""
        if proxy_mode == "pool":
            candidates = await self.proxy_repo.get_candidates(
                user_id,
                country=proxy_pool_country,
                protocol=proxy_pool_protocol,
            )
            if not candidates:
                raise RuntimeError("代理池没有可用代理")

            last_error = ""
            for proxy in candidates:
                try:
                    html = await self._fetch_html(
                        url,
                        use_playwright,
                        cookies_dict,
                        proxy_url=proxy.proxy_url,
                    )
                    await self.proxy_repo.record_success(proxy)
                    await self.db.commit()
                    return html
                except Exception as exc:
                    last_error = str(exc)
                    await self.proxy_repo.record_failure(proxy, last_error)
                    await self.db.commit()

            raise RuntimeError(f"代理池全部失败: {last_error or '未知错误'}")

        return await self._fetch_html(
            url,
            use_playwright,
            cookies_dict,
            proxy_url=proxy_url if proxy_mode == "single" else None,
        )

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

    async def _get_latest_whmcs_status(self, feed_id: int) -> str | None:
        result = await self.db.execute(
            select(Article)
            .where(Article.feed_id == feed_id, Article.guid.like("whmcs:%"))
            .order_by(desc(Article.published_at), desc(Article.id))
            .limit(1)
        )
        article = result.scalar_one_or_none()
        return extract_whmcs_status_from_content(article.content if article else None)

    async def _save_whmcs_status_article(
        self,
        rule: CustomRule,
        feed_id: int,
        html_content: str,
    ) -> list[dict]:
        state = parse_whmcs_product_state(html_content, rule.target_url)
        previous_status = await self._get_latest_whmcs_status(feed_id)
        if previous_status == state.status:
            return []

        now = datetime.utcnow()
        title_prefix = "上架" if state.status == "in_stock" else "下架"
        content = build_whmcs_status_content(state, rule.target_url)
        guid = "whmcs:" + md5(
            f"{rule.target_url}|{state.status}|{now.isoformat()}".encode()
        ).hexdigest()
        article = Article(
            feed_id=feed_id,
            guid=guid,
            link=rule.target_url,
            title=f"[{title_prefix}] {state.title}",
            content=content,
            published_at=now,
        )
        self.db.add(article)
        await self.db.flush()
        await self.keyword_repo.sync_article_matches(rule.user_id, [article.id])
        return [{"title": article.title, "link": article.link, "content": content, "article_id": article.id}]

    async def create_rule(self, user_id: int, data: CustomRuleCreate) -> CustomRule:
        """Create a new custom rule with associated feed."""
        # Validate fetch interval
        validated_interval = await self._validate_fetch_interval(data.fetch_interval)
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
        
        # Create a feed for this custom rule
        feed = Feed(
            user_id=user_id,
            category_id=data.category_id,
            url=data.target_url,
            title=data.name,
            description=f"自定义抓取规则: {data.name}",
            fetch_interval=validated_interval,
            auto_translate=data.auto_translate,
            auto_summarize=data.auto_summarize,
            source_language=data.source_language,
            target_language=data.target_language,
            translate_method=data.translate_method,
            translate_title=data.translate_title,
            translate_content=data.translate_content,
            use_playwright=data.use_playwright,
            browser_engine="playwright" if data.use_playwright else "http",
            proxy_mode=proxy_mode,
            proxy_enabled=proxy_enabled,
            proxy_url=proxy_url,
            proxy_pool_country=proxy_pool_country,
            proxy_pool_protocol=proxy_pool_protocol,
            is_active=data.is_active,
        )
        self.db.add(feed)
        await self.db.flush()  # Get feed.id
        
        # Create the custom rule linked to the feed
        rule_data = data.model_dump()
        rule_data['feed_id'] = feed.id
        rule_data["fetch_interval"] = validated_interval
        rule_data["proxy_mode"] = proxy_mode
        rule_data["proxy_enabled"] = proxy_enabled
        rule_data["proxy_url"] = proxy_url
        rule_data["proxy_pool_country"] = proxy_pool_country
        rule_data["proxy_pool_protocol"] = proxy_pool_protocol
        return await self.repository.create(user_id=user_id, **rule_data)

    async def get_rule(self, rule_id: int, user_id: int) -> CustomRule | None:
        """Get a custom rule by ID."""
        return await self.repository.get_by_id(rule_id, user_id)

    async def get_user_rules(self, user_id: int) -> list[CustomRule]:
        """Get all rules for a user."""
        return await self.repository.get_all_by_user(user_id)

    async def update_rule(
        self, rule_id: int, user_id: int, data: CustomRuleUpdate
    ) -> CustomRule | None:
        """Update a custom rule and its associated feed."""
        rule = await self.repository.get_by_id(rule_id, user_id)
        if not rule:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        
        # Validate fetch interval if provided
        if 'fetch_interval' in update_data:
            update_data['fetch_interval'] = await self._validate_fetch_interval(update_data['fetch_interval'])

        if any(
            key in update_data
            for key in (
                "proxy_mode",
                "proxy_enabled",
                "proxy_url",
                "proxy_pool_country",
                "proxy_pool_protocol",
            )
        ):
            (
                proxy_mode,
                proxy_enabled,
                proxy_url,
                proxy_pool_country,
                proxy_pool_protocol,
            ) = self._normalize_proxy_config(
                update_data.get("proxy_mode", getattr(rule, "proxy_mode", None)),
                update_data.get("proxy_enabled", getattr(rule, "proxy_enabled", False)),
                update_data.get("proxy_url", getattr(rule, "proxy_url", None)),
                update_data.get("proxy_pool_country", getattr(rule, "proxy_pool_country", None)),
                update_data.get("proxy_pool_protocol", getattr(rule, "proxy_pool_protocol", None)),
            )
            update_data["proxy_mode"] = proxy_mode
            update_data["proxy_enabled"] = proxy_enabled
            update_data["proxy_url"] = proxy_url
            update_data["proxy_pool_country"] = proxy_pool_country
            update_data["proxy_pool_protocol"] = proxy_pool_protocol
        
        for key, value in update_data.items():
            setattr(rule, key, value)
        
        # Sync updates to associated feed
        if rule.feed_id:
            from sqlalchemy import select
            result = await self.db.execute(
                select(Feed).where(Feed.id == rule.feed_id)
            )
            feed = result.scalar_one_or_none()
            if feed:
                if 'name' in update_data:
                    feed.title = update_data['name']
                if 'target_url' in update_data:
                    feed.url = update_data['target_url']
                if 'category_id' in update_data:
                    feed.category_id = update_data['category_id']
                if 'fetch_interval' in update_data:
                    feed.fetch_interval = update_data['fetch_interval']
                if 'auto_translate' in update_data:
                    feed.auto_translate = update_data['auto_translate']
                if 'auto_summarize' in update_data:
                    feed.auto_summarize = update_data['auto_summarize']
                if 'source_language' in update_data:
                    feed.source_language = update_data['source_language']
                if 'target_language' in update_data:
                    feed.target_language = update_data['target_language']
                if 'translate_method' in update_data:
                    feed.translate_method = update_data['translate_method']
                if 'translate_title' in update_data:
                    feed.translate_title = update_data['translate_title']
                if 'translate_content' in update_data:
                    feed.translate_content = update_data['translate_content']
                if 'proxy_mode' in update_data:
                    feed.proxy_mode = update_data['proxy_mode']
                if 'proxy_enabled' in update_data:
                    feed.proxy_enabled = update_data['proxy_enabled']
                if 'proxy_url' in update_data:
                    feed.proxy_url = update_data['proxy_url']
                if 'proxy_pool_country' in update_data:
                    feed.proxy_pool_country = update_data['proxy_pool_country']
                if 'proxy_pool_protocol' in update_data:
                    feed.proxy_pool_protocol = update_data['proxy_pool_protocol']
                if 'is_active' in update_data:
                    feed.is_active = update_data['is_active']
        
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def delete_rule(self, rule_id: int, user_id: int) -> bool:
        """Delete a custom rule and its associated feed."""
        rule = await self.repository.get_by_id(rule_id, user_id)
        if not rule:
            return False
        
        # Delete associated feed (will cascade delete articles)
        if rule.feed_id:
            from sqlalchemy import select
            result = await self.db.execute(
                select(Feed).where(Feed.id == rule.feed_id)
            )
            feed = result.scalar_one_or_none()
            if feed:
                await self.db.delete(feed)
        
        await self.db.delete(rule)
        await self.db.commit()
        return True


    async def test_rule(self, user_id: int, data: CustomRuleTestRequest) -> CustomRuleTestResult:
        """Test a custom rule without saving it."""
        try:
            (
                proxy_mode,
                _proxy_enabled,
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
            html_content = await self._fetch_html_with_proxy(
                user_id,
                data.target_url,
                data.use_playwright,
                {},
                proxy_mode,
                proxy_url,
                proxy_pool_country,
                proxy_pool_protocol,
            )
            
            soup = BeautifulSoup(html_content, "html.parser")
            items = soup.select(data.list_selector)
            
            sample_items = []
            for item in items[:5]:  # Get first 5 items as sample
                title_elem = item.select_one(data.title_selector)
                
                # Handle link selector - same logic as execute_rule
                if not data.link_selector or data.link_selector.lower() in ('self', '.', 'this'):
                    link_elem = item if item.name == 'a' else item.find('a')
                else:
                    link_elem = item.select_one(data.link_selector)
                
                # Get link - if link_elem is the <a> tag itself, get href directly
                link = None
                if link_elem:
                    link = link_elem.get("href")
                    # If no href on selected element, try to find <a> inside it
                    if not link and link_elem.name != 'a':
                        inner_a = link_elem.find('a')
                        if inner_a:
                            link = inner_a.get('href')
                
                sample = {
                    "title": title_elem.get_text(strip=True) if title_elem else None,
                    "link": link,
                }
                
                if data.content_selector:
                    content_elem = item.select_one(data.content_selector)
                    sample["content"] = content_elem.get_text(strip=True)[:200] if content_elem else None
                
                if data.date_selector:
                    date_elem = item.select_one(data.date_selector)
                    sample["date"] = date_elem.get_text(strip=True) if date_elem else None
                
                sample_items.append(sample)
            
            return CustomRuleTestResult(
                success=True,
                items_found=len(items),
                sample_items=sample_items
            )
        except Exception as e:
            return CustomRuleTestResult(
                success=False,
                items_found=0,
                sample_items=[],
                error=str(e)
            )

    async def _ensure_feed_for_rule(self, rule: CustomRule) -> int:
        """Ensure rule has an associated feed, create one if missing."""
        if rule.feed_id:
            return rule.feed_id
        
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
            source_language=getattr(rule, 'source_language', None),
            target_language=rule.target_language,
            translate_method=getattr(rule, 'translate_method', 'none'),
            translate_title=getattr(rule, 'translate_title', True),
            translate_content=getattr(rule, 'translate_content', False),
            proxy_enabled=getattr(rule, "proxy_enabled", False),
            proxy_url=getattr(rule, "proxy_url", None),
            proxy_mode=getattr(
                rule,
                "proxy_mode",
                "single" if getattr(rule, "proxy_enabled", False) else "none",
            ),
            proxy_pool_country=getattr(rule, "proxy_pool_country", None),
            proxy_pool_protocol=getattr(rule, "proxy_pool_protocol", None),
            is_active=rule.is_active,
        )
        self.db.add(feed)
        await self.db.flush()
        
        rule.feed_id = feed.id
        await self.db.commit()
        return feed.id

    async def execute_rule(self, rule: CustomRule) -> list[dict]:
        """Execute a custom rule and save articles to associated feed."""
        from urllib.parse import urljoin
        from hashlib import md5
        from sqlalchemy import select
        from app.models.article import Article
        
        # Ensure rule has associated feed
        feed_id = await self._ensure_feed_for_rule(rule)
        
        try:
            # Parse cookies if provided
            cookies_dict = {}
            if hasattr(rule, 'cookies') and rule.cookies:
                for item in rule.cookies.split(';'):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        cookies_dict[key.strip()] = value.strip()

            proxy_mode = getattr(
                rule,
                "proxy_mode",
                "single" if getattr(rule, "proxy_enabled", False) else "none",
            )
            print(f"[CustomRule] use_playwright={rule.use_playwright} for rule {rule.id}")
            print(f"[CustomRule] proxy_mode={proxy_mode} for rule {rule.id}")
            html_content = await self._fetch_html_with_proxy(
                rule.user_id,
                rule.target_url,
                rule.use_playwright,
                cookies_dict,
                proxy_mode,
                getattr(rule, "proxy_url", None),
                getattr(rule, "proxy_pool_country", None),
                getattr(rule, "proxy_pool_protocol", None),
            )
            print(f"[CustomRule] Loaded {len(html_content)} bytes")
            
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Use specialized parser for telegram
            rule_type = getattr(rule, 'rule_type', 'general') or 'general'
            print(f"[CustomRule] rule_type={rule_type}")

            if rule_type == 'whmcs':
                new_articles = await self._save_whmcs_status_article(rule, feed_id, html_content)
                now = datetime.utcnow()
                rule.last_fetched_at = now
                rule.last_error = None
                rule.error_count = 0

                result = await self.db.execute(
                    select(Feed).where(Feed.id == feed_id)
                )
                feed = result.scalar_one_or_none()
                if feed:
                    feed.title = parse_whmcs_product_state(html_content, rule.target_url).title
                    feed.last_fetched_at = now
                    feed.last_error = None
                    feed.error_count = 0

                await self.db.commit()
                for article in new_articles:
                    article_id = article.get("article_id")
                    if article_id:
                        try:
                            from app.tasks.feed_tasks import trigger_push_for_article

                            trigger_push_for_article.delay(article_id)
                        except Exception:
                            pass
                return new_articles
            
            if rule_type == 'telegram':
                items = soup.select('.tgme_widget_message_wrap')
            elif rule_type == 'twitter':
                items = soup.select('.timeline-item')
            else:
                items = soup.select(rule.list_selector)
            
            print(f"[CustomRule] Found {len(items)} items")
            
            new_articles = []
            new_article_ids: list[int] = []
            skipped_no_title_link = 0
            skipped_existing = 0
            
            for idx, item in enumerate(items):
                title = None
                link = None
                content = None
                
                published_at = None
                
                if rule_type == 'telegram':
                    # Telegram-specific parsing
                    text_elem = item.select_one('.tgme_widget_message_text')
                    if text_elem:
                        content = str(text_elem)  # Keep HTML
                        # Use first 100 chars as title
                        title = text_elem.get_text(strip=True)[:100]
                        if len(text_elem.get_text(strip=True)) > 100:
                            title += '...'
                    
                    # Get message link
                    link_elem = item.select_one('.tgme_widget_message_date')
                    if link_elem:
                        link = link_elem.get('href')
                    
                    # Get published time from <time datetime="...">
                    time_elem = item.select_one('time[datetime]')
                    if time_elem:
                        try:
                            from dateutil import parser as date_parser
                            published_at = date_parser.parse(time_elem.get('datetime'))
                        except:
                            pass
                    
                    # If no text, try to get photo/video caption or skip
                    if not title:
                        # Check for forwarded message or media
                        fwd = item.select_one('.tgme_widget_message_forwarded_from')
                        if fwd:
                            title = f"[转发] {fwd.get_text(strip=True)}"
                        else:
                            skipped_no_title_link += 1
                            continue
                
                elif rule_type == 'twitter':
                    # Twitter/Nitter-specific parsing
                    text_elem = item.select_one('.tweet-content')
                    if text_elem:
                        content = str(text_elem)
                        title = text_elem.get_text(strip=True)[:100]
                        if len(text_elem.get_text(strip=True)) > 100:
                            title += '...'
                    
                    # Get tweet link
                    link_elem = item.select_one('.tweet-link')
                    if link_elem:
                        link = link_elem.get('href')
                        if link and not link.startswith('http'):
                            link = urljoin(rule.target_url, link)
                    
                    # Get published time
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
                    
                    # Handle link: if selector is empty or "self", use the item itself
                    if not rule.link_selector or rule.link_selector.lower() in ('self', '.', 'this'):
                        link_elem = item if item.name == 'a' else item.find('a')
                    else:
                        link_elem = item.select_one(rule.link_selector)
                    
                    # Get link - if link_elem is the <a> tag itself, get href directly
                    if link_elem:
                        link = link_elem.get("href")
                        # If no href on selected element, try to find <a> inside it
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
                
                # Make link absolute if relative
                if link and not link.startswith("http"):
                    link = urljoin(rule.target_url, link)
                
                # Generate guid - use link if available, otherwise use title hash
                if link:
                    guid = md5(link.encode()).hexdigest()
                else:
                    guid = md5(title.encode()).hexdigest()
                
                # Debug first item
                if idx == 0:
                    print(f"[CustomRule] First item: title={title[:50]}..., link={link}, guid={guid[:8]}")
                
                # Check if article already exists
                existing = await self.db.execute(
                    select(Article).where(
                        Article.feed_id == feed_id,
                        Article.guid == guid
                    )
                )
                if existing.scalar_one_or_none():
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
                self.db.add(article)
                await self.db.flush()
                new_article_ids.append(article.id)
                new_articles.append({"title": title, "link": link, "content": content})

            await self.keyword_repo.sync_article_matches(rule.user_id, new_article_ids)
            
            print(f"[CustomRule] Skipped {skipped_no_title_link} (no title/link), {skipped_existing} (existing), added {len(new_articles)} new")
            
            # Update rule and feed status
            now = datetime.utcnow()
            rule.last_fetched_at = now
            rule.last_error = None
            rule.error_count = 0
            
            # Update feed status too
            result = await self.db.execute(
                select(Feed).where(Feed.id == feed_id)
            )
            feed = result.scalar_one_or_none()
            if feed:
                feed.last_fetched_at = now
                feed.last_error = None
                feed.error_count = 0
            
            await self.db.commit()
            
            return new_articles
        except Exception as e:
            now = datetime.utcnow()
            rule.last_fetched_at = now
            rule.last_error = str(e)[:500]
            rule.error_count += 1
            if feed_id:
                result = await self.db.execute(
                    select(Feed).where(Feed.id == feed_id)
                )
                feed = result.scalar_one_or_none()
                if feed:
                    feed.last_fetched_at = now
                    feed.last_error = str(e)[:500]
                    feed.error_count += 1
            await self.db.commit()
            raise

    def get_default_generate_prompt(self) -> str:
        """Get the default prompt template for AI rule generation."""
        return """分析这个网页 HTML，识别新闻/文章列表的 CSS 选择器。

URL: {target_url}
页面标题: {page_title}

HTML 内容:
```html
{html_content}
```

请识别以下选择器：

1. list_selector: 文章列表项的选择器（重复出现的容器元素，每个元素代表一篇文章）
   - 通常是 article, li, div, 或带有特定 class 的元素
   - 选择器应该能匹配到多个列表项

2. title_selector: 标题选择器（相对于列表项内部）
   - 通常是 h1, h2, h3, 或带有 title/heading class 的元素
   - 这个选择器是在列表项内部查找的

3. link_selector: 链接选择器（相对于列表项内部）
   - 重要：如果列表项本身就是 <a> 标签，请填写 "self"
   - 如果链接是列表项内部的 <a> 标签，填写 "a" 或具体的选择器
   - 这个选择器用于获取文章的 href 链接

4. content_selector: 摘要/内容选择器（可选，相对于列表项内部）
   - 如果列表页有文章摘要，填写对应选择器
   - 如果没有摘要，填写 null

5. date_selector: 时间/日期选择器（可选，相对于列表项内部）
   - 如果列表页有发布时间，填写对应选择器
   - 通常是 time, span, 或带有 date/time class 的元素
   - 如果没有时间信息，填写 null

注意事项：
- 优先使用简单的 class 选择器，避免过于复杂的选择器
- 如果 class 名包含动态 hash（如 xxx__abc123），仍然可以使用，但要确保完整
- title_selector 和 link_selector 是相对于 list_selector 匹配的元素内部查找的

只返回 JSON 格式，不要其他文字：
{{
    "name": "根据网站建议的规则名称",
    "list_selector": "列表项选择器",
    "title_selector": "标题选择器",
    "link_selector": "链接选择器，如果列表项本身是a标签则填self",
    "content_selector": "内容选择器或null",
    "date_selector": "时间选择器或null"
}}"""

    async def generate_rule_with_ai(self, user_id: int, target_url: str, custom_prompt: str | None = None) -> AIGenerateRuleResponse:
        """Use AI to analyze a webpage and generate CSS selectors."""
        try:
            # Use Playwright to get the page HTML (handles JS-rendered content)
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise RuntimeError(
                    "Playwright runtime is not installed in the API image. "
                    "Run rule generation from a browser-enabled deployment."
                ) from exc
            
            browser = None
            context = None
            try:
                from app.core.config import settings as app_settings

                browser_settings = await load_browser_fetch_settings(self.settings_repo)
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=app_settings.FEED_BROWSER_HEADLESS,
                        args=[
                            "--disable-dev-shm-usage",
                            "--no-sandbox",
                        ],
                    )
                    context = await browser.new_context(
                        user_agent=browser_settings.user_agent,
                        viewport={
                            "width": browser_settings.viewport_width,
                            "height": browser_settings.viewport_height,
                        },
                        locale="en-US",
                    )
                    await _apply_browser_resource_blocking(context, browser_settings)
                    page = await context.new_page()
                    await page.goto(
                        target_url,
                        wait_until=browser_settings.playwright_wait_until,
                        timeout=browser_settings.playwright_timeout_seconds * 1000,
                    )
                    html_content = await page.content()
                    page_title = await page.title()
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass
            
            # Parse and simplify HTML for AI
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Remove scripts, styles, and other non-content elements
            for tag in soup(["script", "style", "meta", "link", "noscript", "svg", "path"]):
                tag.decompose()
            
            # Get simplified HTML structure (limit size for AI)
            body = soup.find("body")
            if body:
                simplified_html = str(body)[:15000]  # Limit to ~15KB
            else:
                simplified_html = str(soup)[:15000]
            
            # Get AI model
            from app.repositories.ai_repository import AIModelRepository, AIProviderRepository
            model_repo = AIModelRepository(self.db)
            provider_repo = AIProviderRepository(self.db)
            default_model = await model_repo.get_default_model(user_id)
            
            if not default_model:
                return AIGenerateRuleResponse(
                    success=False,
                    error="No default AI model configured. Please configure AI settings first."
                )
            
            provider = await provider_repo.get_by_id(default_model.provider_id, user_id)
            if not provider:
                return AIGenerateRuleResponse(
                    success=False,
                    error="AI provider not found"
                )
            
            # Use custom prompt or default
            prompt_template = custom_prompt if custom_prompt else self.get_default_generate_prompt()
            prompt = prompt_template.format(
                target_url=target_url,
                page_title=page_title,
                html_content=simplified_html
            )

            # Call AI
            from app.services.ai_client import create_ai_client, AIClientError
            client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
            
            response = await client.chat(prompt)
            
            # Parse AI response
            import json
            import re
            
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if not json_match:
                return AIGenerateRuleResponse(
                    success=False,
                    error="AI response did not contain valid JSON"
                )
            
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                return AIGenerateRuleResponse(
                    success=False,
                    error="Failed to parse AI response as JSON"
                )
            
            return AIGenerateRuleResponse(
                success=True,
                name=result.get("name"),
                list_selector=result.get("list_selector"),
                title_selector=result.get("title_selector"),
                link_selector=result.get("link_selector"),
                content_selector=result.get("content_selector"),
                date_selector=result.get("date_selector")
            )
            
        except AIClientError as e:
            return AIGenerateRuleResponse(
                success=False,
                error=f"AI error: {str(e)}"
            )
        except Exception as e:
            return AIGenerateRuleResponse(
                success=False,
                error=f"Failed to analyze page: {str(e)}"
            )
