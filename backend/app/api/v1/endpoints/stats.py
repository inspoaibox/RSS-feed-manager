"""Statistics API endpoints."""
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select, and_, case

from app.api.deps import CurrentUserId, DbSession
from app.models.article import Article, UserArticle
from app.models.feed import Feed
from app.models.category import Category

router = APIRouter()


class OverviewStats(BaseModel):
    """Overview statistics."""
    total_feeds: int
    active_feeds: int
    total_articles: int
    unread_articles: int
    favorite_articles: int
    today_articles: int
    this_week_articles: int


class DailyArticleCount(BaseModel):
    """Daily article count."""
    date: str
    count: int


class FeedActivityStats(BaseModel):
    """Feed activity statistics."""
    feed_id: int
    feed_title: str
    article_count: int
    last_article_date: str | None


class CategoryStats(BaseModel):
    """Category statistics."""
    category_id: int | None
    category_name: str
    feed_count: int
    article_count: int


class HourlyDistribution(BaseModel):
    """Hourly article distribution."""
    hour: int
    count: int


class StatsResponse(BaseModel):
    """Complete statistics response."""
    overview: OverviewStats
    daily_trend: List[DailyArticleCount]
    feed_activity: List[FeedActivityStats]
    category_distribution: List[CategoryStats]
    hourly_distribution: List[HourlyDistribution]


@router.get("", response_model=StatsResponse)
async def get_stats(
    user_id: CurrentUserId,
    db: DbSession,
    days: int = Query(30, ge=7, le=90, description="Number of days for trend data")
):
    """Get comprehensive statistics for the user."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    trend_start = today_start - timedelta(days=days)
    
    # Get user's feed IDs
    feed_result = await db.execute(
        select(Feed.id).where(Feed.user_id == user_id)
    )
    user_feed_ids = [row[0] for row in feed_result.fetchall()]
    
    if not user_feed_ids:
        # Return empty stats if user has no feeds
        return StatsResponse(
            overview=OverviewStats(
                total_feeds=0, active_feeds=0, total_articles=0,
                unread_articles=0, favorite_articles=0,
                today_articles=0, this_week_articles=0
            ),
            daily_trend=[],
            feed_activity=[],
            category_distribution=[],
            hourly_distribution=[]
        )
    
    # Overview stats
    overview = await get_overview_stats(db, user_id, user_feed_ids, today_start, week_start)
    
    # Daily trend
    daily_trend = await get_daily_trend(db, user_feed_ids, trend_start, days)
    
    # Feed activity
    feed_activity = await get_feed_activity(db, user_id, user_feed_ids, days)
    
    # Category distribution
    category_distribution = await get_category_distribution(db, user_id)
    
    # Hourly distribution
    hourly_distribution = await get_hourly_distribution(db, user_feed_ids, days)
    
    return StatsResponse(
        overview=overview,
        daily_trend=daily_trend,
        feed_activity=feed_activity,
        category_distribution=category_distribution,
        hourly_distribution=hourly_distribution
    )


async def get_overview_stats(
    db: DbSession, user_id: int, feed_ids: List[int],
    today_start: datetime, week_start: datetime
) -> OverviewStats:
    """Get overview statistics."""
    # Total and active feeds
    feed_result = await db.execute(
        select(
            func.count(Feed.id),
            func.sum(case((Feed.is_active == True, 1), else_=0))
        ).where(Feed.user_id == user_id)
    )
    feed_row = feed_result.fetchone()
    total_feeds = feed_row[0] or 0
    active_feeds = feed_row[1] or 0
    
    # Total articles
    total_result = await db.execute(
        select(func.count(Article.id)).where(Article.feed_id.in_(feed_ids))
    )
    total_articles = total_result.scalar() or 0
    
    # Unread articles (articles without UserArticle record or is_read=False)
    read_subquery = (
        select(UserArticle.article_id)
        .where(and_(UserArticle.user_id == user_id, UserArticle.is_read == True))
    )
    unread_result = await db.execute(
        select(func.count(Article.id))
        .where(and_(
            Article.feed_id.in_(feed_ids),
            ~Article.id.in_(read_subquery)
        ))
    )
    unread_articles = unread_result.scalar() or 0
    
    # Favorite articles
    fav_result = await db.execute(
        select(func.count(UserArticle.article_id))
        .where(and_(
            UserArticle.user_id == user_id,
            UserArticle.is_favorite == True
        ))
    )
    favorite_articles = fav_result.scalar() or 0
    
    # Today's articles
    today_result = await db.execute(
        select(func.count(Article.id))
        .where(and_(
            Article.feed_id.in_(feed_ids),
            Article.created_at >= today_start
        ))
    )
    today_articles = today_result.scalar() or 0
    
    # This week's articles
    week_result = await db.execute(
        select(func.count(Article.id))
        .where(and_(
            Article.feed_id.in_(feed_ids),
            Article.created_at >= week_start
        ))
    )
    this_week_articles = week_result.scalar() or 0
    
    return OverviewStats(
        total_feeds=total_feeds,
        active_feeds=int(active_feeds),
        total_articles=total_articles,
        unread_articles=unread_articles,
        favorite_articles=favorite_articles,
        today_articles=today_articles,
        this_week_articles=this_week_articles
    )


async def get_daily_trend(
    db: DbSession, feed_ids: List[int], start_date: datetime, days: int
) -> List[DailyArticleCount]:
    """Get daily article count trend."""
    # Use created_at for consistency
    result = await db.execute(
        select(
            func.date(Article.created_at).label('date'),
            func.count(Article.id).label('count')
        )
        .where(and_(
            Article.feed_id.in_(feed_ids),
            Article.created_at >= start_date
        ))
        .group_by(func.date(Article.created_at))
        .order_by(func.date(Article.created_at))
    )
    
    # Create a dict of existing data
    data_dict = {str(row.date): row.count for row in result.fetchall()}
    
    # Fill in missing dates with 0
    trend = []
    current = start_date
    end = datetime.utcnow()
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        trend.append(DailyArticleCount(
            date=date_str,
            count=data_dict.get(date_str, 0)
        ))
        current += timedelta(days=1)
    
    return trend


async def get_feed_activity(
    db: DbSession, user_id: int, feed_ids: List[int], days: int
) -> List[FeedActivityStats]:
    """Get feed activity statistics."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(
            Feed.id,
            Feed.title,
            func.count(Article.id).label('article_count'),
            func.max(Article.created_at).label('last_article')
        )
        .outerjoin(Article, and_(
            Article.feed_id == Feed.id,
            Article.created_at >= start_date
        ))
        .where(Feed.user_id == user_id)
        .group_by(Feed.id, Feed.title)
        .order_by(func.count(Article.id).desc())
        .limit(20)
    )
    
    return [
        FeedActivityStats(
            feed_id=row.id,
            feed_title=row.title or 'Unknown',
            article_count=row.article_count or 0,
            last_article_date=row.last_article.isoformat() if row.last_article else None
        )
        for row in result.fetchall()
    ]


