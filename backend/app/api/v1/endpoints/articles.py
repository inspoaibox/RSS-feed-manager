"""Article API endpoints."""
from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserId, DbSession
from app.schemas.article import (
    ArticleFilter,
    ArticleListResponse,
    ArticleResponse,
    ArticleSearchRequest,
    FavoriteResponse,
    MarkAllReadRequest,
)
from app.services.article_service import ArticleService

router = APIRouter()


@router.get("", response_model=ArticleListResponse)
async def get_articles(
    user_id: CurrentUserId,
    db: DbSession,
    feed_id: int | None = Query(None),
    category_id: int | None = Query(None),
    keyword_id: int | None = Query(None),
    is_read: bool | None = Query(None),
    is_favorite: bool | None = Query(None),
    sort_by: str = Query("published_at", pattern="^(published_at|created_at|title)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    date_from: str | None = Query(None, description="Filter by date from (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Filter by date to (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """Get paginated articles with optional filters."""
    service = ArticleService(db)
    filters = ArticleFilter(
        feed_id=feed_id,
        category_id=category_id,
        keyword_id=keyword_id,
        is_read=is_read,
        is_favorite=is_favorite,
        sort_by=sort_by,
        sort_order=sort_order,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size
    )
    return await service.get_articles(user_id, filters)


@router.get("/search", response_model=ArticleListResponse)
async def search_articles(
    user_id: CurrentUserId,
    db: DbSession,
    q: str = Query(..., min_length=1, max_length=200),
    feed_id: int | None = Query(None),
    category_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """Search articles by title and content."""
    service = ArticleService(db)
    request = ArticleSearchRequest(
        query=q,
        feed_id=feed_id,
        category_id=category_id,
        page=page,
        page_size=page_size
    )
    return await service.search(user_id, request)


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, user_id: CurrentUserId, db: DbSession):
    """Get article by ID (automatically marks as read)."""
    service = ArticleService(db)
    return await service.get_by_id(user_id, article_id)


@router.put("/{article_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(article_id: int, user_id: CurrentUserId, db: DbSession):
    """Mark article as read."""
    service = ArticleService(db)
    await service.mark_read(user_id, article_id)


@router.put("/{article_id}/unread", status_code=status.HTTP_204_NO_CONTENT)
async def mark_unread(article_id: int, user_id: CurrentUserId, db: DbSession):
    """Mark article as unread."""
    service = ArticleService(db)
    await service.mark_unread(user_id, article_id)


@router.put("/{article_id}/favorite", response_model=FavoriteResponse)
async def toggle_favorite(article_id: int, user_id: CurrentUserId, db: DbSession):
    """Toggle article favorite status."""
    service = ArticleService(db)
    is_favorite = await service.toggle_favorite(user_id, article_id)
    return FavoriteResponse(is_favorite=is_favorite)


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
async def mark_all_read(
    data: MarkAllReadRequest,
    user_id: CurrentUserId,
    db: DbSession
):
    """Mark all articles as read (optionally filtered by feed, category, or keyword)."""
    service = ArticleService(db)
    count = await service.mark_all_read(user_id, data.feed_id, data.category_id, data.keyword_id)
    return {"marked_count": count}


@router.post("/{article_id}/translate")
async def translate_article(
    article_id: int,
    user_id: CurrentUserId,
    db: DbSession,
    target_language: str = Query("zh-CN")
):
    """Queue article content translation."""
    service = ArticleService(db)
    result = await service.translate_article(user_id, article_id, target_language)
    return result


@router.post("/{article_id}/summarize")
async def summarize_article(
    article_id: int,
    user_id: CurrentUserId,
    db: DbSession
):
    """Summarize article content using AI."""
    service = ArticleService(db)
    result = await service.summarize_article(user_id, article_id)
    return result
