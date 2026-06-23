"""AI service for managing providers, models, and AI operations."""
from datetime import datetime
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_provider import AIModel, AIProvider
from app.repositories.ai_repository import AIModelRepository, AIProviderRepository
from app.repositories.article_repository import ArticleRepository
from app.schemas.ai import (
    AIModelCreate,
    AIModelResponse,
    AIModelUpdate,
    AIProviderCreate,
    AIProviderResponse,
    AIProviderUpdate,
)
from app.services.ai_client import AIClientError, create_ai_client


class AIService:
    """Service for AI operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.provider_repo = AIProviderRepository(session)
        self.model_repo = AIModelRepository(session)
        self.article_repo = ArticleRepository(session)

    # Provider operations
    async def create_provider(self, user_id: int, data: AIProviderCreate) -> AIProviderResponse:
        """Create a new AI provider."""
        provider = await self.provider_repo.create(
            user_id=user_id,
            name=data.name,
            type=data.type,
            api_key=data.api_key,
            base_url=data.base_url
        )

        provider = await self.provider_repo.get_with_models(provider.id, user_id)
        return self._provider_to_response(provider)

    async def get_providers(self, user_id: int) -> List[AIProviderResponse]:
        """Get all providers for a user."""
        providers = await self.provider_repo.get_all_by_user(user_id)
        return [self._provider_to_response(p) for p in providers]

    async def get_provider(self, user_id: int, provider_id: int) -> AIProviderResponse:
        """Get a provider by ID."""
        provider = await self.provider_repo.get_with_models(provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        return self._provider_to_response(provider)

    async def update_provider(
        self, user_id: int, provider_id: int, data: AIProviderUpdate
    ) -> AIProviderResponse:
        """Update a provider."""
        provider = await self.provider_repo.get_by_id(provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        
        update_data = data.model_dump(exclude_unset=True)
        provider = await self.provider_repo.update(provider, **update_data)
        provider = await self.provider_repo.get_with_models(provider_id, user_id)
        return self._provider_to_response(provider)

    async def delete_provider(self, user_id: int, provider_id: int) -> None:
        """Delete a provider."""
        provider = await self.provider_repo.get_by_id(provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        
        # Check if any model is default
        default_model = await self.model_repo.get_default_model(user_id)
        if default_model and default_model.provider_id == provider_id:
            await self.model_repo.clear_defaults_for_user(user_id)
        
        await self.provider_repo.delete(provider)

    async def test_provider(self, user_id: int, provider_id: int) -> dict:
        """Test provider connection."""
        provider = await self.provider_repo.get_by_id(provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        
        try:
            client = create_ai_client(provider.type, provider.api_key, provider.base_url)
            success = await client.test_connection()
            return {"success": success, "message": "Connection successful" if success else "Connection failed"}
        except (AIClientError, ValueError) as e:
            return {"success": False, "message": str(e)}

    async def fetch_models(self, user_id: int, provider_id: int) -> List[AIModelResponse]:
        """Fetch available models from provider and save them."""
        provider = await self.provider_repo.get_by_id(provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        
        try:
            client = create_ai_client(provider.type, provider.api_key, provider.base_url)
            models = await client.list_models()
            if models:
                await self.model_repo.bulk_create(provider_id, models)
            
            # Return updated models
            all_models = await self.model_repo.get_by_provider(provider_id)
            return [self._model_to_response(m) for m in all_models]
        except (AIClientError, ValueError) as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    # Model operations
    async def get_models(self, user_id: int, provider_id: int) -> List[AIModelResponse]:
        """Get all models for a provider."""
        provider = await self.provider_repo.get_by_id(provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        
        models = await self.model_repo.get_by_provider(provider_id)
        return [self._model_to_response(m) for m in models]

    async def create_model(
        self, user_id: int, provider_id: int, data: AIModelCreate
    ) -> AIModelResponse:
        """Create a new model."""
        provider = await self.provider_repo.get_by_id(provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        
        model = await self.model_repo.create(
            provider_id=provider_id,
            model_id=data.model_id,
            name=data.name,
            description=data.description
        )
        return self._model_to_response(model)

    async def update_model(self, user_id: int, model_id: int, data: AIModelUpdate) -> AIModelResponse:
        """Update a model."""
        model = await self.model_repo.get_by_id(model_id)
        if not model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        
        # Verify user owns the provider
        provider = await self.provider_repo.get_by_id(model.provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        
        update_data = data.model_dump(exclude_unset=True)
        model = await self.model_repo.update(model, **update_data)
        return self._model_to_response(model)

    async def delete_model(self, user_id: int, model_id: int) -> None:
        """Delete a model."""
        model = await self.model_repo.get_by_id(model_id)
        if not model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        
        provider = await self.provider_repo.get_by_id(model.provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        
        # If deleting the default model, clear the default flag
        if model.is_default:
            await self.model_repo.clear_defaults_for_user(user_id)
        
        await self.model_repo.delete(model)

    async def set_default_model(self, user_id: int, model_id: int) -> AIModelResponse:
        """Set a model as default."""
        model = await self.model_repo.get_by_id(model_id)
        if not model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        
        provider = await self.provider_repo.get_by_id(model.provider_id, user_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        
        await self.model_repo.set_default(user_id, model_id)
        model = await self.model_repo.get_by_id(model_id)
        return self._model_to_response(model)

    async def get_all_models(self, user_id: int) -> List[AIModelResponse]:
        """Get all models for a user across all providers."""
        providers = await self.provider_repo.get_all_by_user(user_id)
        models = []
        for provider in providers:
            provider_models = await self.model_repo.get_by_provider(provider.id)
            models.extend([self._model_to_response(m) for m in provider_models])
        return models

    async def get_default_model(self, user_id: int) -> AIModelResponse | None:
        """Get the default model for a user."""
        model = await self.model_repo.get_default_model(user_id)
        if not model:
            return None
        return self._model_to_response(model)

    # AI operations
    async def translate_article(self, user_id: int, article_id: int, target_language: str) -> str:
        """Translate an article."""
        article = await self.article_repo.get_by_id(article_id)
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        
        default_model = await self.model_repo.get_default_model(user_id)
        if not default_model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No default AI model configured")
        
        provider = await self.provider_repo.get_by_id(default_model.provider_id, user_id)
        
        content = article.full_content or article.content or article.title
        
        try:
            client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
            article.translation_status = "translating"
            article.translation_error = None
            article.translation_started_at = datetime.utcnow()
            article.translation_completed_at = None
            await self.article_repo.session.flush()
            translation = await client.translate(content, target_language)
            await self.article_repo.update_content(article, translation=translation)
            article.translation_status = "completed"
            article.translation_error = None
            article.translation_completed_at = datetime.utcnow()
            await self.article_repo.session.flush()
            return translation
        except AIClientError as e:
            article.translation_status = "failed"
            article.translation_error = str(e)[:1000]
            article.translation_completed_at = datetime.utcnow()
            await self.article_repo.session.flush()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    async def summarize_article(self, user_id: int, article_id: int) -> str:
        """Generate summary for an article."""
        article = await self.article_repo.get_by_id(article_id)
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        
        default_model = await self.model_repo.get_default_model(user_id)
        if not default_model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No default AI model configured")
        
        provider = await self.provider_repo.get_by_id(default_model.provider_id, user_id)
        
        content = article.full_content or article.content or article.title
        
        try:
            client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
            summary = await client.summarize(content)
            await self.article_repo.update_content(article, summary=summary)
            return summary
        except AIClientError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    def _provider_to_response(self, provider: AIProvider) -> AIProviderResponse:
        """Convert provider to response."""
        return AIProviderResponse(
            id=provider.id,
            name=provider.name,
            type=provider.type,
            base_url=provider.base_url,
            is_active=provider.is_active,
            models=[self._model_to_response(m) for m in provider.models] if provider.models else []
        )

    def _model_to_response(self, model: AIModel) -> AIModelResponse:
        """Convert model to response."""
        return AIModelResponse(
            id=model.id,
            provider_id=model.provider_id,
            model_id=model.model_id,
            name=model.name,
            description=model.description,
            is_default=model.is_default,
            is_active=model.is_active
        )

    # Settings operations
    async def get_settings(self, user_id: int) -> dict:
        """Get AI settings for a user."""
        from app.models.user import User
        from sqlalchemy import select
        
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        # Default prompts
        default_translate = "You are a translator. Translate the following text to {target_language}. Keep the original paragraph structure and formatting. Only output the translation, nothing else."
        default_summarize = "You are a summarizer. Provide a concise summary of the following text in 2-3 sentences. Output in the same language as the input text."
        
        return {
            "translate_prompt": user.translate_prompt or default_translate if user else default_translate,
            "summarize_prompt": user.summarize_prompt or default_summarize if user else default_summarize,
            "embedding_provider_id": user.embedding_provider_id if user else None,
            "embedding_model": user.embedding_model if user else None,
            "google_translate_api_key": user.google_translate_api_key if user else None,
            "argos_source_language": (user.argos_source_language or "en") if user else "en",
            "mc_translation_api_key": user.mc_translation_api_key if user else None,
            "mc_translation_base_url": (user.mc_translation_base_url or "https://fanyi.aboen.com") if user else "https://fanyi.aboen.com",
            "mc_translation_model": (user.mc_translation_model or "argos") if user else "argos",
        }

    async def update_settings(self, user_id: int, data: dict) -> dict:
        """Update AI settings for a user."""
        from app.models.user import User
        from sqlalchemy import select
        
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        if "translate_prompt" in data:
            user.translate_prompt = data["translate_prompt"]
        if "summarize_prompt" in data:
            user.summarize_prompt = data["summarize_prompt"]
        if "embedding_provider_id" in data:
            user.embedding_provider_id = data["embedding_provider_id"]
        if "embedding_model" in data:
            user.embedding_model = data["embedding_model"]
        if "google_translate_api_key" in data:
            user.google_translate_api_key = data["google_translate_api_key"]
        if "argos_source_language" in data:
            user.argos_source_language = data["argos_source_language"]
        if "mc_translation_api_key" in data:
            user.mc_translation_api_key = data["mc_translation_api_key"]
        if "mc_translation_base_url" in data:
            user.mc_translation_base_url = data["mc_translation_base_url"]
        if "mc_translation_model" in data:
            user.mc_translation_model = data["mc_translation_model"]
        
        await self.session.commit()
        
        return await self.get_settings(user_id)
    
    async def get_embedding_config(self, user_id: int) -> dict | None:
        """Get embedding configuration for a user."""
        from app.models.user import User
        from sqlalchemy import select
        
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user or not user.embedding_provider_id or not user.embedding_model:
            return None
        
        provider = await self.provider_repo.get_by_id(user.embedding_provider_id, user_id)
        if not provider:
            return None
        
        return {
            "api_key": provider.api_key,
            "base_url": provider.base_url,
            "model": user.embedding_model,
        }