async def get_category_distribution(db: DbSession, user_id: int) -> List[CategoryStats]:
    """Get category distribution statistics."""
    result = await db.execute(
        select(
            Category.id,
            Category.name,
            func.count(func.distinct(Feed.id)).label('feed_count'),
            func.count(Article.id).label('article_count')
        )
        .outerjoin(Feed, and_(Feed.category_id == Category.id, Feed.user_id == user_id))
        .outerjoin(Article, Article.feed_id == Feed.id)
        .where(Category.user_id == user_id)
        .group_by(Category.id, Category.name)
        .order_by(func.count(Article.id).desc())
    )
    
    categories = [
        CategoryStats(
            category_id=row.id,
            category_name=row.name,
            feed_count=row.feed_count or 0,
            article_count=row.article_count or 0
        )
        for row in result.fetchall()
    ]
    
    # Add uncategorized feeds
    uncategorized_result = await db.execute(
        select(
            func.count(func.distinct(Feed.id)).label('feed_count'),
            func.count(Article.id).label('article_count')
        )
        .select_from(Feed)
        .outerjoin(Article, Article.feed_id == Feed.id)
        .where(and_(Feed.user_id == user_id, Feed.category_id == None))
    )
    uncategorized = uncategorized_result.fetchone()
    if uncategorized and (uncategorized.feed_count or uncategorized.article_count):
        categories.append(CategoryStats(
            category_id=None,
            category_name='未分类',
            feed_count=uncategorized.feed_count or 0,
            article_count=uncategorized.article_count or 0
        ))
    
    return categories


async def get_hourly_distribution(
    db: DbSession, feed_ids: List[int], days: int
) -> List[HourlyDistribution]:
    """Get hourly article distribution."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Use published_at if available, otherwise created_at
    result = await db.execute(
        select(
            func.extract('hour', func.coalesce(Article.published_at, Article.created_at)).label('hour'),
            func.count(Article.id).label('count')
        )
        .where(and_(
            Article.feed_id.in_(feed_ids),
            Article.created_at >= start_date
        ))
        .group_by(func.extract('hour', func.coalesce(Article.published_at, Article.created_at)))
        .order_by('hour')
    )
    
    # Create dict of existing data
    data_dict = {int(row.hour): row.count for row in result.fetchall()}
    
    # Fill all 24 hours
    return [
        HourlyDistribution(hour=h, count=data_dict.get(h, 0))
        for h in range(24)
    ]
