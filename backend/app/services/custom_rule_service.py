"""Custom rule service."""
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_rule import CustomRule
from app.repositories.custom_rule_repository import CustomRuleRepository
from app.schemas.custom_rule import (
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
