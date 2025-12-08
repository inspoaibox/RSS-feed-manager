"""Custom rule service."""
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_rule import CustomRule
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
        """Create a new custom rule."""
        return await self.repository.create(
            user_id=user_id,
            **data.model_dump()
        )

    async def get_rule(self, rule_id: int, user_id: int) -> CustomRule | None:
        """Get a custom rule by ID."""
        return await self.repository.get_by_id(rule_id, user_id)

    async def get_user_rules(self, user_id: int) -> list[CustomRule]:
        """Get all rules for a user."""
        return await self.repository.get_all_by_user(user_id)

    async def update_rule(
        self, rule_id: int, user_id: int, data: CustomRuleUpdate
    ) -> CustomRule | None:
        """Update a custom rule."""
        rule = await self.repository.get_by_id(rule_id, user_id)
        if not rule:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(rule, key, value)
        
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def delete_rule(self, rule_id: int, user_id: int) -> bool:
        """Delete a custom rule."""
        rule = await self.repository.get_by_id(rule_id, user_id)
        if not rule:
            return False
        
        await self.db.delete(rule)
        await self.db.commit()
        return True


    async def test_rule(self, data: CustomRuleTestRequest) -> CustomRuleTestResult:
        """Test a custom rule without saving it."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    data.target_url,
                    headers={"User-Agent": "Mozilla/5.0 RSS Reader Bot"}
                )
                response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
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

    async def execute_rule(self, rule: CustomRule) -> list[dict]:
        """Execute a custom rule and return extracted articles."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    rule.target_url,
                    headers={"User-Agent": "Mozilla/5.0 RSS Reader Bot"}
                )
                response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select(rule.list_selector)
            
            articles = []
            for item in items:
                title_elem = item.select_one(rule.title_selector)
                link_elem = item.select_one(rule.link_selector)
                
                if not title_elem or not link_elem:
                    continue
                
                article = {
                    "title": title_elem.get_text(strip=True),
                    "link": link_elem.get("href"),
                    "content": None,
                    "published_at": None,
                }
                
                # Make link absolute if relative
                if article["link"] and not article["link"].startswith("http"):
                    from urllib.parse import urljoin
                    article["link"] = urljoin(rule.target_url, article["link"])
                
                if rule.content_selector:
                    content_elem = item.select_one(rule.content_selector)
                    article["content"] = content_elem.get_text(strip=True) if content_elem else None
                
                articles.append(article)
            
            # Update rule status
            rule.last_fetched_at = datetime.utcnow()
            rule.last_error = None
            rule.error_count = 0
            await self.db.commit()
            
            return articles
        except Exception as e:
            rule.last_error = str(e)
            rule.error_count += 1
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
