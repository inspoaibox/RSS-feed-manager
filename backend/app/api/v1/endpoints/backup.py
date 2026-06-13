"""Backup and restore API endpoints."""
import json
import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from webdav3.client import Client
from webdav3.exceptions import WebDavException

from app.api.deps import CurrentUserId, DbSession
from app.models.ai_provider import AIModel, AIProvider
from app.models.analysis_query import AnalysisQuery
from app.models.article import Article, UserArticle
from app.models.category import Category
from app.models.custom_rule import CustomRule
from app.models.feed import Feed
from app.models.google_translate_key import GoogleTranslateKey
from app.models.keyword_subscription import KeywordSubscription
from app.models.notification import Notification, UserNotificationRead
from app.models.proxy_pool import ProxyPoolEntry
from app.models.recommended_feed import RecommendedFeed
from app.models.system_settings import SystemSettings
from app.models.user import User
from sqlalchemy import select

router = APIRouter()


# WebDAV Configuration Models
class WebDAVConfig(BaseModel):
    """WebDAV configuration."""
    server_url: str
    username: str
    password: str
    backup_path: str = "/rss_manager_backups/"


class WebDAVConfigResponse(BaseModel):
    """WebDAV configuration response (without password)."""
    server_url: Optional[str] = None
    username: Optional[str] = None
    backup_path: str = "/rss_manager_backups/"
    configured: bool = False


class WebDAVBackupInfo(BaseModel):
    """WebDAV backup file info."""
    filename: str
    size: int
    modified: str


class WebDAVBackupList(BaseModel):
    """List of WebDAV backups."""
    backups: List[WebDAVBackupInfo]


def get_webdav_client(config: dict) -> Client:
    """Create WebDAV client from config."""
    options = {
        'webdav_hostname': config['server_url'],
        'webdav_login': config['username'],
        'webdav_password': config['password'],
    }
    return Client(options)


class BackupData(BaseModel):
    """Backup data structure."""
    version: str = "1.0"
    exported_at: str
    user_settings: Dict[str, Any] = Field(default_factory=dict)
    categories: List[Dict[str, Any]]
    feeds: List[Dict[str, Any]]
    articles: List[Dict[str, Any]] = Field(default_factory=list)
    user_articles: List[Dict[str, Any]] = Field(default_factory=list)
    ai_providers: List[Dict[str, Any]]
    ai_models: List[Dict[str, Any]]
    custom_rules: List[Dict[str, Any]]
    keyword_subscriptions: List[Dict[str, Any]] = Field(default_factory=list)
    proxy_pool_entries: List[Dict[str, Any]] = Field(default_factory=list)
    google_translate_keys: List[Dict[str, Any]] = Field(default_factory=list)
    analysis_queries: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_feeds: List[Dict[str, Any]] = Field(default_factory=list)
    notifications: List[Dict[str, Any]] = Field(default_factory=list)
    user_notification_reads: List[Dict[str, Any]] = Field(default_factory=list)


class ImportResult(BaseModel):
    """Import result."""
    success: bool
    categories_imported: int = 0
    feeds_imported: int = 0
    articles_imported: int = 0
    user_articles_imported: int = 0
    ai_providers_imported: int = 0
    ai_models_imported: int = 0
    custom_rules_imported: int = 0
    keyword_subscriptions_imported: int = 0
    proxy_pool_entries_imported: int = 0
    google_translate_keys_imported: int = 0
    analysis_queries_imported: int = 0
    recommended_feeds_imported: int = 0
    notifications_imported: int = 0
    user_notification_reads_imported: int = 0
    updated: int = 0
    errors: List[str] = Field(default_factory=list)


@router.get("/export")
async def export_all(user_id: CurrentUserId, db: DbSession):
    """Export all user settings and data."""
    backup = await generate_backup_data(db, user_id)
    content = json.dumps(backup, ensure_ascii=False, indent=2)
    filename = f"rss_manager_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/import", response_model=ImportResult)
async def import_all(
    file: UploadFile = File(...),
    user_id: CurrentUserId = None,
    db: DbSession = None
):
    """Import settings and data from backup file."""
    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError:
        return ImportResult(success=False, errors=["无效的 JSON 文件"])

    return await import_backup_data(db, user_id, data)


# ==================== WebDAV Backup APIs ====================

WEBDAV_CONFIG_KEY = "webdav_config"


async def get_webdav_config_from_db(db: DbSession, user_id: int) -> Optional[dict]:
    """Get WebDAV config from database."""
    result = await db.execute(
        select(SystemSettings).where(
            SystemSettings.key == f"{WEBDAV_CONFIG_KEY}_{user_id}"
        )
    )
    setting = result.scalar_one_or_none()
    if setting:
        return json.loads(setting.value)
    return None


async def save_webdav_config_to_db(db: DbSession, user_id: int, config: dict):
    """Save WebDAV config to database."""
    key = f"{WEBDAV_CONFIG_KEY}_{user_id}"
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = json.dumps(config)
    else:
        setting = SystemSettings(key=key, value=json.dumps(config))
        db.add(setting)
    
    await db.commit()


def _dt(value: Any) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _json_vector(value: Any) -> list[float] | None:
    if value is None:
        return None
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value) if isinstance(value, (list, tuple)) else None


def _apply_attrs(model: Any, data: dict, fields: list[str], datetime_fields: set[str] | None = None) -> bool:
    changed = False
    datetime_fields = datetime_fields or set()
    for field in fields:
        if field not in data:
            continue
        if field == "created_at" and not data.get(field):
            continue
        value = _parse_dt(data.get(field)) if field in datetime_fields else data.get(field)
        if getattr(model, field, None) != value:
            setattr(model, field, value)
            changed = True
    return changed


def _increment(result: ImportResult, field: str, amount: int = 1) -> None:
    setattr(result, field, getattr(result, field) + amount)


