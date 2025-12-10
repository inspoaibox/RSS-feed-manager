"""AI schemas for request/response validation."""
from pydantic import BaseModel, Field


class AIProviderCreate(BaseModel):
    """Schema for creating an AI provider."""
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., pattern="^(openai|gemini|openai_compatible)$")
    api_key: str = Field(..., min_length=1, max_length=500)
    base_url: str | None = Field(None, max_length=2048)


class AIProviderUpdate(BaseModel):
    """Schema for updating an AI provider."""
    name: str | None = Field(None, min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1, max_length=500)
    base_url: str | None = Field(None, max_length=2048)
    is_active: bool | None = None


class AIModelResponse(BaseModel):
    """Schema for AI model response."""
    id: int
    provider_id: int
    model_id: str
    name: str
    description: str | None
    is_default: bool
    is_active: bool

    class Config:
        from_attributes = True


class AIProviderResponse(BaseModel):
    """Schema for AI provider response."""
    id: int
    name: str
    type: str
    base_url: str | None
    is_active: bool
    models: list[AIModelResponse] = []

    class Config:
        from_attributes = True


class AIModelCreate(BaseModel):
    """Schema for creating an AI model."""
    model_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class AIModelUpdate(BaseModel):
    """Schema for updating an AI model."""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class TestConnectionResponse(BaseModel):
    """Schema for connection test response."""
    success: bool
    message: str


class TranslateRequest(BaseModel):
    """Schema for translation request."""
    target_language: str = Field(..., min_length=2, max_length=10)


class SummarizeResponse(BaseModel):
    """Schema for summarize response."""
    summary: str


class TranslateResponse(BaseModel):
    """Schema for translate response."""
    translation: str


# ============ Content Analysis Schemas ============

class AnalyzeRequest(BaseModel):
    """Schema for content analysis request."""
    query: str = Field(..., min_length=1, max_length=500, description="搜索查询文本")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    use_semantic_search: bool = Field(default=True, description="是否使用语义搜索")


class ArticleResult(BaseModel):
    """Schema for article in analysis results."""
    id: int
    title: str
    feed_title: str
    link: str | None
    published_at: str | None
    relevance_score: float
    snippet: str

    class Config:
        from_attributes = True


class AnalyzeResponse(BaseModel):
    """Schema for content analysis response."""
    query: str
    analysis: str | None
    articles: list[ArticleResult]
    total: int
    page: int
    page_size: int
    search_type: str  # "semantic" or "keyword"


class QueryHistoryItem(BaseModel):
    """Schema for query history item."""
    id: int
    query: str
    created_at: str

    class Config:
        from_attributes = True


class QueryHistoryResponse(BaseModel):
    """Schema for query history response."""
    queries: list[QueryHistoryItem]
