"""Mobile sync API endpoints."""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select

from app.api.deps import CurrentUserId, DbSession
from app.models.article import Article, UserArticle
from app.models.category import Category
from app.models.feed import Feed
from app.repositories.article_repository import ArticleRepository
from app.repositories.feed_repository import FeedRepository

router = APIRouter()


class MobileCategory(BaseModel):
    id: int
    name: str
    description: str | None
    position: int
    feed_count: int = 0
    unread_count: int = 0


class MobileFeed(BaseModel):
    id: int
    url: str
    title: str
    description: str | None
    site_url: str | None
    icon_url: str | None
    category_id: int | None
    fetch_interval: int
    last_fetched_at: datetime | None
    auto_translate: bool
    auto_summarize: bool
    target_language: str | None
    translate_method: str
    is_active: bool
    use_playwright: bool
    position: int
    unread_count: int = 0
    article_count: int = 0


class MobileArticle(BaseModel):
    id: int
    feed_id: int
    feed_title: str | None = None
    title: str
    link: str | None
    content: str | None
    full_content: str | None
    summary: str | None
    translation: str | None
    author: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    is_read: bool = False
    is_favorite: bool = False
    read_at: datetime | None = None


class MobileArticleState(BaseModel):
    article_id: int
    is_read: bool = False
    is_favorite: bool = False
    read_at: datetime | None = None


class MobileSyncResponse(BaseModel):
    server_time: datetime
    since: str | None
    has_more: bool
    next_offset: int | None
    categories: list[MobileCategory]
    feeds: list[MobileFeed]
    articles: list[MobileArticle]
    states: list[MobileArticleState]


class MobileAction(BaseModel):
    client_action_id: str | None = None
    type: str = Field(..., pattern="^(mark_read|mark_unread|set_favorite)$")
    article_id: int
    value: bool | None = None


class MobileActionsRequest(BaseModel):
    actions: list[MobileAction] = Field(default_factory=list)


class MobileActionResult(BaseModel):
    client_action_id: str | None = None
    article_id: int
    type: str
    status: str
    detail: str | None = None


class MobileActionsResponse(BaseModel):
    results: list[MobileActionResult]


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _category_to_mobile(category: Category, feed_count: int, unread_count: int) -> MobileCategory:
    return MobileCategory(
        id=category.id,
        name=category.name,
        description=category.description,
        position=category.position,
        feed_count=feed_count,
        unread_count=unread_count,
    )


def _feed_to_mobile(feed: Feed, counts: dict[str, int]) -> MobileFeed:
    return MobileFeed(
        id=feed.id,
        url=feed.url,
        title=feed.title,
        description=feed.description,
        site_url=feed.site_url,
        icon_url=feed.icon_url,
        category_id=feed.category_id,
        fetch_interval=feed.fetch_interval,
        last_fetched_at=feed.last_fetched_at,
        auto_translate=feed.auto_translate,
        auto_summarize=feed.auto_summarize,
        target_language=feed.target_language,
        translate_method=feed.translate_method,
        is_active=feed.is_active,
        use_playwright=feed.use_playwright,
        position=feed.position,
        unread_count=counts.get("unread_count", 0),
        article_count=counts.get("article_count", 0),
    )


def _article_to_mobile(row: dict[str, Any]) -> MobileArticle:
    article: Article = row["article"]
    return MobileArticle(
        id=article.id,
        feed_id=article.feed_id,
        feed_title=row.get("feed_title"),
        title=article.title,
        link=article.link,
        content=article.content,
        full_content=article.full_content,
        summary=article.summary,
        translation=article.translation,
        author=article.author,
        published_at=article.published_at,
        created_at=article.created_at,
        updated_at=article.updated_at,
        is_read=row.get("is_read", False),
        is_favorite=row.get("is_favorite", False),
        read_at=row.get("read_at"),
    )


