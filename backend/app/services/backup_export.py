"""Backup data operations."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
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
from app.models.user import User
from app.services.backup_settings import get_webdav_config_from_db
from app.services.notification_backup import export_notification_settings


def _dt(value: Any) -> str | None:
    return value.isoformat() if value else None


def _json_vector(value: Any) -> list[float] | None:
    if value is None:
        return None
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value) if isinstance(value, (list, tuple)) else None


async def generate_backup_data(db: AsyncSession, user_id: int) -> dict:
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
    article_key_map = {
        article.id: (feed_urls.get(article.feed_id), article.guid) for article in articles
    }

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
        **await export_notification_settings(db, user_id),
        "version": "2.0",
        "exported_at": utc_now().isoformat(),
        "user_settings": {
            "translate_prompt": getattr(user, "translate_prompt", None),
            "summarize_prompt": getattr(user, "summarize_prompt", None),
            "auto_generate_summaries": getattr(user, "auto_generate_summaries", False),
            "embedding_provider_name": embedding_provider_name,
            "embedding_model": getattr(user, "embedding_model", None),
            "auto_generate_embeddings": getattr(user, "auto_generate_embeddings", False),
            "google_translate_api_key": getattr(user, "google_translate_api_key", None),
            "argos_source_language": getattr(user, "argos_source_language", None),
            "mc_translation_api_key": getattr(user, "mc_translation_api_key", None),
            "mc_translation_base_url": getattr(user, "mc_translation_base_url", None),
            "mc_translation_model": getattr(user, "mc_translation_model", None),
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
                "proxy_enabled": getattr(r, "proxy_enabled", False),
                "proxy_url": getattr(r, "proxy_url", None),
                "proxy_mode": getattr(
                    r,
                    "proxy_mode",
                    "single" if getattr(r, "proxy_enabled", False) else "none",
                ),
                "proxy_pool_country": getattr(r, "proxy_pool_country", None),
                "proxy_pool_protocol": getattr(r, "proxy_pool_protocol", None),
                "last_fetched_at": _dt(r.last_fetched_at),
                "last_error": r.last_error,
                "error_count": r.error_count,
                "auto_translate": getattr(r, "auto_translate", False),
                "auto_summarize": getattr(r, "auto_summarize", False),
                "source_language": getattr(r, "source_language", None),
                "target_language": getattr(r, "target_language", None),
                "translate_method": getattr(r, "translate_method", "none"),
                "translate_title": getattr(r, "translate_title", True),
                "translate_content": getattr(r, "translate_content", False),
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
                "excluded_category_ids": list(getattr(item, "excluded_category_ids", []) or []),
                "excluded_feed_ids": list(getattr(item, "excluded_feed_ids", []) or []),
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