async def generate_backup_data(db: DbSession, user_id: int) -> dict:
    """Generate complete database-backed backup data for a user."""
    # Get user-level settings
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    # Get categories and feeds
    result = await db.execute(
        select(Category).where(Category.user_id == user_id).order_by(Category.position, Category.id)
    )
    categories = result.scalars().all()
    category_names = {category.id: category.name for category in categories}

    result = await db.execute(
        select(Feed).where(Feed.user_id == user_id).order_by(Feed.position, Feed.id)
    )
    feeds = result.scalars().all()
    feed_urls = {feed.id: feed.url for feed in feeds}

    # Get AI providers
    result = await db.execute(select(AIProvider).where(AIProvider.user_id == user_id))
    providers = result.scalars().all()
    provider_names = {provider.id: provider.name for provider in providers}

    provider_ids = [p.id for p in providers]
    models = []
    if provider_ids:
        result = await db.execute(select(AIModel).where(AIModel.provider_id.in_(provider_ids)))
        models = result.scalars().all()

    # Get custom rules
    result = await db.execute(select(CustomRule).where(CustomRule.user_id == user_id))
    rules = result.scalars().all()

    # Get articles and user state
    article_result = await db.execute(
        select(Article)
        .join(Feed, Article.feed_id == Feed.id)
        .where(Feed.user_id == user_id)
        .order_by(Article.published_at.desc().nullslast(), Article.id.desc())
    )
    articles = article_result.scalars().all()
    article_key_map = {article.id: (feed_urls.get(article.feed_id), article.guid) for article in articles}

    user_article_result = await db.execute(
        select(UserArticle)
        .join(Article, UserArticle.article_id == Article.id)
        .join(Feed, Article.feed_id == Feed.id)
        .where(UserArticle.user_id == user_id, Feed.user_id == user_id)
    )
    user_articles = user_article_result.scalars().all()

    result = await db.execute(
        select(KeywordSubscription)
        .where(KeywordSubscription.user_id == user_id)
        .order_by(KeywordSubscription.position, KeywordSubscription.id)
    )
    keyword_subscriptions = result.scalars().all()

    result = await db.execute(
        select(ProxyPoolEntry)
        .where(ProxyPoolEntry.user_id == user_id)
        .order_by(ProxyPoolEntry.created_at, ProxyPoolEntry.id)
    )
    proxy_pool_entries = result.scalars().all()

    result = await db.execute(
        select(GoogleTranslateKey)
        .where(GoogleTranslateKey.user_id == user_id)
        .order_by(GoogleTranslateKey.position, GoogleTranslateKey.id)
    )
    google_translate_keys = result.scalars().all()

    result = await db.execute(
        select(AnalysisQuery)
        .where(AnalysisQuery.user_id == user_id)
        .order_by(AnalysisQuery.created_at.desc())
    )
    analysis_queries = result.scalars().all()

    result = await db.execute(
        select(RecommendedFeed)
        .where(RecommendedFeed.created_by == user_id)
        .order_by(RecommendedFeed.created_at, RecommendedFeed.id)
    )
    recommended_feeds = result.scalars().all()

    result = await db.execute(
        select(Notification)
        .where(Notification.created_by == user_id)
        .order_by(Notification.created_at, Notification.id)
    )
    notifications = result.scalars().all()
    notification_keys = {
        notification.id: {
            "title": notification.title,
            "content": notification.content,
            "type": notification.type,
        }
        for notification in notifications
    }

    result = await db.execute(
        select(UserNotificationRead)
        .join(Notification, UserNotificationRead.notification_id == Notification.id)
        .where(UserNotificationRead.user_id == user_id)
    )
    user_notification_reads = result.scalars().all()

    embedding_provider_name = provider_names.get(user.embedding_provider_id) if user else None
    webdav_config = await get_webdav_config_from_db(db, user_id)

    return {
        "version": "2.0",
        "exported_at": datetime.utcnow().isoformat(),
        "user_settings": {
            "translate_prompt": getattr(user, "translate_prompt", None),
            "summarize_prompt": getattr(user, "summarize_prompt", None),
            "embedding_provider_name": embedding_provider_name,
            "embedding_model": getattr(user, "embedding_model", None),
            "google_translate_api_key": getattr(user, "google_translate_api_key", None),
            "argos_source_language": getattr(user, "argos_source_language", None),
            "webdav_config": webdav_config,
        },
        "categories": [
            {
                "name": c.name,
                "description": c.description,
                "position": c.position,
                "created_at": _dt(c.created_at),
                "updated_at": _dt(c.updated_at),
            }
            for c in categories
        ],
        "feeds": [
            {
                "url": f.url,
                "title": f.title,
                "description": f.description,
                "site_url": f.site_url,
                "icon_url": f.icon_url,
                "category_name": category_names.get(f.category_id),
                "fetch_interval": f.fetch_interval,
                "last_fetched_at": _dt(f.last_fetched_at),
                "last_error": f.last_error,
                "error_count": f.error_count,
                "is_active": f.is_active,
                "auto_translate": getattr(f, "auto_translate", False),
                "auto_summarize": getattr(f, "auto_summarize", False),
                "source_language": getattr(f, "source_language", None),
                "target_language": getattr(f, "target_language", None),
                "translate_method": getattr(f, "translate_method", "none"),
                "use_playwright": f.use_playwright,
                "browser_engine": getattr(
                    f,
                    "browser_engine",
                    "playwright" if f.use_playwright else "http",
                ),
                "proxy_enabled": getattr(f, "proxy_enabled", False),
                "proxy_url": getattr(f, "proxy_url", None),
                "proxy_mode": getattr(
                    f,
                    "proxy_mode",
                    "single" if getattr(f, "proxy_enabled", False) else "none",
                ),
                "proxy_pool_country": getattr(f, "proxy_pool_country", None),
                "proxy_pool_protocol": getattr(f, "proxy_pool_protocol", None),
                "position": f.position,
                "created_at": _dt(f.created_at),
                "updated_at": _dt(f.updated_at),
            }
            for f in feeds
        ],
        "articles": [
            {
                "feed_url": feed_urls.get(a.feed_id),
                "guid": a.guid,
                "link": a.link,
                "title": a.title,
                "content": a.content,
                "full_content": a.full_content,
                "summary": a.summary,
                "translation": a.translation,
                "translation_status": getattr(a, "translation_status", "none"),
                "translation_error": getattr(a, "translation_error", None),
                "translation_started_at": _dt(getattr(a, "translation_started_at", None)),
                "translation_completed_at": _dt(getattr(a, "translation_completed_at", None)),
                "author": a.author,
                "published_at": _dt(a.published_at),
                "cached_images": a.cached_images,
                "embedding": _json_vector(a.embedding),
                "created_at": _dt(a.created_at),
                "updated_at": _dt(a.updated_at),
            }
            for a in articles
            if feed_urls.get(a.feed_id)
        ],
        "user_articles": [
            {
                "feed_url": article_key_map.get(state.article_id, (None, None))[0],
                "guid": article_key_map.get(state.article_id, (None, None))[1],
                "is_read": state.is_read,
                "is_favorite": state.is_favorite,
                "read_at": _dt(state.read_at),
                "favorited_at": _dt(state.favorited_at),
            }
            for state in user_articles
            if article_key_map.get(state.article_id, (None, None))[0]
        ],
        "ai_providers": [
            {
                "name": p.name,
                "type": p.type,
                "api_key": p.api_key,
                "base_url": p.base_url,
                "is_active": p.is_active,
                "created_at": _dt(p.created_at),
                "updated_at": _dt(p.updated_at),
            }
            for p in providers
        ],
        "ai_models": [
            {
                "provider_name": provider_names.get(m.provider_id),
                "name": m.name,
                "model_id": m.model_id,
                "description": m.description,
                "is_default": m.is_default,
                "is_active": m.is_active,
                "created_at": _dt(m.created_at),
                "updated_at": _dt(m.updated_at),
            }
            for m in models
        ],
        "custom_rules": [
            {
                "name": r.name,
                "target_url": r.target_url,
                "feed_url": feed_urls.get(r.feed_id),
                "rule_type": getattr(r, "rule_type", "general"),
                "cookies": getattr(r, "cookies", None),
                "category_name": category_names.get(r.category_id),
                "list_selector": r.list_selector,
                "title_selector": r.title_selector,
                "link_selector": r.link_selector,
                "content_selector": r.content_selector,
                "date_selector": getattr(r, "date_selector", None),
                "fetch_interval": r.fetch_interval,
                "use_playwright": getattr(r, "use_playwright", False),
                "last_fetched_at": _dt(r.last_fetched_at),
                "last_error": r.last_error,
                "error_count": r.error_count,
                "auto_translate": getattr(r, "auto_translate", False),
                "auto_summarize": getattr(r, "auto_summarize", False),
                "source_language": getattr(r, "source_language", None),
                "target_language": getattr(r, "target_language", None),
                "translate_method": getattr(r, "translate_method", "none"),
                "is_active": r.is_active,
                "created_at": _dt(r.created_at),
                "updated_at": _dt(r.updated_at),
            }
            for r in rules
        ],
        "keyword_subscriptions": [
            {
                "name": item.name,
                "keyword": item.keyword,
                "is_active": item.is_active,
                "match_title": item.match_title,
                "match_content": item.match_content,
                "match_author": item.match_author,
                "match_feed_title": item.match_feed_title,
                "position": item.position,
                "created_at": _dt(item.created_at),
                "updated_at": _dt(item.updated_at),
            }
            for item in keyword_subscriptions
        ],
        "proxy_pool_entries": [
            {
                "protocol": item.protocol,
                "host": item.host,
                "port": item.port,
                "username": item.username,
                "password": item.password,
                "country": item.country,
                "source_format": item.source_format,
                "proxy_url": item.proxy_url,
                "is_active": item.is_active,
                "fail_count": item.fail_count,
                "last_used_at": _dt(item.last_used_at),
                "last_tested_at": _dt(item.last_tested_at),
                "last_latency_ms": item.last_latency_ms,
                "last_error": item.last_error,
                "created_at": _dt(item.created_at),
                "updated_at": _dt(item.updated_at),
            }
            for item in proxy_pool_entries
        ],
        "google_translate_keys": [
            {
                "name": item.name,
                "api_key": item.api_key,
                "is_active": item.is_active,
                "position": item.position,
                "limit_days": item.limit_days,
                "limit_articles": item.limit_articles,
                "limit_characters": item.limit_characters,
                "usage_started_at": _dt(item.usage_started_at),
                "usage_article_count": item.usage_article_count,
                "usage_character_count": item.usage_character_count,
                "last_used_at": _dt(item.last_used_at),
                "last_error": item.last_error,
                "fail_count": item.fail_count,
                "created_at": _dt(item.created_at),
                "updated_at": _dt(item.updated_at),
            }
            for item in google_translate_keys
        ],
        "analysis_queries": [
            {
                "query": item.query,
                "created_at": _dt(item.created_at),
                "updated_at": _dt(item.updated_at),
            }
            for item in analysis_queries
        ],
        "recommended_feeds": [
            {
                "url": item.url,
                "title": item.title,
                "description": item.description,
                "icon_url": item.icon_url,
                "categories": item.categories,
                "use_playwright": item.use_playwright,
                "is_active": item.is_active,
                "subscriber_count": item.subscriber_count,
                "created_at": _dt(item.created_at),
                "updated_at": _dt(item.updated_at),
            }
            for item in recommended_feeds
        ],
        "notifications": [
            {
                "title": item.title,
                "content": item.content,
                "type": item.type,
                "is_active": item.is_active,
                "expires_at": _dt(item.expires_at),
                "created_at": _dt(item.created_at),
                "updated_at": _dt(item.updated_at),
            }
            for item in notifications
        ],
        "user_notification_reads": [
            {
                **notification_keys.get(item.notification_id, {}),
                "read_at": _dt(item.read_at),
            }
            for item in user_notification_reads
            if notification_keys.get(item.notification_id)
        ],
    }


