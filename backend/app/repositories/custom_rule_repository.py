"""Custom rule repository."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_rule import CustomRule


class CustomRuleRepository:
    """Repository for custom rule operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, **kwargs) -> CustomRule:
        """Create a new custom rule."""
        rule = CustomRule(user_id=user_id, **kwargs)
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def get_by_id(self, rule_id: int, user_id: int) -> CustomRule | None:
        """Get a custom rule by ID for a specific user."""
        result = await self.db.execute(
            select(CustomRule).where(
                CustomRule.id == rule_id,
                CustomRule.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_all_by_user(self, user_id: int) -> list[CustomRule]:
        """Get all custom rules for a user."""
        result = await self.db.execute(
            select(CustomRule)
            .where(CustomRule.user_id == user_id)
            .order_by(CustomRule.name)
        )
        return list(result.scalars().all())

    async def get_active_rules(self, user_id: int | None = None) -> list[CustomRule]:
        """Get all active custom rules, optionally filtered by user."""
        query = select(CustomRule).where(CustomRule.is_active == True)
        if user_id:
            query = query.where(CustomRule.user_id == user_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_rules_due_for_fetch(self) -> list[CustomRule]:
        """Get rules that are due for fetching."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(CustomRule).where(
                CustomRule.is_active == True,
                (CustomRule.last_fetched_at == None) | 
                (CustomRule.last_fetched_at + CustomRule.fetch_interval <= now)
            )
        )
        return list(result.scalars().all())
