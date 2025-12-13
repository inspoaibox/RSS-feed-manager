"""Recommended feeds API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.feed import Feed
from app.models.recommended_feed import RecommendedFeed
from app.repositories.system_settings_repository import SystemSettingsRepository

router = APIRouter()


# Schemas
class RecommendedFeedCreate(BaseModel):
    url: str
    title: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    categories: str = ""  # comma-separated


class RecommendedFeedUpdate(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    categories: Optional[str] = None
    is_active: Optional[bool] = None


class RecommendedFeedResponse(BaseModel):
    id: int
    url: str
    title: str
    description: Optional[str]
    icon_url: Optional[str]
    categories: str
    is_active: bool
    subscriber_count: int
    is_subscribed: bool = False  # Whether current user has subscribed

    class Config:
        from_attributes = True


class SubscribeRequest(BaseModel):
    category_id: Optional[int] = None


class RecommendationStatusResponse(BaseModel):
    enabled: bool
    category_tags: List[str]  # All unique category tags


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin user."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return user


async def check_feature_enabled(db: AsyncSession) -> bool:
    """Check if recommendations feature is enabled."""
    settings_repo = SystemSettingsRepository(db)
    return await settings_repo.get_bool('enable_feed_recommendations', False)


# Public endpoints (for all authenticated users)

@router.get("/status", response_model=RecommendationStatusResponse)
async def get_recommendation_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get recommendation feature status and available category tags."""
    enabled = await check_feature_enabled(db)
    
    # Get all unique category tags
    result = await db.execute(
        select(RecommendedFeed.categories)
        .where(RecommendedFeed.is_active == True)
    )
    all_categories = result.scalars().all()
    
    # Parse and deduplicate tags
    tags = set()
    for cats in all_categories:
        if cats:
            for tag in cats.split(','):
                tag = tag.strip()
                if tag:
                    tags.add(tag)
    
    return RecommendationStatusResponse(
        enabled=enabled,
        category_tags=sorted(list(tags))
    )


@router.get("", response_model=List[RecommendedFeedResponse])
async def list_recommendations(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List all active recommended feeds."""
    enabled = await check_feature_enabled(db)
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="订阅推荐功能未开启"
        )
    
    query = select(RecommendedFeed).where(RecommendedFeed.is_active == True)
    result = await db.execute(query)
    feeds = result.scalars().all()
    
    # Filter by category if specified
    if category:
        feeds = [f for f in feeds if category in [c.strip() for c in f.categories.split(',')]]
    
    # Get user's subscribed URLs
    user_feeds_result = await db.execute(
        select(Feed.url).where(Feed.user_id == user.id)
    )
    subscribed_urls = {row[0] for row in user_feeds_result.fetchall()}
    
    # Build response
    response = []
    for feed in feeds:
        resp = RecommendedFeedResponse(
            id=feed.id,
            url=feed.url,
            title=feed.title,
            description=feed.description,
            icon_url=feed.icon_url,
            categories=feed.categories,
            is_active=feed.is_active,
            subscriber_count=feed.subscriber_count,
            is_subscribed=feed.url in subscribed_urls
        )
        response.append(resp)
    
    return response


@router.post("/{recommendation_id}/subscribe")
async def subscribe_to_recommendation(
    recommendation_id: int,
    data: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Subscribe to a recommended feed."""
    enabled = await check_feature_enabled(db)
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="订阅推荐功能未开启"
        )
    
    # Get recommendation
    result = await db.execute(
        select(RecommendedFeed).where(
            RecommendedFeed.id == recommendation_id,
            RecommendedFeed.is_active == True
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="推荐源不存在")
    
    # Check if already subscribed
    existing = await db.execute(
        select(Feed).where(
            Feed.user_id == user.id,
            Feed.url == rec.url
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已订阅此源")
    
    # Create feed for user
    feed = Feed(
        user_id=user.id,
        category_id=data.category_id,
        url=rec.url,
        title=rec.title,
        description=rec.description,
        icon_url=rec.icon_url,
        is_active=True
    )
    db.add(feed)
    
    # Increment subscriber count
    rec.subscriber_count += 1
    
    await db.commit()
    
    return {"success": True, "message": f"已订阅 {rec.title}", "feed_id": feed.id}


# Admin endpoints

@router.get("/admin/all", response_model=List[RecommendedFeedResponse])
async def admin_list_all_recommendations(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """List all recommended feeds (admin only, includes inactive)."""
    result = await db.execute(
        select(RecommendedFeed).order_by(RecommendedFeed.created_at.desc())
    )
    feeds = result.scalars().all()
    
    return [
        RecommendedFeedResponse(
            id=f.id,
            url=f.url,
            title=f.title,
            description=f.description,
            icon_url=f.icon_url,
            categories=f.categories,
            is_active=f.is_active,
            subscriber_count=f.subscriber_count,
            is_subscribed=False
        )
        for f in feeds
    ]


@router.post("/admin", response_model=RecommendedFeedResponse)
async def admin_create_recommendation(
    data: RecommendedFeedCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create a new recommended feed (admin only)."""
    # Check for duplicate URL
    existing = await db.execute(
        select(RecommendedFeed).where(RecommendedFeed.url == data.url)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该 URL 已存在")
    
    rec = RecommendedFeed(
        url=data.url,
        title=data.title,
        description=data.description,
        icon_url=data.icon_url,
        categories=data.categories,
        created_by=admin.id
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    
    return RecommendedFeedResponse(
        id=rec.id,
        url=rec.url,
        title=rec.title,
        description=rec.description,
        icon_url=rec.icon_url,
        categories=rec.categories,
        is_active=rec.is_active,
        subscriber_count=rec.subscriber_count,
        is_subscribed=False
    )


@router.put("/admin/{recommendation_id}", response_model=RecommendedFeedResponse)
async def admin_update_recommendation(
    recommendation_id: int,
    data: RecommendedFeedUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update a recommended feed (admin only)."""
    result = await db.execute(
        select(RecommendedFeed).where(RecommendedFeed.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="推荐源不存在")
    
    # Check URL uniqueness if changing
    if data.url and data.url != rec.url:
        existing = await db.execute(
            select(RecommendedFeed).where(RecommendedFeed.url == data.url)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该 URL 已存在")
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rec, key, value)
    
    await db.commit()
    await db.refresh(rec)
    
    return RecommendedFeedResponse(
        id=rec.id,
        url=rec.url,
        title=rec.title,
        description=rec.description,
        icon_url=rec.icon_url,
        categories=rec.categories,
        is_active=rec.is_active,
        subscriber_count=rec.subscriber_count,
        is_subscribed=False
    )


@router.delete("/admin/{recommendation_id}")
async def admin_delete_recommendation(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete a recommended feed (admin only)."""
    result = await db.execute(
        select(RecommendedFeed).where(RecommendedFeed.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="推荐源不存在")
    
    await db.delete(rec)
    await db.commit()
    
    return {"success": True, "message": "已删除"}