async def import_backup_data(db: DbSession, user_id: int, data: dict) -> ImportResult:
    """Import backup data with update-or-create semantics."""
    import_result = ImportResult(success=True)

    def add_error(label: str, item: Any, exc: Exception) -> None:
        import_result.errors.append(f"{label} '{item or '?'}': {str(exc)}")

    # Existing maps are refreshed as new objects are created.
    category_map: dict[str, int] = {}
    feed_map: dict[str, int] = {}
    article_map: dict[tuple[str, str], int] = {}
    provider_map: dict[str, int] = {}
    notification_map: dict[tuple[str, str, str], int] = {}

    # Categories
    for cat_data in data.get("categories", []):
        name = (cat_data.get("name") or "").strip()
        if not name:
            continue
        try:
            existing = (
                await db.execute(
                    select(Category).where(Category.user_id == user_id, Category.name == name)
                )
            ).scalar_one_or_none()
            values = {
                "description": cat_data.get("description"),
                "position": cat_data.get("position", 0),
                "created_at": cat_data.get("created_at"),
                "updated_at": cat_data.get("updated_at"),
            }
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), {"created_at", "updated_at"}):
                    _increment(import_result, "updated")
                category_map[name] = existing.id
            else:
                category = Category(user_id=user_id, name=name)
                _apply_attrs(category, values, list(values.keys()), {"created_at", "updated_at"})
                db.add(category)
                await db.flush()
                category_map[name] = category.id
                _increment(import_result, "categories_imported")
        except Exception as exc:
            add_error("分类", name, exc)

    # Keep existing categories available for feed/rule references.
    existing_categories = (
        await db.execute(select(Category).where(Category.user_id == user_id))
    ).scalars().all()
    category_map.update({category.name: category.id for category in existing_categories})

    # Feeds
    for feed_data in data.get("feeds", []):
        url = (feed_data.get("url") or "").strip()
        if not url:
            continue
        try:
            existing = (
                await db.execute(select(Feed).where(Feed.user_id == user_id, Feed.url == url))
            ).scalar_one_or_none()
            browser_engine = feed_data.get(
                "browser_engine",
                "playwright" if feed_data.get("use_playwright", False) else "http",
            )
            values = {
                "title": feed_data.get("title", ""),
                "description": feed_data.get("description"),
                "site_url": feed_data.get("site_url"),
                "icon_url": feed_data.get("icon_url"),
                "category_id": category_map.get(feed_data.get("category_name")),
                "fetch_interval": feed_data.get("fetch_interval", 3600),
                "last_fetched_at": feed_data.get("last_fetched_at"),
                "last_error": feed_data.get("last_error"),
                "error_count": feed_data.get("error_count", 0),
                "use_playwright": feed_data.get("use_playwright", browser_engine != "http"),
                "browser_engine": browser_engine,
                "proxy_enabled": feed_data.get("proxy_enabled", False),
                "proxy_url": feed_data.get("proxy_url") if feed_data.get("proxy_enabled", False) else None,
                "proxy_mode": feed_data.get(
                    "proxy_mode",
                    "single" if feed_data.get("proxy_enabled", False) else "none",
                ),
                "proxy_pool_country": feed_data.get("proxy_pool_country"),
                "proxy_pool_protocol": feed_data.get("proxy_pool_protocol"),
                "auto_translate": feed_data.get("auto_translate", False),
                "auto_summarize": feed_data.get("auto_summarize", False),
                "source_language": feed_data.get("source_language"),
                "target_language": feed_data.get("target_language"),
                "translate_method": feed_data.get("translate_method", "none"),
                "is_active": feed_data.get("is_active", True),
                "position": feed_data.get("position", 0),
                "created_at": feed_data.get("created_at"),
                "updated_at": feed_data.get("updated_at"),
            }
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), {"last_fetched_at", "created_at", "updated_at"}):
                    _increment(import_result, "updated")
                feed_map[url] = existing.id
            else:
                feed = Feed(user_id=user_id, url=url)
                _apply_attrs(feed, values, list(values.keys()), {"last_fetched_at", "created_at", "updated_at"})
                db.add(feed)
                await db.flush()
                feed_map[url] = feed.id
                _increment(import_result, "feeds_imported")
        except Exception as exc:
            add_error("订阅源", url, exc)

    existing_feeds = (
        await db.execute(select(Feed).where(Feed.user_id == user_id))
    ).scalars().all()
    feed_map.update({feed.url: feed.id for feed in existing_feeds})

    # Articles
    for article_data in data.get("articles", []):
        feed_url = article_data.get("feed_url")
        guid = article_data.get("guid")
        feed_id = feed_map.get(feed_url)
        if not feed_id or not guid:
            continue
        try:
            existing = (
                await db.execute(
                    select(Article).where(Article.feed_id == feed_id, Article.guid == guid)
                )
            ).scalar_one_or_none()
            values = {
                "link": article_data.get("link"),
                "title": article_data.get("title") or "Untitled",
                "content": article_data.get("content"),
                "full_content": article_data.get("full_content"),
                "summary": article_data.get("summary"),
                "translation": article_data.get("translation"),
                "translation_status": article_data.get("translation_status") or (
                    "completed" if article_data.get("translation") else "none"
                ),
                "translation_error": article_data.get("translation_error"),
                "translation_started_at": article_data.get("translation_started_at"),
                "translation_completed_at": article_data.get("translation_completed_at"),
                "author": article_data.get("author"),
                "published_at": article_data.get("published_at"),
                "cached_images": article_data.get("cached_images"),
                "embedding": article_data.get("embedding"),
                "created_at": article_data.get("created_at"),
                "updated_at": article_data.get("updated_at"),
            }
            datetime_fields = {
                "published_at",
                "translation_started_at",
                "translation_completed_at",
                "created_at",
                "updated_at",
            }
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), datetime_fields):
                    _increment(import_result, "updated")
                article_map[(feed_url, guid)] = existing.id
            else:
                article = Article(feed_id=feed_id, guid=guid, title=values["title"])
                _apply_attrs(article, values, list(values.keys()), datetime_fields)
                db.add(article)
                await db.flush()
                article_map[(feed_url, guid)] = article.id
                _increment(import_result, "articles_imported")
        except Exception as exc:
            add_error("文章", guid, exc)

    existing_articles = (
        await db.execute(
            select(Article, Feed.url)
            .join(Feed, Article.feed_id == Feed.id)
            .where(Feed.user_id == user_id)
        )
    ).all()
    article_map.update({(feed_url, article.guid): article.id for article, feed_url in existing_articles})

    # User article states
    for state_data in data.get("user_articles", []):
        feed_url = state_data.get("feed_url")
        guid = state_data.get("guid")
        article_id = article_map.get((feed_url, guid))
        if not article_id:
            continue
        try:
            existing = (
                await db.execute(
                    select(UserArticle).where(
                        UserArticle.user_id == user_id,
                        UserArticle.article_id == article_id,
                    )
                )
            ).scalar_one_or_none()
            values = {
                "is_read": state_data.get("is_read", False),
                "is_favorite": state_data.get("is_favorite", False),
                "read_at": state_data.get("read_at"),
                "favorited_at": state_data.get("favorited_at"),
            }
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), {"read_at", "favorited_at"}):
                    _increment(import_result, "updated")
            else:
                state = UserArticle(user_id=user_id, article_id=article_id)
                _apply_attrs(state, values, list(values.keys()), {"read_at", "favorited_at"})
                db.add(state)
                _increment(import_result, "user_articles_imported")
        except Exception as exc:
            add_error("阅读状态", guid, exc)

    # AI providers
    for provider_data in data.get("ai_providers", []):
        name = (provider_data.get("name") or "").strip()
        if not name:
            continue
        try:
            existing = (
                await db.execute(
                    select(AIProvider).where(AIProvider.user_id == user_id, AIProvider.name == name)
                )
            ).scalar_one_or_none()
            values = {
                "type": provider_data.get("type", "openai"),
                "api_key": provider_data.get("api_key", ""),
                "base_url": provider_data.get("base_url"),
                "is_active": provider_data.get("is_active", True),
                "created_at": provider_data.get("created_at"),
                "updated_at": provider_data.get("updated_at"),
            }
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), {"created_at", "updated_at"}):
                    _increment(import_result, "updated")
                provider_map[name] = existing.id
            else:
                provider = AIProvider(user_id=user_id, name=name)
                _apply_attrs(provider, values, list(values.keys()), {"created_at", "updated_at"})
                db.add(provider)
                await db.flush()
                provider_map[name] = provider.id
                _increment(import_result, "ai_providers_imported")
        except Exception as exc:
            add_error("AI 渠道", name, exc)

    existing_providers = (
        await db.execute(select(AIProvider).where(AIProvider.user_id == user_id))
    ).scalars().all()
    provider_map.update({provider.name: provider.id for provider in existing_providers})

    # User settings that may depend on providers.
    user_settings = data.get("user_settings") or {}
    if isinstance(user_settings, dict):
        try:
            user = (
                await db.execute(select(User).where(User.id == user_id))
            ).scalar_one_or_none()
            if user:
                values = {
                    "translate_prompt": user_settings.get("translate_prompt"),
                    "summarize_prompt": user_settings.get("summarize_prompt"),
                    "embedding_provider_id": provider_map.get(user_settings.get("embedding_provider_name")),
                    "embedding_model": user_settings.get("embedding_model"),
                    "google_translate_api_key": user_settings.get("google_translate_api_key"),
                    "argos_source_language": user_settings.get("argos_source_language"),
                }
                if _apply_attrs(user, values, list(values.keys())):
                    _increment(import_result, "updated")
            webdav_config = user_settings.get("webdav_config")
            if isinstance(webdav_config, dict) and webdav_config.get("server_url"):
                key = f"{WEBDAV_CONFIG_KEY}_{user_id}"
                setting = (
                    await db.execute(select(SystemSettings).where(SystemSettings.key == key))
                ).scalar_one_or_none()
                serialized = json.dumps(webdav_config)
                if setting:
                    if setting.value != serialized:
                        setting.value = serialized
                        _increment(import_result, "updated")
                else:
                    db.add(SystemSettings(key=key, value=serialized))
                    _increment(import_result, "updated")
        except Exception as exc:
            add_error("用户设置", "user_settings", exc)

    # AI models
    for model_data in data.get("ai_models", []):
        provider_id = provider_map.get(model_data.get("provider_name"))
        model_id = model_data.get("model_id")
        if not provider_id or not model_id:
            continue
        try:
            existing = (
                await db.execute(
                    select(AIModel).where(AIModel.provider_id == provider_id, AIModel.model_id == model_id)
                )
            ).scalar_one_or_none()
            values = {
                "name": model_data.get("name") or model_id,
                "description": model_data.get("description"),
                "is_default": model_data.get("is_default", False),
                "is_active": model_data.get("is_active", True),
                "created_at": model_data.get("created_at"),
                "updated_at": model_data.get("updated_at"),
            }
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), {"created_at", "updated_at"}):
                    _increment(import_result, "updated")
            else:
                model = AIModel(provider_id=provider_id, model_id=model_id, name=values["name"])
                _apply_attrs(model, values, list(values.keys()), {"created_at", "updated_at"})
                db.add(model)
                _increment(import_result, "ai_models_imported")
        except Exception as exc:
            add_error("AI 模型", model_data.get("name"), exc)

    # Custom rules
    for rule_data in data.get("custom_rules", []):
        target_url = (rule_data.get("target_url") or "").strip()
        if not target_url:
            continue
        try:
            existing = (
                await db.execute(
                    select(CustomRule).where(CustomRule.user_id == user_id, CustomRule.target_url == target_url)
                )
            ).scalar_one_or_none()
            values = {
                "name": rule_data.get("name") or target_url,
                "feed_id": feed_map.get(rule_data.get("feed_url")) or feed_map.get(target_url),
                "rule_type": rule_data.get("rule_type", "general"),
                "cookies": rule_data.get("cookies"),
                "category_id": category_map.get(rule_data.get("category_name")),
                "list_selector": rule_data.get("list_selector", ""),
                "title_selector": rule_data.get("title_selector", ""),
                "link_selector": rule_data.get("link_selector"),
                "content_selector": rule_data.get("content_selector"),
                "date_selector": rule_data.get("date_selector"),
                "fetch_interval": rule_data.get("fetch_interval", 3600),
                "use_playwright": rule_data.get("use_playwright", False),
                "last_fetched_at": rule_data.get("last_fetched_at"),
                "last_error": rule_data.get("last_error"),
                "error_count": rule_data.get("error_count", 0),
                "auto_translate": rule_data.get("auto_translate", False),
                "auto_summarize": rule_data.get("auto_summarize", False),
                "source_language": rule_data.get("source_language"),
                "target_language": rule_data.get("target_language"),
                "translate_method": rule_data.get("translate_method", "none"),
                "is_active": rule_data.get("is_active", True),
                "created_at": rule_data.get("created_at"),
                "updated_at": rule_data.get("updated_at"),
            }
            datetime_fields = {"last_fetched_at", "created_at", "updated_at"}
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), datetime_fields):
                    _increment(import_result, "updated")
            else:
                rule = CustomRule(user_id=user_id, target_url=target_url, name=values["name"])
                _apply_attrs(rule, values, list(values.keys()), datetime_fields)
                db.add(rule)
                _increment(import_result, "custom_rules_imported")
        except Exception as exc:
            add_error("自定义规则", rule_data.get("name") or target_url, exc)

    # Keyword subscriptions
    for item_data in data.get("keyword_subscriptions", []):
        keyword = (item_data.get("keyword") or "").strip()
        if not keyword:
            continue
        try:
            existing = (
                await db.execute(
                    select(KeywordSubscription).where(
                        KeywordSubscription.user_id == user_id,
                        KeywordSubscription.keyword == keyword,
                    )
                )
            ).scalar_one_or_none()
            values = {
                "name": item_data.get("name") or keyword,
                "is_active": item_data.get("is_active", True),
                "match_title": item_data.get("match_title", True),
                "match_content": item_data.get("match_content", True),
                "match_author": item_data.get("match_author", False),
                "match_feed_title": item_data.get("match_feed_title", False),
                "position": item_data.get("position", 0),
                "created_at": item_data.get("created_at"),
                "updated_at": item_data.get("updated_at"),
            }
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), {"created_at", "updated_at"}):
                    _increment(import_result, "updated")
            else:
                item = KeywordSubscription(user_id=user_id, keyword=keyword, name=values["name"])
                _apply_attrs(item, values, list(values.keys()), {"created_at", "updated_at"})
                db.add(item)
                _increment(import_result, "keyword_subscriptions_imported")
        except Exception as exc:
            add_error("关键词订阅", keyword, exc)

    # Proxy pool entries
    for proxy_data in data.get("proxy_pool_entries", []):
        proxy_url = proxy_data.get("proxy_url")
        if not proxy_url:
            continue
        try:
            existing = (
                await db.execute(
                    select(ProxyPoolEntry).where(
                        ProxyPoolEntry.user_id == user_id,
                        ProxyPoolEntry.proxy_url == proxy_url,
                    )
                )
            ).scalar_one_or_none()
            values = {
                "protocol": proxy_data.get("protocol", "http"),
                "host": proxy_data.get("host", ""),
                "port": proxy_data.get("port", 0),
                "username": proxy_data.get("username"),
                "password": proxy_data.get("password"),
                "country": proxy_data.get("country"),
                "source_format": proxy_data.get("source_format", "backup"),
                "is_active": proxy_data.get("is_active", True),
                "fail_count": proxy_data.get("fail_count", 0),
                "last_used_at": proxy_data.get("last_used_at"),
                "last_tested_at": proxy_data.get("last_tested_at"),
                "last_latency_ms": proxy_data.get("last_latency_ms"),
                "last_error": proxy_data.get("last_error"),
                "created_at": proxy_data.get("created_at"),
                "updated_at": proxy_data.get("updated_at"),
            }
            datetime_fields = {"last_used_at", "last_tested_at", "created_at", "updated_at"}
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), datetime_fields):
                    _increment(import_result, "updated")
            else:
                proxy = ProxyPoolEntry(user_id=user_id, proxy_url=proxy_url)
                _apply_attrs(proxy, values, list(values.keys()), datetime_fields)
                db.add(proxy)
                _increment(import_result, "proxy_pool_entries_imported")
        except Exception as exc:
            add_error("代理", proxy_url, exc)

    # Google Translate keys
    for key_data in data.get("google_translate_keys", []):
        api_key = key_data.get("api_key")
        if not api_key:
            continue
        try:
            existing = (
                await db.execute(
                    select(GoogleTranslateKey).where(
                        GoogleTranslateKey.user_id == user_id,
                        GoogleTranslateKey.api_key == api_key,
                    )
                )
            ).scalar_one_or_none()
            values = {
                "name": key_data.get("name") or "Google Translate Key",
                "is_active": key_data.get("is_active", True),
                "position": key_data.get("position", 0),
                "limit_days": key_data.get("limit_days"),
                "limit_articles": key_data.get("limit_articles"),
                "limit_characters": key_data.get("limit_characters"),
                "usage_started_at": key_data.get("usage_started_at"),
                "usage_article_count": key_data.get("usage_article_count", 0),
                "usage_character_count": key_data.get("usage_character_count", 0),
                "last_used_at": key_data.get("last_used_at"),
                "last_error": key_data.get("last_error"),
                "fail_count": key_data.get("fail_count", 0),
                "created_at": key_data.get("created_at"),
                "updated_at": key_data.get("updated_at"),
            }
            datetime_fields = {"usage_started_at", "last_used_at", "created_at", "updated_at"}
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), datetime_fields):
                    _increment(import_result, "updated")
            else:
                key = GoogleTranslateKey(user_id=user_id, api_key=api_key, name=values["name"])
                _apply_attrs(key, values, list(values.keys()), datetime_fields)
                db.add(key)
                _increment(import_result, "google_translate_keys_imported")
        except Exception as exc:
            add_error("Google Translate Key", key_data.get("name"), exc)

    # Analysis query history
    for query_data in data.get("analysis_queries", []):
        query_text = query_data.get("query")
        if not query_text:
            continue
        try:
            existing = (
                await db.execute(
                    select(AnalysisQuery).where(
                        AnalysisQuery.user_id == user_id,
                        AnalysisQuery.query == query_text,
                    )
                )
            ).scalar_one_or_none()
            values = {
                "created_at": query_data.get("created_at"),
                "updated_at": query_data.get("updated_at"),
            }
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), {"created_at", "updated_at"}):
                    _increment(import_result, "updated")
            else:
                query = AnalysisQuery(user_id=user_id, query=query_text)
                _apply_attrs(query, values, list(values.keys()), {"created_at", "updated_at"})
                db.add(query)
                _increment(import_result, "analysis_queries_imported")
        except Exception as exc:
            add_error("分析历史", query_text, exc)

    # Admin-created recommendation data
    for item_data in data.get("recommended_feeds", []):
        url = item_data.get("url")
        if not url:
            continue
        try:
            existing = (
                await db.execute(select(RecommendedFeed).where(RecommendedFeed.url == url))
            ).scalar_one_or_none()
            values = {
                "title": item_data.get("title") or url,
                "description": item_data.get("description"),
                "icon_url": item_data.get("icon_url"),
                "categories": item_data.get("categories", ""),
                "use_playwright": item_data.get("use_playwright", False),
                "is_active": item_data.get("is_active", True),
                "subscriber_count": item_data.get("subscriber_count", 0),
                "created_by": user_id,
                "created_at": item_data.get("created_at"),
                "updated_at": item_data.get("updated_at"),
            }
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), {"created_at", "updated_at"}):
                    _increment(import_result, "updated")
            else:
                item = RecommendedFeed(url=url, title=values["title"])
                _apply_attrs(item, values, list(values.keys()), {"created_at", "updated_at"})
                db.add(item)
                _increment(import_result, "recommended_feeds_imported")
        except Exception as exc:
            add_error("推荐订阅", item_data.get("title") or url, exc)

    # Admin-created notifications
    for notification_data in data.get("notifications", []):
        title = notification_data.get("title")
        content = notification_data.get("content")
        notification_type = notification_data.get("type", "system")
        if not title or not content:
            continue
        notification_key = (title, content, notification_type)
        try:
            existing = (
                await db.execute(
                    select(Notification).where(
                        Notification.title == title,
                        Notification.content == content,
                        Notification.type == notification_type,
                    )
                )
            ).scalar_one_or_none()
            values = {
                "is_active": notification_data.get("is_active", True),
                "created_by": user_id,
                "expires_at": notification_data.get("expires_at"),
                "created_at": notification_data.get("created_at"),
                "updated_at": notification_data.get("updated_at"),
            }
            datetime_fields = {"expires_at", "created_at", "updated_at"}
            if existing:
                if _apply_attrs(existing, values, list(values.keys()), datetime_fields):
                    _increment(import_result, "updated")
                notification_map[notification_key] = existing.id
            else:
                notification = Notification(title=title, content=content, type=notification_type)
                _apply_attrs(notification, values, list(values.keys()), datetime_fields)
                db.add(notification)
                await db.flush()
                notification_map[notification_key] = notification.id
                _increment(import_result, "notifications_imported")
        except Exception as exc:
            add_error("通知", title, exc)

    existing_notifications = (await db.execute(select(Notification))).scalars().all()
    notification_map.update(
        {
            (notification.title, notification.content, notification.type): notification.id
            for notification in existing_notifications
        }
    )

    for read_data in data.get("user_notification_reads", []):
        title = read_data.get("title")
        content = read_data.get("content")
        notification_type = read_data.get("type", "system")
        notification_id = notification_map.get((title, content, notification_type))
        if not notification_id:
            continue
        try:
            existing = (
                await db.execute(
                    select(UserNotificationRead).where(
                        UserNotificationRead.user_id == user_id,
                        UserNotificationRead.notification_id == notification_id,
                    )
                )
            ).scalar_one_or_none()
            values = {"read_at": read_data.get("read_at") or datetime.utcnow().isoformat()}
            if existing:
                if _apply_attrs(existing, values, ["read_at"], {"read_at"}):
                    _increment(import_result, "updated")
            else:
                state = UserNotificationRead(user_id=user_id, notification_id=notification_id)
                _apply_attrs(state, values, ["read_at"], {"read_at"})
                db.add(state)
                _increment(import_result, "user_notification_reads_imported")
        except Exception as exc:
            add_error("通知阅读状态", title, exc)

    await db.commit()
    import_result.success = len(import_result.errors) == 0
    return import_result


