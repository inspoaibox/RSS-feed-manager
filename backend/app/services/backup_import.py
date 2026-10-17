"""Backup data operations."""

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException
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
from app.models.system_settings import SystemSettings
from app.models.user import User
from app.schemas.backup import BackupData, ImportResult
from app.services.backup_settings import WEBDAV_CONFIG_KEY
from app.services.notification_backup import import_notification_settings
from app.services.notification_outbox import suppress_import_notifications


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _apply_attrs(
    model: Any, data: dict, fields: list[str], datetime_fields: set[str] | None = None
) -> bool:
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


def _translation_settings(data: dict) -> dict:
    if data.get("translate_method") == "mc_translation":
        return {"translate_method": "none", "auto_translate": False}
    return {
        "translate_method": data.get("translate_method", "none"),
        "auto_translate": data.get("auto_translate", False),
    }


@suppress_import_notifications
async def import_backup_data(db: AsyncSession, user_id: int, data: dict) -> ImportResult:
    """Import backup data with update-or-create semantics."""
    from pydantic import ValidationError

    try:
        BackupData.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="备份结构无效") from exc
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if (data.get("recommended_feeds") or data.get("notifications")) and (
        not user or not user.is_admin
    ):
        raise HTTPException(status_code=403, detail="导入公共推荐或系统通知需要管理员权限")
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
            async with db.begin_nested():
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
                    if _apply_attrs(
                        existing, values, list(values.keys()), {"created_at", "updated_at"}
                    ):
                        _increment(import_result, "updated")
                    category_map[name] = existing.id
                else:
                    category = Category(user_id=user_id, name=name)
                    _apply_attrs(
                        category, values, list(values.keys()), {"created_at", "updated_at"}
                    )
                    db.add(category)
                    await db.flush()
                    category_map[name] = category.id
                    _increment(import_result, "categories_imported")
        except Exception as exc:
            add_error("分类", name, exc)

    # Keep existing categories available for feed/rule references.
    existing_categories = (
        (await db.execute(select(Category).where(Category.user_id == user_id))).scalars().all()
    )
    category_map.update({category.name: category.id for category in existing_categories})

    # Restoring a legacy backup must not reactivate the retired translator.
    retired_feed_urls = {
        (item.get("url") or "").strip()
        for item in data.get("feeds", [])
        if item.get("translate_method") == "mc_translation"
    }

    # Feeds
    for feed_data in data.get("feeds", []):
        url = (feed_data.get("url") or "").strip()
        if not url:
            continue
        try:
            async with db.begin_nested():
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
                    "proxy_url": feed_data.get("proxy_url")
                    if feed_data.get("proxy_enabled", False)
                    else None,
                    "proxy_mode": feed_data.get(
                        "proxy_mode",
                        "single" if feed_data.get("proxy_enabled", False) else "none",
                    ),
                    "proxy_pool_country": feed_data.get("proxy_pool_country"),
                    "proxy_pool_protocol": feed_data.get("proxy_pool_protocol"),
                    **_translation_settings(feed_data),
                    "translate_title": feed_data.get("translate_title", True),
                    "translate_content": feed_data.get("translate_content", False),
                    "auto_summarize": feed_data.get("auto_summarize", False),
                    "source_language": feed_data.get("source_language"),
                    "target_language": feed_data.get("target_language"),
                    "is_active": feed_data.get("is_active", True),
                    "position": feed_data.get("position", 0),
                    "created_at": feed_data.get("created_at"),
                    "updated_at": feed_data.get("updated_at"),
                }
                if existing:
                    if _apply_attrs(
                        existing,
                        values,
                        list(values.keys()),
                        {"last_fetched_at", "created_at", "updated_at"},
                    ):
                        _increment(import_result, "updated")
                    feed_map[url] = existing.id
                else:
                    feed = Feed(user_id=user_id, url=url)
                    _apply_attrs(
                        feed,
                        values,
                        list(values.keys()),
                        {"last_fetched_at", "created_at", "updated_at"},
                    )
                    db.add(feed)
                    await db.flush()
                    feed_map[url] = feed.id
                    _increment(import_result, "feeds_imported")
        except Exception as exc:
            add_error("订阅源", url, exc)

    existing_feeds = (await db.execute(select(Feed).where(Feed.user_id == user_id))).scalars().all()
    feed_map.update({feed.url: feed.id for feed in existing_feeds})

    # Articles
    for article_data in data.get("articles", []):
        feed_url = article_data.get("feed_url")
        guid = article_data.get("guid")
        feed_id = feed_map.get(feed_url)
        if not feed_id or not guid:
            continue
        try:
            async with db.begin_nested():
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
                    "translation_revision": max(
                        0, int(article_data.get("translation_revision") or 0)
                    ),
                    "translation_status": article_data.get("translation_status")
                    or ("completed" if article_data.get("translation") else "none"),
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
                if feed_url in retired_feed_urls and values["translation_status"] in {
                    "queued",
                    "translating",
                }:
                    values.update(
                        translation_status="completed" if values["translation"] else "none",
                        translation_error=None,
                        translation_started_at=None,
                        translation_completed_at=None,
                    )
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
    article_map.update(
        {(feed_url, article.guid): article.id for article, feed_url in existing_articles}
    )

    # User article states
    for state_data in data.get("user_articles", []):
        feed_url = state_data.get("feed_url")
        guid = state_data.get("guid")
        article_id = article_map.get((feed_url, guid))
        if not article_id:
            continue
        try:
            async with db.begin_nested():
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
                    if _apply_attrs(
                        existing, values, list(values.keys()), {"read_at", "favorited_at"}
                    ):
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
            async with db.begin_nested():
                existing = (
                    await db.execute(
                        select(AIProvider).where(
                            AIProvider.user_id == user_id, AIProvider.name == name
                        )
                    )
                ).scalar_one_or_none()
                values = {
                    "type": provider_data.get("type", "openai"),
                    "api_key": provider_data.get("api_key", ""),
                    "base_url": provider_data.get("base_url"),
                    "token_limit_parameter": provider_data.get("token_limit_parameter", "auto"),
                    "is_active": provider_data.get("is_active", True),
                    "created_at": provider_data.get("created_at"),
                    "updated_at": provider_data.get("updated_at"),
                }
                if existing:
                    if _apply_attrs(
                        existing, values, list(values.keys()), {"created_at", "updated_at"}
                    ):
                        _increment(import_result, "updated")
                    provider_map[name] = existing.id
                else:
                    provider = AIProvider(user_id=user_id, name=name)
                    _apply_attrs(
                        provider, values, list(values.keys()), {"created_at", "updated_at"}
                    )
                    db.add(provider)
                    await db.flush()
                    provider_map[name] = provider.id
                    _increment(import_result, "ai_providers_imported")
        except Exception as exc:
            add_error("AI 渠道", name, exc)

    existing_providers = (
        (await db.execute(select(AIProvider).where(AIProvider.user_id == user_id))).scalars().all()
    )
    provider_map.update({provider.name: provider.id for provider in existing_providers})

    # User settings that may depend on providers.
    user_settings = data.get("user_settings") or {}
    if isinstance(user_settings, dict):
        try:
            async with db.begin_nested():
                user = (
                    await db.execute(select(User).where(User.id == user_id))
                ).scalar_one_or_none()
                if user:
                    values = {
                        "translate_prompt": user_settings.get("translate_prompt"),
                        "summarize_prompt": user_settings.get("summarize_prompt"),
                        "auto_generate_summaries": bool(
                            user_settings.get("auto_generate_summaries", False)
                        ),
                        "embedding_provider_id": provider_map.get(
                            user_settings.get("embedding_provider_name")
                        ),
                        "embedding_model": user_settings.get("embedding_model"),
                        "auto_generate_embeddings": bool(
                            user_settings.get("auto_generate_embeddings", False)
                        ),
                        "google_translate_api_key": user_settings.get("google_translate_api_key"),
                        "argos_source_language": user_settings.get("argos_source_language"),
                    }
                    from app.schemas.ai import TranslationLimits

                    limits = TranslationLimits.model_validate(
                        {
                            name: user_settings.get(name, getattr(user, name))
                            for name in TranslationLimits.model_fields
                        }
                    )
                    values.update(limits.model_dump())
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
            async with db.begin_nested():
                existing = (
                    await db.execute(
                        select(AIModel).where(
                            AIModel.provider_id == provider_id, AIModel.model_id == model_id
                        )
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
                    if _apply_attrs(
                        existing, values, list(values.keys()), {"created_at", "updated_at"}
                    ):
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
            async with db.begin_nested():
                existing = (
                    await db.execute(
                        select(CustomRule).where(
                            CustomRule.user_id == user_id, CustomRule.target_url == target_url
                        )
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
                    "proxy_enabled": rule_data.get("proxy_enabled", False),
                    "proxy_url": rule_data.get("proxy_url")
                    if rule_data.get("proxy_enabled", False)
                    else None,
                    "proxy_mode": rule_data.get(
                        "proxy_mode",
                        "single" if rule_data.get("proxy_enabled", False) else "none",
                    ),
                    "proxy_pool_country": rule_data.get("proxy_pool_country"),
                    "proxy_pool_protocol": rule_data.get("proxy_pool_protocol"),
                    "last_fetched_at": rule_data.get("last_fetched_at"),
                    "last_error": rule_data.get("last_error"),
                    "error_count": rule_data.get("error_count", 0),
                    **_translation_settings(rule_data),
                    "auto_summarize": rule_data.get("auto_summarize", False),
                    "source_language": rule_data.get("source_language"),
                    "target_language": rule_data.get("target_language"),
                    "translate_title": rule_data.get("translate_title", True),
                    "translate_content": rule_data.get("translate_content", False),
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
            async with db.begin_nested():
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
                    "excluded_category_ids": list(item_data.get("excluded_category_ids") or []),
                    "excluded_feed_ids": list(item_data.get("excluded_feed_ids") or []),
                    "position": item_data.get("position", 0),
                    "created_at": item_data.get("created_at"),
                    "updated_at": item_data.get("updated_at"),
                }
                if existing:
                    if _apply_attrs(
                        existing, values, list(values.keys()), {"created_at", "updated_at"}
                    ):
                        _increment(import_result, "updated")
                else:
                    item = KeywordSubscription(
                        user_id=user_id, keyword=keyword, name=values["name"]
                    )
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
            async with db.begin_nested():
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
            async with db.begin_nested():
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
            async with db.begin_nested():
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
                    if _apply_attrs(
                        existing, values, list(values.keys()), {"created_at", "updated_at"}
                    ):
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
            async with db.begin_nested():
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
                    if _apply_attrs(
                        existing, values, list(values.keys()), {"created_at", "updated_at"}
                    ):
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
            async with db.begin_nested():
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
                    notification = Notification(
                        title=title, content=content, type=notification_type
                    )
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
            async with db.begin_nested():
                existing = (
                    await db.execute(
                        select(UserNotificationRead).where(
                            UserNotificationRead.user_id == user_id,
                            UserNotificationRead.notification_id == notification_id,
                        )
                    )
                ).scalar_one_or_none()
                values = {"read_at": read_data.get("read_at") or utc_now().isoformat()}
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

    import_result.errors.extend(await import_notification_settings(db, user_id, data))
    await db.commit()
    import_result.success = len(import_result.errors) == 0
    return import_result
