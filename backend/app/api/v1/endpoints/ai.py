"""AI API endpoints."""
from typing import List

from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, DbSession
from app.schemas.ai import (
    AIModelCreate,
    AIModelResponse,
    AIModelUpdate,
    AIProviderCreate,
    AIProviderResponse,
    AIProviderUpdate,
    SummarizeResponse,
    TestConnectionResponse,
    TranslateRequest,
    TranslateResponse,
)
from app.services.ai_service import AIService

router = APIRouter()


# Provider endpoints
@router.get("/providers", response_model=List[AIProviderResponse])
async def get_providers(user_id: CurrentUserId, db: DbSession):
    """Get all AI providers for the current user."""
    service = AIService(db)
    return await service.get_providers(user_id)


@router.post("/providers", response_model=AIProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(data: AIProviderCreate, user_id: CurrentUserId, db: DbSession):
    """Create a new AI provider."""
    service = AIService(db)
    return await service.create_provider(user_id, data)


@router.get("/providers/{provider_id}", response_model=AIProviderResponse)
async def get_provider(provider_id: int, user_id: CurrentUserId, db: DbSession):
    """Get an AI provider by ID."""
    service = AIService(db)
    return await service.get_provider(user_id, provider_id)


@router.put("/providers/{provider_id}", response_model=AIProviderResponse)
async def update_provider(
    provider_id: int, data: AIProviderUpdate, user_id: CurrentUserId, db: DbSession
):
    """Update an AI provider."""
    service = AIService(db)
    return await service.update_provider(user_id, provider_id, data)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(provider_id: int, user_id: CurrentUserId, db: DbSession):
    """Delete an AI provider."""
    service = AIService(db)
    await service.delete_provider(user_id, provider_id)


@router.post("/providers/{provider_id}/test", response_model=TestConnectionResponse)
async def test_provider(provider_id: int, user_id: CurrentUserId, db: DbSession):
    """Test AI provider connection."""
    service = AIService(db)
    return await service.test_provider(user_id, provider_id)


@router.post("/providers/{provider_id}/fetch-models", response_model=List[AIModelResponse])
async def fetch_models(provider_id: int, user_id: CurrentUserId, db: DbSession):
    """Fetch available models from the AI provider."""
    service = AIService(db)
    return await service.fetch_models(user_id, provider_id)


# Model endpoints
@router.get("/providers/{provider_id}/models", response_model=List[AIModelResponse])
async def get_models(provider_id: int, user_id: CurrentUserId, db: DbSession):
    """Get all models for a provider."""
    service = AIService(db)
    return await service.get_models(user_id, provider_id)


@router.post("/providers/{provider_id}/models", response_model=AIModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    provider_id: int, data: AIModelCreate, user_id: CurrentUserId, db: DbSession
):
    """Create a new AI model."""
    service = AIService(db)
    return await service.create_model(user_id, provider_id, data)


@router.put("/models/{model_id}", response_model=AIModelResponse)
async def update_model(model_id: int, data: AIModelUpdate, user_id: CurrentUserId, db: DbSession):
    """Update an AI model."""
    service = AIService(db)
    return await service.update_model(user_id, model_id, data)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(model_id: int, user_id: CurrentUserId, db: DbSession):
    """Delete an AI model."""
    service = AIService(db)
    await service.delete_model(user_id, model_id)


@router.put("/models/{model_id}/default", response_model=AIModelResponse)
async def set_default_model(model_id: int, user_id: CurrentUserId, db: DbSession):
    """Set a model as the default."""
    service = AIService(db)
    return await service.set_default_model(user_id, model_id)


@router.get("/models", response_model=List[AIModelResponse])
async def get_all_models(user_id: CurrentUserId, db: DbSession):
    """Get all AI models for the current user."""
    service = AIService(db)
    return await service.get_all_models(user_id)


@router.get("/models/default", response_model=AIModelResponse | None)
async def get_default_model(user_id: CurrentUserId, db: DbSession):
    """Get the default AI model."""
    service = AIService(db)
    return await service.get_default_model(user_id)


# AI operation endpoints
@router.post("/translate/{article_id}", response_model=TranslateResponse)
async def translate_article(
    article_id: int, data: TranslateRequest, user_id: CurrentUserId, db: DbSession
):
    """Translate an article using AI."""
    service = AIService(db)
    translation = await service.translate_article(user_id, article_id, data.target_language)
    return TranslateResponse(translation=translation)


@router.post("/summarize/{article_id}", response_model=SummarizeResponse)
async def summarize_article(article_id: int, user_id: CurrentUserId, db: DbSession):
    """Generate AI summary for an article."""
    service = AIService(db)
    summary = await service.summarize_article(user_id, article_id)
    return SummarizeResponse(summary=summary)