@router.get("/sync", response_model=MobileSyncResponse)
async def sync_mobile(
    user_id: CurrentUserId,
    db: DbSession,
    since: str | None = Query(None, description="Last server_time returned by this endpoint"),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
):
    """Return mobile-friendly metadata and recently changed articles."""
    since_dt = _parse_since(since)
    server_time = datetime.now(timezone.utc)

    categories_result = await db.execute(
        select(Category)
        .where(Category.user_id == user_id)
        .order_by(Category.position.asc(), Category.name.asc())
    )
    categories = list(categories_result.scalars().all())

    feed_counts_by_category: dict[int, int] = {}
    category_counts_result = await db.execute(
        select(Feed.category_id, func.count(Feed.id))
        .where(Feed.user_id == user_id)
        .group_by(Feed.category_id)
    )
    for category_id, count in category_counts_result.all():
        if category_id is not None:
            feed_counts_by_category[category_id] = count

    unread_counts_by_category: dict[int, int] = {}
    unread_counts_result = await db.execute(
        select(Feed.category_id, func.count(Article.id))
        .join(Article, Article.feed_id == Feed.id)
        .outerjoin(
            UserArticle,
            and_(
                UserArticle.article_id == Article.id,
                UserArticle.user_id == user_id,
            ),
        )
        .where(
            Feed.user_id == user_id,
            Feed.category_id.is_not(None),
            or_(UserArticle.is_read == False, UserArticle.is_read == None),
        )
        .group_by(Feed.category_id)
    )
    for category_id, count in unread_counts_result.all():
        if category_id is not None:
            unread_counts_by_category[category_id] = count

    feed_repo = FeedRepository(db)
    feeds = await feed_repo.get_all_by_user(user_id)
    feed_ids = [feed.id for feed in feeds]
    feed_counts = await feed_repo.get_article_counts(user_id, feed_ids)

    article_query = (
        select(Article, UserArticle, Feed.title.label("feed_title"))
        .join(Feed, Article.feed_id == Feed.id)
        .outerjoin(
            UserArticle,
            and_(
                UserArticle.article_id == Article.id,
                UserArticle.user_id == user_id,
            ),
        )
        .where(Feed.user_id == user_id)
    )
    if since_dt is not None:
        article_query = article_query.where(
            or_(
                Article.created_at > since_dt,
                Article.updated_at > since_dt,
                UserArticle.read_at > since_dt,
                UserArticle.favorited_at > since_dt,
            )
        )

    article_query = (
        article_query
        .order_by(Article.created_at.desc(), Article.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    article_result = await db.execute(article_query)
    rows = article_result.all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    articles = []
    for article, user_article, feed_title in rows:
        articles.append(_article_to_mobile({
            "article": article,
            "feed_title": feed_title,
            "is_read": user_article.is_read if user_article else False,
            "is_favorite": user_article.is_favorite if user_article else False,
            "read_at": user_article.read_at if user_article else None,
        }))

    state_result = await db.execute(
        select(UserArticle)
        .join(Article, UserArticle.article_id == Article.id)
        .join(Feed, Article.feed_id == Feed.id)
        .where(UserArticle.user_id == user_id, Feed.user_id == user_id)
    )
    states = [
        MobileArticleState(
            article_id=state.article_id,
            is_read=state.is_read,
            is_favorite=state.is_favorite,
            read_at=state.read_at,
        )
        for state in state_result.scalars().all()
    ] if offset == 0 else []

    return MobileSyncResponse(
        server_time=server_time,
        since=since,
        has_more=has_more,
        next_offset=offset + limit if has_more else None,
        categories=[
            _category_to_mobile(
                category,
                feed_counts_by_category.get(category.id, 0),
                unread_counts_by_category.get(category.id, 0),
            )
            for category in categories
        ],
        feeds=[
            _feed_to_mobile(feed, feed_counts.get(feed.id, {}))
            for feed in feeds
        ],
        articles=articles,
        states=states,
    )


@router.post("/actions", response_model=MobileActionsResponse)
async def apply_mobile_actions(
    data: MobileActionsRequest,
    user_id: CurrentUserId,
    db: DbSession,
):
    """Apply queued mobile article state changes."""
    repo = ArticleRepository(db)
    results: list[MobileActionResult] = []

    for action in data.actions:
        access_result = await db.execute(
            select(Article.id)
            .join(Feed, Article.feed_id == Feed.id)
            .where(Article.id == action.article_id, Feed.user_id == user_id)
        )
        if access_result.scalar_one_or_none() is None:
            results.append(MobileActionResult(
                client_action_id=action.client_action_id,
                article_id=action.article_id,
                type=action.type,
                status="not_found",
                detail="Article not found",
            ))
            continue

        user_article = await repo.get_or_create_user_article(user_id, action.article_id)
        now = datetime.utcnow()
        if action.type == "mark_read":
            user_article.is_read = True
            user_article.read_at = now
        elif action.type == "mark_unread":
            user_article.is_read = False
            user_article.read_at = None
        elif action.type == "set_favorite":
            user_article.is_favorite = bool(action.value)
            user_article.favorited_at = now if user_article.is_favorite else None
        await db.flush()

        results.append(MobileActionResult(
            client_action_id=action.client_action_id,
            article_id=action.article_id,
            type=action.type,
            status="ok",
        ))

    return MobileActionsResponse(results=results)