@router.get("/webdav/config", response_model=WebDAVConfigResponse)
async def get_webdav_config(user_id: CurrentUserId, db: DbSession):
    """Get WebDAV configuration (without password)."""
    config = await get_webdav_config_from_db(db, user_id)
    if config:
        return WebDAVConfigResponse(
            server_url=config.get("server_url"),
            username=config.get("username"),
            backup_path=config.get("backup_path", "/rss_manager_backups/"),
            configured=True,
        )
    return WebDAVConfigResponse(configured=False)


@router.post("/webdav/config")
async def save_webdav_config(config: WebDAVConfig, user_id: CurrentUserId, db: DbSession):
    """Save WebDAV configuration."""
    # If password is empty, try to use existing password
    config_dict = config.dict()
    if not config_dict.get("password"):
        existing_config = await get_webdav_config_from_db(db, user_id)
        if existing_config and existing_config.get("password"):
            config_dict["password"] = existing_config["password"]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码不能为空"
            )
    
    # Test connection first
    try:
        client = get_webdav_client(config_dict)
        # Try to check if backup path exists, create if not
        backup_path = config_dict["backup_path"].rstrip('/') + '/'
        if not client.check(backup_path):
            client.mkdir(backup_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"WebDAV 连接失败: {str(e)}"
        )
    
    await save_webdav_config_to_db(db, user_id, config_dict)
    return {"success": True, "message": "WebDAV 配置已保存"}


