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
    AnalyzeRequest,
    AnalyzeResponse,
    ArticleResult,
    QueryHistoryItem,
    QueryHistoryResponse,
    SummarizeResponse,
    TestConnectionResponse,
    TranslateRequest,
    TranslateResponse,
)
from app.services.ai_service import AIService
from app.services.content_analysis_service import ContentAnalysisService
from app.services.embedding_service import EmbeddingService
from app.repositories.analysis_query_repository import AnalysisQueryRepository
from app.repositories.ai_repository import AIProviderRepository
from app.services.ai_client import create_ai_client

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


# Settings endpoints
@router.get("/settings")
async def get_ai_settings(user_id: CurrentUserId, db: DbSession):
    """Get AI prompt settings."""
    service = AIService(db)
    return await service.get_settings(user_id)


@router.put("/settings")
async def update_ai_settings(
    data: dict,
    user_id: CurrentUserId,
    db: DbSession
):
    """Update AI prompt settings."""
    service = AIService(db)
    return await service.update_settings(user_id, data)


# ============ Content Analysis Endpoints ============

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_content(
    data: AnalyzeRequest,
    user_id: CurrentUserId,
    db: DbSession
):
    """
    Analyze content based on a natural language query.
    
    Returns AI-generated analysis and related articles.
    """
    # 获取用户的默认 AI 模型配置
    ai_service = AIService(db)
    default_model = await ai_service.get_default_model(user_id)
    
    embedding_service = None
    ai_client = None
    
    if default_model:
        # 获取 provider 信息
        provider_repo = AIProviderRepository(db)
        provider = await provider_repo.get_by_id(default_model.provider_id, user_id)
        
        if provider:
            # 创建 embedding 服务
            embedding_service = EmbeddingService(
                api_key=provider.api_key,
                base_url=provider.base_url
            )
            
            # 创建 AI 客户端用于生成分析
            ai_client = create_ai_client(
                provider.type,
                provider.api_key,
                provider.base_url,
                default_model.model_id
            )
    
    # 创建内容分析服务
    analysis_service = ContentAnalysisService(
        session=db,
        embedding_service=embedding_service,
        ai_client=ai_client
    )
    
    # 执行分析
    result = await analysis_service.analyze(
        user_id=user_id,
        query=data.query,
        page=data.page,
        page_size=data.page_size,
        use_semantic_search=data.use_semantic_search
    )
    
    # 保存查询历史
    query_repo = AnalysisQueryRepository(db)
    await query_repo.create(user_id=user_id, query=data.query)
    await query_repo.delete_old_queries(user_id=user_id, keep_count=10)
    await db.commit()
    
    # 转换为响应格式
    articles = [
        ArticleResult(
            id=a.id,
            title=a.title,
            feed_title=a.feed_title,
            link=a.link,
            published_at=a.published_at.isoformat() if a.published_at else None,
            relevance_score=a.relevance_score,
            snippet=a.get_snippet()
        )
        for a in result.articles
    ]
    
    return AnalyzeResponse(
        query=result.query,
        analysis=result.analysis,
        articles=articles,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        search_type=result.search_type
    )


@router.get("/history", response_model=QueryHistoryResponse)
async def get_query_history(user_id: CurrentUserId, db: DbSession):
    """Get user's recent analysis query history."""
    query_repo = AnalysisQueryRepository(db)
    queries = await query_repo.get_recent_by_user(user_id, limit=10)
    
    return QueryHistoryResponse(
        queries=[
            QueryHistoryItem(
                id=q.id,
                query=q.query,
                created_at=q.created_at.isoformat() if q.created_at else ""
            )
            for q in queries
        ]
    )


@router.delete("/history/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query_history(
    query_id: int,
    user_id: CurrentUserId,
    db: DbSession
):
    """Delete a query from history."""
    query_repo = AnalysisQueryRepository(db)
    deleted = await query_repo.delete(query_id, user_id)
    
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Query not found")
    
    await db.commit()
