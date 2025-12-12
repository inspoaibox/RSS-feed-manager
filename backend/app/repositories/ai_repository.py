"""AI Provider and Model repository for database operations."""
from typing import List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_provider import AIModel, AIProvider


class AIProviderRepository:
    """Repository for AIProvider database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        name: str,
        type: str,
        api_key: str,
        base_url: str | None = None
    ) -> AIProvider:
        """Create a new AI provider."""
        provider = AIProvider(
            user_id=user_id,
            name=name,
            type=type,
            api_key=api_key,
            base_url=base_url
        )
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def get_by_id(self, provider_id: int, user_id: int) -> AIProvider | None:
        """Get provider by ID for a specific user."""
        result = await self.session.execute(
            select(AIProvider).where(
                AIProvider.id == provider_id,
                AIProvider.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_with_models(self, provider_id: int, user_id: int) -> AIProvider | None:
        """Get provider with models loaded."""
        result = await self.session.execute(
            select(AIProvider)
            .options(selectinload(AIProvider.models))
            .where(AIProvider.id == provider_id, AIProvider.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all_by_user(self, user_id: int) -> List[AIProvider]:
        """Get all providers for a user."""
        result = await self.session.execute(
            select(AIProvider)
            .options(selectinload(AIProvider.models))
            .where(AIProvider.user_id == user_id)
            .order_by(AIProvider.created_at)
        )
        return list(result.scalars().all())

    async def update(self, provider: AIProvider, **kwargs) -> AIProvider:
        """Update provider fields."""
        for key, value in kwargs.items():
            if hasattr(provider, key) and value is not None:
                setattr(provider, key, value)
        await self.session.flush()
        return provider

    async def delete(self, provider: AIProvider) -> None:
        """Delete a provider (cascades to models)."""
        await self.session.delete(provider)
        await self.session.flush()


class AIModelRepository:
    """Repository for AIModel database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        provider_id: int,
        model_id: str,
        name: str,
        description: str | None = None
    ) -> AIModel:
        """Create a new AI model."""
        model = AIModel(
            provider_id=provider_id,
            model_id=model_id,
            name=name,
            description=description
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def get_by_id(self, model_id: int) -> AIModel | None:
        """Get model by ID."""
        result = await self.session.execute(
            select(AIModel).where(AIModel.id == model_id)
        )
        return result.scalar_one_or_none()

    async def get_by_provider(self, provider_id: int) -> List[AIModel]:
        """Get all models for a provider."""
        result = await self.session.execute(
            select(AIModel)
            .where(AIModel.provider_id == provider_id)
            .order_by(AIModel.name)
        )
        return list(result.scalars().all())

    async def get_default_model(self, user_id: int) -> AIModel | None:
        """Get the default model for a user."""
        result = await self.session.execute(
            select(AIModel)
            .join(AIProvider, AIModel.provider_id == AIProvider.id)
            .where(AIProvider.user_id == user_id, AIModel.is_default == True)
        )
        return result.scalar_one_or_none()

    async def set_default(self, user_id: int, model_id: int) -> None:
        """Set a model as default (clears other defaults)."""
        # Clear all defaults for user
        await self.session.execute(
            update(AIModel)
            .where(
                AIModel.provider_id.in_(
                    select(AIProvider.id).where(AIProvider.user_id == user_id)
                )
            )
            .values(is_default=False)
        )
        
        # Set new default
        await self.session.execute(
            update(AIModel)
            .where(AIModel.id == model_id)
            .values(is_default=True)
        )
        await self.session.flush()

    async def clear_defaults_for_user(self, user_id: int) -> None:
        """Clear all default models for a user."""
        await self.session.execute(
            update(AIModel)
            .where(
                AIModel.provider_id.in_(
                    select(AIProvider.id).where(AIProvider.user_id == user_id)
                )
            )
            .values(is_default=False)
        )
        await self.session.flush()

    async def update(self, model: AIModel, **kwargs) -> AIModel:
        """Update model fields."""
        for key, value in kwargs.items():
            if hasattr(model, key) and value is not None:
                setattr(model, key, value)
        await self.session.flush()
        return model

    async def delete(self, model: AIModel) -> None:
        """Delete a model."""
        await self.session.delete(model)
        await self.session.flush()

    async def bulk_create(self, provider_id: int, models: List[dict]) -> List[AIModel]:
        """Bulk create models for a provider, skipping duplicates."""
        # Get existing model_ids for this provider
        existing_query = select(AIModel.model_id).where(AIModel.provider_id == provider_id)
        result = await self.session.execute(existing_query)
        existing_model_ids = {row[0] for row in result.fetchall()}
        
        created = []
        for m in models:
            model_id = m["model_id"]
            # Skip if model already exists
            if model_id in existing_model_ids:
                continue
            
            model = AIModel(
                provider_id=provider_id,
                model_id=model_id,
                name=m.get("name", model_id)
            )
            self.session.add(model)
            created.append(model)
            existing_model_ids.add(model_id)  # Prevent duplicates within same batch
        
        if created:
            await self.session.flush()
        return created