@router.post("/webdav/test")
async def test_webdav_connection(config: WebDAVConfig, user_id: CurrentUserId, db: DbSession):
    """Test WebDAV connection without saving."""
    config_dict = config.dict()
    if not config_dict.get("password"):
        existing_config = await get_webdav_config_from_db(db, user_id)
        if existing_config and existing_config.get("password"):
            config_dict["password"] = existing_config["password"]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码不能为空"
            )
    
    try:
        client = get_webdav_client(config_dict)
        # Test by checking root or backup path
        backup_path = config_dict["backup_path"].rstrip('/') + '/'
        # Try to list root to verify connection
        client.list("/")
        return {"success": True, "message": "WebDAV 连接成功"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"WebDAV 连接失败: {str(e)}"
        )


@router.get("/webdav/list", response_model=WebDAVBackupList)
async def list_webdav_backups(user_id: CurrentUserId, db: DbSession):
    """List all backups from WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        
        if not client.check(backup_path):
            return WebDAVBackupList(backups=[])
        
        # webdavclient3 list() returns list of filenames (strings)
        files = client.list(backup_path)
        backups = []
        
        for filename in files:
            # Skip empty strings and non-json files
            if not filename or not filename.endswith('.json'):
                continue
            
            # Try to get file info
            try:
                remote_path = backup_path + filename
                info = client.info(remote_path)
                size = int(info.get('size', 0) or 0)
                modified = str(info.get('modified', '') or '')
            except Exception:
                size = 0
                modified = ''
            
            backups.append(WebDAVBackupInfo(
                filename=filename,
                size=size,
                modified=modified,
            ))
        
        # Sort by filename descending (since filenames contain timestamps)
        backups.sort(key=lambda x: x.filename, reverse=True)
        return WebDAVBackupList(backups=backups)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取备份列表失败: {str(e)}"
        )


@router.post("/webdav/upload")
async def upload_to_webdav(user_id: CurrentUserId, db: DbSession):
    """Upload current backup to WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        # Generate backup data
        backup_data = await generate_backup_data(db, user_id)
        content = json.dumps(backup_data, ensure_ascii=False, indent=2)
        
        # Upload to WebDAV
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        filename = f"rss_manager_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        remote_path = backup_path + filename
        
        # Ensure backup directory exists
        if not client.check(backup_path):
            client.mkdir(backup_path)
        
        # Upload using buffer
        buffer = io.BytesIO(content.encode('utf-8'))
        client.upload_to(buffer, remote_path)
        
        return {"success": True, "filename": filename, "message": "备份已上传到 WebDAV"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传备份失败: {str(e)}"
        )


