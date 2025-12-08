"""Custom rule service."""
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_rule import CustomRule
from app.models.feed import Feed
from app.repositories.custom_rule_repository import CustomRuleRepository
from app.schemas.custom_rule import (
    AIGenerateRuleResponse,
    CustomRuleCreate,
    CustomRuleTestRequest,
    CustomRuleTestResult,
    CustomRuleUpdate,
)


class CustomRuleService:
    """Service for custom rule operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = CustomRuleRepository(db)

    async def create_rule(self, user_id: int, data: CustomRuleCreate) -> CustomRule:
        """Create a new custom rule with associated feed."""
        # Create a feed for this custom rule
        feed = Feed(
            user_id=user_id,
            category_id=data.category_id,
            url=data.target_url,
            title=data.name,
            description=f"自定义抓取规则: {data.name}",
            fetch_interval=data.fetch_interval,
            auto_translate=data.auto_translate,
            auto_summarize=data.auto_summarize,
            target_language=data.target_language,
            is_active=data.is_active,
        )
        self.db.add(feed)
        await self.db.flush()  # Get feed.id
        
        # Create the custom rule linked to the feed
        rule_data = data.model_dump()
        rule_data['feed_id'] = feed.id
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
                if 'target_language' in update_data:
                    feed.target_language = update_data['target_language']
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


    async def test_rule(self, data: CustomRuleTestRequest) -> CustomRuleTestResult:
        """Test a custom rule without saving it."""
        try:
            if data.use_playwright:
                # Use Playwright for JS-rendered pages
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(data.target_url, wait_until="networkidle", timeout=30000)
                    html_content = await page.content()
                    await browser.close()
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        data.target_url,
                        headers={"User-Agent": "Mozilla/5.0 RSS Reader Bot"}
                    )
                    response.raise_for_status()
                html_content = response.text
            
            soup = BeautifulSoup(html_content, "html.parser")
            items = soup.select(data.list_selector)
            
            sample_items = []
            for item in items[:5]:  # Get first 5 items as sample
                title_elem = item.select_one(data.title_selector)
                link_elem = item.select_one(data.link_selector)
                
                sample = {
                    "title": title_elem.get_text(strip=True) if title_elem else None,
                    "link": link_elem.get("href") if link_elem else None,
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
            target_language=rule.target_language,
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
            # Use Playwright for JS-rendered pages if enabled
            print(f"[CustomRule] use_playwright={rule.use_playwright} for rule {rule.id}")
            if rule.use_playwright:
                from playwright.async_api import async_playwright
                print(f"[CustomRule] Starting Playwright for {rule.target_url}")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(rule.target_url, wait_until="networkidle", timeout=30000)
                    html_content = await page.content()
                    await browser.close()
                print(f"[CustomRule] Playwright loaded {len(html_content)} bytes")
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        rule.target_url,
                        headers={"User-Agent": "Mozilla/5.0 RSS Reader Bot"}
                    )
                    response.raise_for_status()
                html_content = response.text
                print(f"[CustomRule] HTTP loaded {len(html_content)} bytes")
            
            soup = BeautifulSoup(html_content, "html.parser")
            items = soup.select(rule.list_selector)
            
            print(f"[CustomRule] Found {len(items)} items with selector: {rule.list_selector}")
            
            new_articles = []
            skipped_no_title_link = 0
            skipped_existing = 0
            
            for idx, item in enumerate(items):
                title_elem = item.select_one(rule.title_selector)
                
                # Handle link: if selector is empty or "self", use the item itself
                if not rule.link_selector or rule.link_selector.lower() in ('self', '.', 'this'):
                    link_elem = item if item.name == 'a' else item.find('a')
                else:
                    link_elem = item.select_one(rule.link_selector)
                
                # Debug first item
                if idx == 0:
                    print(f"[CustomRule] First item tag: {item.name}, has href: {item.get('href') is not None}")
                    print(f"[CustomRule] title found={title_elem is not None}, link found={link_elem is not None}")
                
                if not title_elem:
                    skipped_no_title_link += 1
                    continue
                
                # Get link from element
                if link_elem:
                    link = link_elem.get("href")
                else:
                    # Try to get href from item itself if it's an anchor
                    link = item.get("href")
                
                title = title_elem.get_text(strip=True)
                
                if not link:
                    skipped_no_title_link += 1
                    continue
                
                # Make link absolute if relative
                if link and not link.startswith("http"):
                    link = urljoin(rule.target_url, link)
                
                if not link:
                    continue
                
                # Generate guid from link
                guid = md5(link.encode()).hexdigest()
                
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
                
                content = None
                if rule.content_selector:
                    content_elem = item.select_one(rule.content_selector)
                    content = content_elem.get_text(strip=True) if content_elem else None
                
                # Create article
                article = Article(
                    feed_id=feed_id,
                    guid=guid,
                    link=link,
                    title=title,
                    content=content,
                    published_at=datetime.utcnow(),
                )
                self.db.add(article)
                new_articles.append({"title": title, "link": link, "content": content})
            
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
            rule.last_error = str(e)
            rule.error_count += 1
            if feed_id:
                result = await self.db.execute(
                    select(Feed).where(Feed.id == feed_id)
                )
                feed = result.scalar_one_or_none()
                if feed:
                    feed.last_error = str(e)
                    feed.error_count += 1
            await self.db.commit()
            raise

    async def generate_rule_with_ai(self, user_id: int, target_url: str) -> AIGenerateRuleResponse:
        """Use AI to analyze a webpage and generate CSS selectors."""
        try:
            # Use Playwright to get the page HTML (handles JS-rendered content)
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(target_url, wait_until="networkidle", timeout=30000)
                html_content = await page.content()
                page_title = await page.title()
                await browser.close()
            
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
            
            # Create AI prompt
            prompt = f"""Analyze this webpage HTML and identify the CSS selectors for a news/article list.

URL: {target_url}
Page Title: {page_title}

HTML Content:
```html
{simplified_html}
```

Please identify:
1. list_selector: CSS selector for each article/post item in the list (the repeating container element)
2. title_selector: CSS selector for the article title (relative to list item)
3. link_selector: CSS selector for the article link (relative to list item, usually an <a> tag)
4. content_selector: CSS selector for article summary/excerpt if available (relative to list item)

Respond in this exact JSON format only, no other text:
{{
    "name": "suggested name for this rule based on the website",
    "list_selector": "CSS selector for list items",
    "title_selector": "CSS selector for title",
    "link_selector": "CSS selector for link",
    "content_selector": "CSS selector for content or null if not found"
}}"""

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
                content_selector=result.get("content_selector")
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