@router.get("/webdav/download/{filename}")
async def download_from_webdav(filename: str, user_id: CurrentUserId, db: DbSession):
    """Download a specific backup from WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        remote_path = backup_path + filename
        
        if not client.check(remote_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="备份文件不存在"
            )
        
        # Download to buffer
        buffer = io.BytesIO()
        client.download_from(remote_path, buffer)
        buffer.seek(0)
        content = buffer.read()
        
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载备份失败: {str(e)}"
        )


@router.post("/webdav/restore/{filename}", response_model=ImportResult)
async def restore_from_webdav(filename: str, user_id: CurrentUserId, db: DbSession):
    """Restore from a specific WebDAV backup."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        remote_path = backup_path + filename
        
        if not client.check(remote_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="备份文件不存在"
            )
        
        # Download backup content
        buffer = io.BytesIO()
        client.download_from(remote_path, buffer)
        buffer.seek(0)
        content = buffer.read()
        
        # Parse and import
        try:
            data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError:
            return ImportResult(success=False, errors=["无效的 JSON 文件"])
        
        return await import_backup_data(db, user_id, data)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复备份失败: {str(e)}"
        )


@router.delete("/webdav/delete/{filename}")
async def delete_webdav_backup(filename: str, user_id: CurrentUserId, db: DbSession):
    """Delete a specific backup from WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        remote_path = backup_path + filename
        
        if not client.check(remote_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="备份文件不存在"
            )
        
        client.clean(remote_path)
        return {"success": True, "message": "备份已删除"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除备份失败: {str(e)}"
        )
