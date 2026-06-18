"""Feed-related background tasks."""
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.article import Article
from app.models.argos_translation_log import ArgosTranslationLog
from app.models.feed import Feed
from app.models.custom_rule import CustomRule
from app.models.proxy_pool import ProxyPoolEntry
from app.models.ai_provider import AIModel, AIProvider
from app.services.browser_fetch_settings import load_browser_fetch_settings_sync
from app.utils.feed_parser import (
    FeedParserError,
    ParsedFeed,
    _apply_browser_resource_blocking,
    _build_playwright_proxy,
    parse_feed,
)


# Create sync engine for Celery tasks
# Read DATABASE_URL directly from environment to avoid caching issues
def get_sync_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./rss_manager.db")
    if "postgresql+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    elif "sqlite+aiosqlite" in url:
        return url.replace("sqlite+aiosqlite", "sqlite")
    return url


# Lazy initialization of database engine
_sync_engine = None
_SyncSessionLocal = None
FEED_REFRESH_QUEUE_LOCK_TTL = int(os.environ.get("FEED_REFRESH_QUEUE_LOCK_TTL", "14400"))
ARTICLE_TRANSLATION_QUEUE_LOCK_TTL = int(os.environ.get("ARTICLE_TRANSLATION_QUEUE_LOCK_TTL", "14400"))
CUSTOM_RULE_EXECUTION_QUEUE_LOCK_TTL = int(os.environ.get("CUSTOM_RULE_EXECUTION_QUEUE_LOCK_TTL", "14400"))
FEED_REFRESH_DISPATCH_LIMIT = int(os.environ.get("FEED_REFRESH_DISPATCH_LIMIT", "100"))
CUSTOM_RULE_DISPATCH_LIMIT = int(os.environ.get("CUSTOM_RULE_DISPATCH_LIMIT", "10"))


def get_sync_session():
    """Get a sync database session, initializing engine if needed."""
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        _sync_engine = create_engine(get_sync_database_url())
        _SyncSessionLocal = sessionmaker(bind=_sync_engine)
    return _SyncSessionLocal()


def get_redis_client():
    """Get a Redis client for Celery coordination locks."""
    import redis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


def _feed_refresh_slot_key(feed_id: int) -> str:
    return f"refresh_feed_{feed_id}_queued_or_running"


def _redis_value_matches(value, expected: str) -> bool:
    if value is None:
        return False
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace") == expected
    return str(value) == expected


def _acquire_feed_refresh_slot(redis_client, feed_id: int, owner: str) -> bool:
    return bool(
        redis_client.set(
            _feed_refresh_slot_key(feed_id),
            owner,
            nx=True,
            ex=FEED_REFRESH_QUEUE_LOCK_TTL,
        )
    )


def _refresh_feed_slot_for_worker(redis_client, feed_id: int, owner: str) -> bool:
    key = _feed_refresh_slot_key(feed_id)
    current_owner = redis_client.get(key)

    if current_owner is None:
        return _acquire_feed_refresh_slot(redis_client, feed_id, owner)

    if _redis_value_matches(current_owner, owner):
        redis_client.expire(key, FEED_REFRESH_QUEUE_LOCK_TTL)
        return True

    return False


def _release_feed_refresh_slot(redis_client, feed_id: int, owner: str) -> None:
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """
    try:
        redis_client.eval(script, 1, _feed_refresh_slot_key(feed_id), owner)
    except Exception:
        pass


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo else value


def _next_fetch_at(last_fetched_at: datetime | None, fetch_interval: int | None) -> datetime:
    last_fetched = _naive_utc(last_fetched_at)
    if last_fetched is None:
        return datetime.min
    return last_fetched + timedelta(seconds=fetch_interval or 0)


def _current_task_queue(task) -> str | None:
    delivery_info = getattr(getattr(task, "request", None), "delivery_info", None) or {}
    return delivery_info.get("routing_key") or delivery_info.get("queue")


def _feed_uses_browser(feed: Feed) -> bool:
    if getattr(feed, "use_playwright", False):
        return True
    engine = (getattr(feed, "browser_engine", None) or "").strip().lower()
    return bool(engine and engine != "http")


def _feed_browser_engine_for_parse(feed: Feed) -> str | None:
    engine = (getattr(feed, "browser_engine", None) or "").strip().lower()
    if getattr(feed, "use_playwright", False) and (not engine or engine == "http"):
        return "playwright"
    return engine or None


def _rule_uses_browser(rule: CustomRule) -> bool:
    return bool(getattr(rule, "use_playwright", False))


def _custom_rule_execution_slot_key(rule_id: int) -> str:
    return f"execute_custom_rule_{rule_id}_queued_or_running"


def _acquire_custom_rule_execution_slot(redis_client, rule_id: int, owner: str) -> bool:
    return bool(
        redis_client.set(
            _custom_rule_execution_slot_key(rule_id),
            owner,
            nx=True,
            ex=CUSTOM_RULE_EXECUTION_QUEUE_LOCK_TTL,
        )
    )


def _refresh_custom_rule_slot_for_worker(redis_client, rule_id: int, owner: str) -> bool:
    key = _custom_rule_execution_slot_key(rule_id)
    current_owner = redis_client.get(key)

    if current_owner is None:
        return _acquire_custom_rule_execution_slot(redis_client, rule_id, owner)

    if _redis_value_matches(current_owner, owner):
        redis_client.expire(key, CUSTOM_RULE_EXECUTION_QUEUE_LOCK_TTL)
        return True

    return False


def _release_custom_rule_execution_slot(redis_client, rule_id: int, owner: str) -> None:
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """
    try:
        redis_client.eval(script, 1, _custom_rule_execution_slot_key(rule_id), owner)
    except Exception:
        pass


def _article_translation_slot_key(article_id: int) -> str:
    return f"translate_article_{article_id}_queued_or_running"


def _acquire_article_translation_slot(redis_client, article_id: int, owner: str) -> bool:
    return bool(
        redis_client.set(
            _article_translation_slot_key(article_id),
            owner,
            nx=True,
            ex=ARTICLE_TRANSLATION_QUEUE_LOCK_TTL,
        )
    )


def _release_article_translation_slot(redis_client, article_id: int, owner: str) -> None:
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """
    try:
        redis_client.eval(script, 1, _article_translation_slot_key(article_id), owner)
    except Exception:
        pass


def _translation_method_for_feed(feed: Feed) -> str:
    return getattr(feed, "translate_method", None) or ("ai" if feed.auto_translate else "none")


def _has_translatable_article_text(article: Article) -> bool:
    return bool((article.title or "").strip() or (article.content or "").strip())


def _mark_article_translation_queued(
    db: Session,
    article: Article,
    feed: Feed,
    *,
    force: bool = False,
) -> bool:
    """Mark an article as queued for translation if the feed is configured for it."""
    translate_method = _translation_method_for_feed(feed)
    if translate_method == "none" or not feed.target_language:
        if not article.translation:
            article.translation_status = "none"
            article.translation_error = None
            db.flush()
        return False

    if not force and article.translation_status in {"queued", "translating"}:
        return False

    if not force and _translation_has_title(article.translation):
        article.translation_status = "completed"
        article.translation_error = None
        db.flush()
        return False

    if not _has_translatable_article_text(article):
        article.translation_status = "failed"
        article.translation_error = "Article has no content to translate"
        db.flush()
        return False

    article.translation_status = "queued"
    article.translation_error = None
    article.translation_started_at = None
    article.translation_completed_at = None
    db.flush()
    return True


def dispatch_article_translation(article_id: int, target_language: str | None = None, force_full: bool = False) -> tuple[bool, str | None]:
    """Dispatch a single-article translation task with a Redis dedupe lock.

    Args:
        article_id: Article ID
        target_language: Target language code
        force_full: 如果为 True，强制翻译标题+正文，忽略 Feed 的 translate_title/translate_content 配置
    """
    owner = str(uuid.uuid4())
    redis_client = None
    lock_acquired = False

    try:
        redis_client = get_redis_client()
        lock_acquired = _acquire_article_translation_slot(redis_client, article_id, owner)
        if not lock_acquired:
            return False, "duplicate"

        kwargs = {}
        if target_language:
            kwargs["target_language"] = target_language
        if force_full:
            kwargs["force_full"] = True

        from app.tasks.celery_app import celery_app

        celery_app.send_task(
            "app.tasks.feed_tasks.translate_article",
            args=[article_id],
            kwargs=kwargs,
            task_id=owner,
            queue="translation",
        )
        return True, None
    except Exception as exc:
        if lock_acquired and redis_client is not None:
            _release_article_translation_slot(redis_client, article_id, owner)
        return False, str(exc)


def _mark_translation_dispatch_failed(db: Session, article_id: int, error: str) -> None:
    article = db.execute(select(Article).where(Article.id == article_id)).scalar_one_or_none()
    if not article:
        return
    article.translation_status = "failed"
    article.translation_error = f"Translation queue dispatch failed: {error}"[:1000]
    article.translation_completed_at = datetime.utcnow()
    db.commit()


def _dispatch_queued_article_translations(db: Session, article_ids: list[int]) -> int:
    dispatched = 0
    for article_id in article_ids:
        queued, error = dispatch_article_translation(article_id)
        if queued or error == "duplicate":
            dispatched += 1
        elif error:
            _mark_translation_dispatch_failed(db, article_id, error)
    return dispatched


def _generate_article_embedding_sync(db: Session, article: Article, user_id: int) -> None:
    """Generate embedding for a single article (sync version, non-blocking on failure)."""
    from app.models.user import User
    
    try:
        # Get user's embedding configuration
        user = db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        
        if not user or not user.embedding_provider_id or not user.embedding_model:
            # No embedding config, skip silently
            return
        
        provider = db.execute(
            select(AIProvider).where(AIProvider.id == user.embedding_provider_id)
        ).scalar_one_or_none()
        
        if not provider:
            return
        
        # Generate embedding
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.services.embedding_service import EmbeddingService
            
            service = EmbeddingService(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=user.embedding_model
            )
            
            # Combine title and content for embedding
            text = f"{article.title} {article.content or ''}"
            embedding = loop.run_until_complete(service.generate_embedding(text))
            
            if embedding:
                article.embedding = embedding
                db.flush()
                print(f"Generated embedding for article {article.id}: {article.title[:50]}...")
        finally:
            loop.close()
    except Exception as e:
        # Don't fail the article save if embedding generation fails
        print(f"Failed to generate embedding for article {article.id}: {e}")


def _trigger_push_notifications(db: Session, article: Article) -> None:
    """Trigger push notifications for a new article."""
    try:
        from app.services.push_notification_service import PushNotificationService

        service = PushNotificationService(db)
        pushes_sent = service.check_and_trigger_pushes(article)

        if pushes_sent > 0:
            print(f"Sent {pushes_sent} push notifications for article {article.id}: {article.title[:50]}")

    except Exception as e:
        # Don't fail the article save if push notification fails
        print(f"Failed to trigger push notifications for article {article.id}: {e}")


def _process_article_with_ai(db: Session, article: Article, feed: Feed) -> bool:
    """Queue article translation and summarize if enabled."""
    from app.models.user import User

    translation_queued = _mark_article_translation_queued(db, article, feed)

    if not feed.auto_summarize:
        return translation_queued

    if not (article.content or article.title):
        return translation_queued

    title = article.title or ""
    content = article.content or ""
    content_for_ai = content or title
    if not content_for_ai:
        return translation_queued

    # Get user info
    user = db.execute(
        select(User).where(User.id == feed.user_id)
    ).scalar_one_or_none()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Handle AI summarization (always uses AI model)
        default_model = db.execute(
            select(AIModel)
            .join(AIProvider, AIModel.provider_id == AIProvider.id)
            .where(
                AIProvider.user_id == feed.user_id,
                AIModel.is_default == True
            )
        ).scalar_one_or_none()

        if not default_model:
            print(f"No default AI model set for user {feed.user_id}, skipping AI summarization")
        else:
            provider = db.execute(
                select(AIProvider).where(AIProvider.id == default_model.provider_id)
            ).scalar_one_or_none()

            if provider:
                summarize_prompt = user.summarize_prompt if user and user.summarize_prompt else None

                try:
                    from app.services.ai_client import create_ai_client, AIClientError
                    client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
                    summary = loop.run_until_complete(client.summarize(content_for_ai, summarize_prompt))
                    article.summary = summary
                except AIClientError as e:
                    print(f"AI summarize error for article {article.id}: {e}")

        db.flush()
    except Exception as e:
        print(f"Article processing error: {e}")
    finally:
        loop.close()

    return translation_queued


def _translation_has_title(translation: str | None) -> bool:
    """Return whether a stored translation already contains a translated title."""
    if not translation:
        return False
    try:
        data = json.loads(translation)
    except (TypeError, json.JSONDecodeError):
        return False
    return bool(data.get("title"))


def _resolve_argos_languages(db: Session, feed: Feed, target_language: str) -> tuple[str, str]:
    from app.models.user import User
    from app.services.argos_translate_service import normalize_argos_language

    user = db.execute(
        select(User).where(User.id == feed.user_id)
    ).scalar_one_or_none()
    source_language = (
        getattr(feed, "source_language", None)
        or (user.argos_source_language if user else None)
        or "en"
    )
    return (
        normalize_argos_language(source_language, default="en"),
        normalize_argos_language(target_language, default="zh"),
    )


def _create_argos_translation_log(
    db: Session,
    article: Article,
    feed: Feed,
    target_language: str,
    started_at: datetime,
) -> ArgosTranslationLog:
    source_language, normalized_target = _resolve_argos_languages(db, feed, target_language)
    log = ArgosTranslationLog(
        user_id=feed.user_id,
        feed_id=feed.id,
        article_id=article.id,
        feed_title=feed.title,
        article_title=article.title,
        source_language=source_language,
        target_language=normalized_target,
        status="translating",
        title_chars=len(article.title or ""),
        content_chars=len(article.content or ""),
        started_at=started_at,
    )
    db.add(log)
    db.flush()
    return log


def _finish_argos_translation_log(
    log: ArgosTranslationLog | None,
    status: str,
    started_at: datetime,
    completed_at: datetime,
    error: str | None = None,
) -> None:
    if not log:
        return

    log.status = status
    log.completed_at = completed_at
    log.duration_ms = max(
        0,
        int((completed_at - started_at).total_seconds() * 1000),
    )
    log.error = error[:1000] if error else None


def _perform_article_translation_sync(
    db: Session,
    article: Article,
    feed: Feed,
    target_language: str | None = None,
    force_full: bool = False,
) -> tuple[str, str]:
    """Translate article title/content with the feed's configured translation provider.

    Args:
        db: Database session
        article: Article to translate
        feed: Feed configuration
        target_language: Target language code
        force_full: 如果为 True，强制翻译标题+正文，忽略 Feed 的 translate_title/translate_content 配置
    """
    from app.models.user import User
    from app.services.translation_scope import translation_targets_for_source

    translate_method = _translation_method_for_feed(feed)
    target = target_language or feed.target_language
    if translate_method == "none" or not target:
        raise ValueError("Feed does not have translation enabled")

    # Get translation scope from feed settings
    if force_full:
        # 手动触发时，强制翻译标题+正文
        translate_title, translate_content = True, True
    else:
        # 自动翻译时，遵循 Feed 配置
        translate_title, translate_content = translation_targets_for_source(feed)

    # Prepare input based on translation scope
    title = (article.title or "") if translate_title else ""
    content = (article.content or "") if translate_content else ""

    if not title and not content:
        raise ValueError("Article has no content to translate")

    user = db.execute(
        select(User).where(User.id == feed.user_id)
    ).scalar_one_or_none()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        if translate_method == "google":
            from app.services.google_translate_key_service import (
                translate_google_article_sync,
            )

            translated_title, translated_content = translate_google_article_sync(
                db,
                feed.user_id,
                title,
                content,
                target,
                loop,
            )

        elif translate_method == "argos":
            from app.services.argos_translate_service import ArgosTranslateService

            source_language = (
                getattr(feed, "source_language", None)
                or (user.argos_source_language if user else None)
                or "en"
            )
            translated_title, translated_content = ArgosTranslateService(
                source_language
            ).translate_article_sync(title, content, target)

        elif translate_method == "mc_translation":
            from app.services.mc_translation_service import McTranslationService

            source_language = getattr(feed, "source_language", None) or "en"
            translated_title, translated_content = loop.run_until_complete(
                McTranslationService(
                    api_key=user.mc_translation_api_key if user else None,
                    base_url=user.mc_translation_base_url if user else None,
                    model=user.mc_translation_model if user else None,
                    source_language=source_language,
                ).translate_article(title, content, target, source_language)
            )

        elif translate_method == "ai":
            default_model = db.execute(
                select(AIModel)
                .join(AIProvider, AIModel.provider_id == AIProvider.id)
                .where(
                    AIProvider.user_id == feed.user_id,
                    AIModel.is_default == True
                )
            ).scalar_one_or_none()

            if not default_model:
                raise ValueError("请先在 AI 设置中设置默认模型")

            provider = db.execute(
                select(AIProvider).where(AIProvider.id == default_model.provider_id)
            ).scalar_one_or_none()

            if not provider:
                raise ValueError("AI provider not found")

            translate_prompt = user.translate_prompt if user and user.translate_prompt else None

            from app.services.ai_client import create_ai_client
            client = create_ai_client(
                provider.type,
                provider.api_key,
                provider.base_url,
                default_model.model_id,
            )
            translated_title = (
                loop.run_until_complete(client.translate(title, target, translate_prompt))
                if title
                else ""
            )
            translated_content = (
                loop.run_until_complete(client.translate(content, target, translate_prompt))
                if content
                else ""
            )

        else:
            raise ValueError(f"Unsupported translate method: {translate_method}")
    finally:
        loop.close()

    translation_data = json.dumps(
        {"title": translated_title, "content": translated_content},
        ensure_ascii=False,
    )
    return translation_data, translate_method


@shared_task(name="app.tasks.feed_tasks.translate_article", bind=True)
def translate_article_task(self, article_id: int, target_language: str | None = None, force_full: bool = False) -> dict:
    """Translate one article in the background and persist translation status.

    Args:
        article_id: Article ID
        target_language: Target language code
        force_full: 如果为 True，强制翻译标题+正文，忽略 Feed 的 translate_title/translate_content 配置
    """
    owner = self.request.id or ""
    redis_client = None

    try:
        redis_client = get_redis_client()
    except Exception:
        redis_client = None

    with get_sync_session() as db:
        article = db.execute(select(Article).where(Article.id == article_id)).scalar_one_or_none()
        if not article:
            if redis_client is not None:
                _release_article_translation_slot(redis_client, article_id, owner)
            return {"success": False, "article_id": article_id, "error": "Article not found"}

        feed = db.execute(select(Feed).where(Feed.id == article.feed_id)).scalar_one_or_none()
        if not feed:
            article.translation_status = "failed"
            article.translation_error = "Feed not found"
            article.translation_completed_at = datetime.utcnow()
            db.commit()
            if redis_client is not None:
                _release_article_translation_slot(redis_client, article_id, owner)
            return {"success": False, "article_id": article_id, "error": "Feed not found"}

        translate_method = _translation_method_for_feed(feed)
        target = target_language or feed.target_language
        if translate_method == "none" or not target:
            article.translation_status = "none" if not article.translation else "completed"
            article.translation_error = None
            article.translation_started_at = None
            article.translation_completed_at = None
            db.commit()
            if redis_client is not None:
                _release_article_translation_slot(redis_client, article_id, owner)
            return {"success": False, "article_id": article_id, "error": "Translation disabled"}

        if not _has_translatable_article_text(article):
            article.translation_status = "failed"
            article.translation_error = "Article has no content to translate"
            article.translation_completed_at = datetime.utcnow()
            db.commit()
            if redis_client is not None:
                _release_article_translation_slot(redis_client, article_id, owner)
            return {"success": False, "article_id": article_id, "error": article.translation_error}

        argos_log: ArgosTranslationLog | None = None
        try:
            started_at = datetime.utcnow()
            article.translation_status = "translating"
            article.translation_error = None
            article.translation_started_at = started_at
            article.translation_completed_at = None
            db.commit()

            if translate_method == "argos":
                argos_log = _create_argos_translation_log(db, article, feed, target, started_at)
                db.commit()

            translation_data, method = _perform_article_translation_sync(
                db,
                article,
                feed,
                target_language=target,
                force_full=force_full,
            )
            completed_at = datetime.utcnow()
            article.translation = translation_data
            article.translation_status = "completed"
            article.translation_error = None
            article.translation_completed_at = completed_at
            _finish_argos_translation_log(argos_log, "completed", started_at, completed_at)
            db.commit()
            print(f"{method} translated article {article.id}: {article.title[:50]}...")
            return {
                "success": True,
                "article_id": article_id,
                "method": method,
                "status": "completed",
            }
        except Exception as exc:
            completed_at = datetime.utcnow()
            article.translation_status = "failed"
            article.translation_error = str(exc)[:1000]
            article.translation_completed_at = completed_at
            _finish_argos_translation_log(argos_log, "failed", started_at, completed_at, str(exc))
            db.commit()
            print(f"Translate error for article {article_id}: {exc}")
            return {
                "success": False,
                "article_id": article_id,
                "status": "failed",
                "error": str(exc),
            }
        finally:
            if redis_client is not None:
                _release_article_translation_slot(redis_client, article_id, owner)


def _record_proxy_success_sync(db: Session, proxy: ProxyPoolEntry) -> None:
    proxy.fail_count = 0
    proxy.is_active = True
    proxy.last_error = None
    proxy.last_used_at = datetime.utcnow()
    proxy.last_tested_at = datetime.utcnow()
    db.flush()


def _record_proxy_failure_sync(db: Session, proxy: ProxyPoolEntry, error: str) -> None:
    proxy.fail_count += 1
    if proxy.fail_count >= 5:
        proxy.is_active = False
    proxy.last_error = error[:1000]
    proxy.last_used_at = datetime.utcnow()
    proxy.last_tested_at = datetime.utcnow()
    db.flush()


def _get_proxy_candidates_sync(db: Session, feed: Feed) -> list[ProxyPoolEntry]:
    query = select(ProxyPoolEntry).where(
        ProxyPoolEntry.user_id == feed.user_id,
        ProxyPoolEntry.is_active == True,
    )
    country = getattr(feed, "proxy_pool_country", None)
    protocol = getattr(feed, "proxy_pool_protocol", None)
    if country:
        query = query.where(ProxyPoolEntry.country == country)
    if protocol:
        query = query.where(ProxyPoolEntry.protocol == protocol)
    query = query.order_by(
        ProxyPoolEntry.fail_count,
        ProxyPoolEntry.last_used_at.is_not(None),
        ProxyPoolEntry.last_used_at,
        ProxyPoolEntry.last_latency_ms.is_(None),
        ProxyPoolEntry.last_latency_ms,
        ProxyPoolEntry.id,
    )
    return list(db.execute(query).scalars().all())


def _parse_feed_for_sync_refresh(db: Session, feed: Feed) -> ParsedFeed:
    """Parse a feed for Celery refresh, rotating pool proxies when configured."""
    browser_settings = load_browser_fetch_settings_sync(db) if _feed_uses_browser(feed) else None
    proxy_mode = getattr(
        feed,
        "proxy_mode",
        "single" if getattr(feed, "proxy_enabled", False) else "none",
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        if proxy_mode == "pool":
            candidates = _get_proxy_candidates_sync(db, feed)
            if not candidates:
                raise FeedParserError("代理池没有可用代理")

            last_error = ""
            for proxy in candidates:
                try:
                    parsed = loop.run_until_complete(
                        parse_feed(
                            feed.url,
                            use_playwright=feed.use_playwright,
                            browser_engine=_feed_browser_engine_for_parse(feed),
                            proxy_url=proxy.proxy_url,
                            browser_settings=browser_settings,
                        )
                    )
                    _record_proxy_success_sync(db, proxy)
                    return parsed
                except Exception as exc:
                    last_error = str(exc)
                    _record_proxy_failure_sync(db, proxy, last_error)

            raise FeedParserError(f"代理池全部失败: {last_error or '未知错误'}")

        proxy_url = (
            getattr(feed, "proxy_url", None)
            if proxy_mode == "single" and getattr(feed, "proxy_enabled", False)
            else None
        )
        return loop.run_until_complete(
            parse_feed(
                feed.url,
                use_playwright=feed.use_playwright,
                browser_engine=_feed_browser_engine_for_parse(feed),
                proxy_url=proxy_url,
                browser_settings=browser_settings,
            )
        )
    finally:
        loop.close()


def _refresh_feed_sync(db: Session, feed: Feed) -> int:
    """Refresh a single feed and return number of new articles (sync version)."""
    try:
        parsed: Optional[ParsedFeed] = _parse_feed_for_sync_refresh(db, feed)
        
        if not parsed:
            feed.last_error = "Failed to parse feed"
            feed.error_count += 1
            db.commit()
            return 0

        is_initial_fetch = feed.last_fetched_at is None
        if is_initial_fetch:
            if parsed.title:
                feed.title = parsed.title
            if parsed.description:
                feed.description = parsed.description
            if parsed.site_url:
                feed.site_url = parsed.site_url
            if parsed.icon_url:
                feed.icon_url = parsed.icon_url
        
        new_count = 0
        queued_translation_article_ids: list[int] = []
        for article_data in parsed.articles:
            # Check if article already exists
            guid = article_data.guid
            if not guid:
                continue
            
            existing = db.execute(
                select(Article).where(
                    Article.feed_id == feed.id,
                    Article.guid == guid
                )
            ).scalar_one_or_none()
            
            if existing:
                continue
            
            # Create new article
            article = Article(
                feed_id=feed.id,
                guid=guid,
                title=article_data.title or "Untitled",
                link=article_data.link,
                content=article_data.content,
                summary=None,  # Only set by AI if auto_summarize is enabled
                author=article_data.author,
                published_at=article_data.published_at,
            )
            db.add(article)
            db.flush()  # Get article ID

            # Queue translation and process summary if enabled.
            if _process_article_with_ai(db, article, feed):
                queued_translation_article_ids.append(article.id)

            # Generate embedding for the new article (async, non-blocking)
            _generate_article_embedding_sync(db, article, feed.user_id)

            # Trigger push notifications for new article
            _trigger_push_notifications(db, article)

            new_count += 1
        
        feed.last_fetched_at = datetime.utcnow()
        feed.last_error = None
        feed.error_count = 0
        db.commit()

        if queued_translation_article_ids:
            _dispatch_queued_article_translations(db, queued_translation_article_ids)
        
        return new_count
    except Exception as e:
        feed.last_error = str(e)[:500]
        feed.error_count += 1
        db.commit()
        return 0


def _execute_custom_rule_sync(db: Session, rule: CustomRule) -> list[dict]:
    """Execute a custom rule and save articles (sync version for Celery)."""
    from urllib.parse import urljoin, urlparse
    from hashlib import md5
    import httpx
    from bs4 import BeautifulSoup
    
    # Ensure rule has associated feed
    feed_id = rule.feed_id
    if not feed_id:
        # Create feed for legacy rule without feed_id
        feed = Feed(
            user_id=rule.user_id,
            category_id=rule.category_id,
            url=rule.target_url,
            title=rule.name,
            description=f"自定义抓取规则: {rule.name}",
            fetch_interval=rule.fetch_interval,
            auto_translate=rule.auto_translate,
            auto_summarize=rule.auto_summarize,
            source_language=getattr(rule, 'source_language', None),
            target_language=rule.target_language,
            translate_method=getattr(rule, 'translate_method', 'none'),
            proxy_enabled=getattr(rule, "proxy_enabled", False),
            proxy_url=getattr(rule, "proxy_url", None),
            proxy_mode=getattr(
                rule,
                "proxy_mode",
                "single" if getattr(rule, "proxy_enabled", False) else "none",
            ),
            proxy_pool_country=getattr(rule, "proxy_pool_country", None),
            proxy_pool_protocol=getattr(rule, "proxy_pool_protocol", None),
            is_active=rule.is_active,
        )
        db.add(feed)
        db.flush()
        rule.feed_id = feed.id
        feed_id = feed.id
        db.commit()
    
    try:
        # Parse cookies if provided
        cookies_dict = {}
        if hasattr(rule, 'cookies') and rule.cookies:
            for item in rule.cookies.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookies_dict[key.strip()] = value.strip()
        
        proxy_mode = getattr(
            rule,
            "proxy_mode",
            "single" if getattr(rule, "proxy_enabled", False) else "none",
        )
        print(f"[CustomRule] use_playwright={rule.use_playwright} for rule {rule.id}")
        print(f"[CustomRule] proxy_mode={proxy_mode} for rule {rule.id}")
        browser_settings = load_browser_fetch_settings_sync(db) if rule.use_playwright else None

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def _fetch_with_playwright(proxy_url: str | None = None):
                from playwright.async_api import async_playwright
                from app.core.config import settings as app_settings

                if browser_settings is None:
                    raise RuntimeError("Browser settings unavailable")

                launch_kwargs = {
                    "headless": app_settings.FEED_BROWSER_HEADLESS,
                    "args": [
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ],
                }
                playwright_proxy = _build_playwright_proxy(proxy_url)
                if playwright_proxy:
                    launch_kwargs["proxy"] = playwright_proxy

                print(f"[CustomRule] Starting Playwright for {rule.target_url}")
                browser = None
                context = None
                try:
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(**launch_kwargs)
                        context = await browser.new_context(
                            user_agent=browser_settings.user_agent,
                            viewport={
                                "width": browser_settings.viewport_width,
                                "height": browser_settings.viewport_height,
                            },
                            locale="en-US",
                            extra_http_headers={
                                "Accept-Language": "en-US,en;q=0.9",
                                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            },
                        )
                        if cookies_dict:
                            host = urlparse(rule.target_url).hostname or ""
                            cookie_list = [
                                {"name": k, "value": v, "domain": host, "path": "/"}
                                for k, v in cookies_dict.items()
                            ]
                            await context.add_cookies(cookie_list)
                        await _apply_browser_resource_blocking(context, browser_settings)
                        page = await context.new_page()
                        await page.goto(
                            rule.target_url,
                            wait_until=browser_settings.playwright_wait_until,
                            timeout=browser_settings.playwright_timeout_seconds * 1000,
                        )
                        return await page.content()
                finally:
                    if context:
                        try:
                            await context.close()
                        except Exception:
                            pass
                    if browser:
                        try:
                            await browser.close()
                        except Exception:
                            pass

            async def _fetch_with_httpx(proxy_url: str | None = None):
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                async with httpx.AsyncClient(
                    timeout=30.0,
                    cookies=cookies_dict if cookies_dict else None,
                    proxy=proxy_url,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(rule.target_url, headers=headers)
                    response.raise_for_status()
                return response.text

            def _fetch_once(proxy_url: str | None = None) -> str:
                if rule.use_playwright:
                    return loop.run_until_complete(_fetch_with_playwright(proxy_url))
                return loop.run_until_complete(_fetch_with_httpx(proxy_url))

            if proxy_mode == "pool":
                candidates = _get_proxy_candidates_sync(db, rule)
                if not candidates:
                    raise RuntimeError("代理池没有可用代理")

                last_error = ""
                for proxy in candidates:
                    try:
                        html_content = _fetch_once(proxy.proxy_url)
                        _record_proxy_success_sync(db, proxy)
                        db.commit()
                        break
                    except Exception as exc:
                        last_error = str(exc)
                        _record_proxy_failure_sync(db, proxy, last_error)
                        db.commit()
                else:
                    raise RuntimeError(f"代理池全部失败: {last_error or '未知错误'}")
            else:
                proxy_url = (
                    getattr(rule, "proxy_url", None)
                    if proxy_mode == "single" and getattr(rule, "proxy_enabled", False)
                    else None
                )
                html_content = _fetch_once(proxy_url)

            print(f"[CustomRule] Loaded {len(html_content)} bytes")
        finally:
            loop.close()
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Use specialized parser for telegram/twitter
        rule_type = getattr(rule, 'rule_type', 'general') or 'general'
        print(f"[CustomRule] rule_type={rule_type}")
        
        if rule_type == 'telegram':
            items = soup.select('.tgme_widget_message_wrap')
        elif rule_type == 'twitter':
            items = soup.select('.timeline-item')
        else:
            items = soup.select(rule.list_selector)
        
        print(f"[CustomRule] Found {len(items)} items")
        
        new_articles = []
        skipped_no_title_link = 0
        skipped_existing = 0
        
        for idx, item in enumerate(items):
            title = None
            link = None
            content = None
            published_at = None
            
            if rule_type == 'telegram':
                text_elem = item.select_one('.tgme_widget_message_text')
                if text_elem:
                    content = str(text_elem)
                    title = text_elem.get_text(strip=True)[:100]
                    if len(text_elem.get_text(strip=True)) > 100:
                        title += '...'
                
                link_elem = item.select_one('.tgme_widget_message_date')
                if link_elem:
                    link = link_elem.get('href')
                
                time_elem = item.select_one('time[datetime]')
                if time_elem:
                    try:
                        from dateutil import parser as date_parser
                        published_at = date_parser.parse(time_elem.get('datetime'))
                    except:
                        pass
                
                if not title:
                    fwd = item.select_one('.tgme_widget_message_forwarded_from')
                    if fwd:
                        title = f"[转发] {fwd.get_text(strip=True)}"
                    else:
                        skipped_no_title_link += 1
                        continue
            
            elif rule_type == 'twitter':
                text_elem = item.select_one('.tweet-content')
                if text_elem:
                    content = str(text_elem)
                    title = text_elem.get_text(strip=True)[:100]
                    if len(text_elem.get_text(strip=True)) > 100:
                        title += '...'
                
                link_elem = item.select_one('.tweet-link')
                if link_elem:
                    link = link_elem.get('href')
                    if link and not link.startswith('http'):
                        link = urljoin(rule.target_url, link)
                
                time_elem = item.select_one('.tweet-date a')
                if time_elem:
                    try:
                        from dateutil import parser as date_parser
                        title_attr = time_elem.get('title')
                        if title_attr:
                            published_at = date_parser.parse(title_attr)
                    except:
                        pass
                
                if not title:
                    skipped_no_title_link += 1
                    continue
            
            else:
                # General rule parsing
                title_elem = item.select_one(rule.title_selector)
                
                if not rule.link_selector or rule.link_selector.lower() in ('self', '.', 'this'):
                    link_elem = item if item.name == 'a' else item.find('a')
                else:
                    link_elem = item.select_one(rule.link_selector)
                
                if link_elem:
                    link = link_elem.get("href")
                    if not link and link_elem.name != 'a':
                        inner_a = link_elem.find('a')
                        if inner_a:
                            link = inner_a.get('href')
                
                if not title_elem:
                    skipped_no_title_link += 1
                    continue
                
                title = title_elem.get_text(strip=True)
                
                if rule.content_selector:
                    content_elem = item.select_one(rule.content_selector)
                    content = content_elem.get_text(strip=True) if content_elem else None
            
            if not title:
                skipped_no_title_link += 1
                continue
            
            # Make link absolute
            if link and not link.startswith("http"):
                link = urljoin(rule.target_url, link)
            
            # Generate guid
            if link:
                guid = md5(link.encode()).hexdigest()
            else:
                guid = md5(title.encode()).hexdigest()
            
            if idx == 0:
                print(f"[CustomRule] First item: title={title[:50]}..., link={link}, guid={guid[:8]}")
            
            # Check if article exists
            existing = db.execute(
                select(Article).where(
                    Article.feed_id == feed_id,
                    Article.guid == guid
                )
            ).scalar_one_or_none()
            
            if existing:
                skipped_existing += 1
                continue
            
            # Create article
            article = Article(
                feed_id=feed_id,
                guid=guid,
                link=link,
                title=title,
                content=content,
                published_at=published_at or datetime.utcnow(),
            )
            db.add(article)
            new_articles.append({"title": title, "link": link, "content": content})

            # Trigger push notifications for new article
            db.flush()  # Ensure article has ID
            _trigger_push_notifications(db, article)

        print(f"[CustomRule] Skipped {skipped_no_title_link} (no title/link), {skipped_existing} (existing), added {len(new_articles)} new")
        
        # Update rule and feed status
        now = datetime.utcnow()
        rule.last_fetched_at = now
        rule.last_error = None
        rule.error_count = 0
        
        feed = db.execute(
            select(Feed).where(Feed.id == feed_id)
        ).scalar_one_or_none()
        if feed:
            feed.last_fetched_at = now
            feed.last_error = None
            feed.error_count = 0
        
        db.commit()
        return new_articles
        
    except Exception as e:
        rule.last_error = str(e)[:500]
        rule.error_count += 1
        if feed_id:
            feed = db.execute(
                select(Feed).where(Feed.id == feed_id)
            ).scalar_one_or_none()
            if feed:
                feed.last_error = str(e)[:500]
                feed.error_count += 1
        db.commit()
        raise


@shared_task(name="app.tasks.feed_tasks.refresh_feed")
def refresh_feed(feed_id: int) -> dict:
    """Refresh a single feed."""
    with get_sync_session() as db:
        feed = db.execute(select(Feed).where(Feed.id == feed_id)).scalar_one_or_none()
        if not feed:
            return {"success": False, "error": "Feed not found"}
        
        new_count = _refresh_feed_sync(db, feed)
        return {"success": True, "new_articles": new_count}


@shared_task(name="app.tasks.feed_tasks.refresh_all_feeds")
def refresh_all_feeds() -> dict:
    """Refresh all active feeds."""
    with get_sync_session() as db:
        feeds = db.execute(
            select(Feed).where(Feed.is_active == True)
        ).scalars().all()
        
        total_new = 0
        errors = 0
        for feed in feeds:
            try:
                new_count = _refresh_feed_sync(db, feed)
                total_new += new_count
            except Exception:
                errors += 1
        
        return {
            "success": True,
            "feeds_processed": len(feeds),
            "new_articles": total_new,
            "errors": errors
        }


@shared_task(name="app.tasks.feed_tasks.refresh_due_feeds", bind=True)
def refresh_due_feeds(self) -> dict:
    """Dispatch feed refresh tasks for feeds that are due."""
    # Use Redis lock to prevent concurrent dispatch
    redis_client = get_redis_client()
    lock = redis_client.lock("refresh_due_feeds_dispatch_lock", timeout=60)
    
    if not lock.acquire(blocking=False):
        return {"success": True, "message": "Another dispatch is running", "skipped": True}
    
    try:
        with get_sync_session() as db:
            browser_fetch_settings = load_browser_fetch_settings_sync(db)
            now = datetime.utcnow()
            
            # Get all active feeds
            feeds = db.execute(
                select(Feed).where(Feed.is_active == True)
            ).scalars().all()
            
            dispatched = 0
            dispatched_browser = 0
            dispatched_regular = 0
            skipped = 0
            skipped_queued = 0
            skipped_limited = 0
            due_feeds: list[tuple[datetime, int, Feed]] = []
            
            for feed in feeds:
                next_fetch = _next_fetch_at(feed.last_fetched_at, feed.fetch_interval)
                if now < next_fetch:
                    skipped += 1
                    continue
                due_feeds.append((next_fetch, feed.id, feed))

            due_feeds.sort(key=lambda item: (item[0], item[1]))

            for _next_fetch, _feed_id, feed in due_feeds:
                uses_browser = _feed_uses_browser(feed)
                if dispatched >= FEED_REFRESH_DISPATCH_LIMIT:
                    skipped_limited += 1
                    continue
                if (
                    uses_browser
                    and dispatched_browser >= browser_fetch_settings.feed_browser_refresh_dispatch_limit
                ):
                    skipped_limited += 1
                    continue

                owner = f"refresh_due_feeds:{self.request.id}:{feed.id}:{int(now.timestamp())}"
                if not _acquire_feed_refresh_slot(redis_client, feed.id, owner):
                    skipped_queued += 1
                    continue

                try:
                    # Dispatch individual feed refresh task after reserving its queue slot.
                    queue_name = "browser" if uses_browser else "feed"
                    refresh_single_feed.apply_async(args=[feed.id, owner], queue=queue_name)
                except Exception:
                    _release_feed_refresh_slot(redis_client, feed.id, owner)
                    raise
                dispatched += 1
                if uses_browser:
                    dispatched_browser += 1
                else:
                    dispatched_regular += 1
            
            if skipped_queued:
                print(
                    "[FeedRefreshDedup] "
                    f"Skipped {skipped_queued} feeds already queued/running "
                    f"during dispatch task {self.request.id}"
                )

            return {
                "success": True,
                "feeds_checked": len(feeds),
                "feeds_due": len(due_feeds),
                "feeds_dispatched": dispatched,
                "feeds_dispatched_regular": dispatched_regular,
                "feeds_dispatched_browser": dispatched_browser,
                "feeds_skipped": skipped,
                "feeds_skipped_queued": skipped_queued,
                "feeds_skipped_limited": skipped_limited,
            }
    finally:
        try:
            lock.release()
        except Exception:
            pass


@shared_task(name="app.tasks.feed_tasks.refresh_single_feed", bind=True)
def refresh_single_feed(self, feed_id: int, refresh_owner: str | None = None) -> dict:
    """Refresh a single feed - designed for parallel execution."""
    redis_client = get_redis_client()
    owner = refresh_owner or f"refresh_single_feed:{self.request.id}:{feed_id}"
    release_slot = True

    if not _refresh_feed_slot_for_worker(redis_client, feed_id, owner):
        print(f"[FeedRefreshDedup] Skipped feed {feed_id}: already queued or processing")
        return {
            "success": True,
            "feed_id": feed_id,
            "skipped": True,
            "reason": "already queued or processing",
        }
    
    try:
        with get_sync_session() as db:
            feed = db.execute(
                select(Feed).where(Feed.id == feed_id)
            ).scalar_one_or_none()
            
            if not feed:
                return {"success": False, "feed_id": feed_id, "error": "Feed not found"}
            
            if not feed.is_active:
                return {"success": True, "feed_id": feed_id, "skipped": True, "reason": "inactive"}

            if _feed_uses_browser(feed) and _current_task_queue(self) != "browser":
                refresh_single_feed.apply_async(args=[feed.id, owner], queue="browser")
                release_slot = False
                return {
                    "success": True,
                    "feed_id": feed_id,
                    "queued": True,
                    "queue": "browser",
                    "reason": "browser feed moved to browser queue",
                }
            
            try:
                new_count = _refresh_feed_sync(db, feed)
                print(f"Refreshed feed {feed.id} ({feed.title}): {new_count} new articles")
                return {
                    "success": True,
                    "feed_id": feed_id,
                    "new_articles": new_count
                }
            except Exception as e:
                db.rollback()
                print(f"Error refreshing feed {feed.id}: {e}")
                return {
                    "success": False,
                    "feed_id": feed_id,
                    "error": str(e)
                }
    finally:
        if release_slot:
            _release_feed_refresh_slot(redis_client, feed_id, owner)



@shared_task(name="app.tasks.feed_tasks.execute_custom_rule")
def execute_custom_rule(rule_id: int) -> dict:
    """Execute a single custom rule."""
    # Use sync session to avoid asyncpg concurrent operation issues
    with get_sync_session() as db:
        rule = db.execute(
            select(CustomRule).where(CustomRule.id == rule_id)
        ).scalar_one_or_none()
        
        if not rule:
            return {"success": False, "error": "Rule not found"}
        
        try:
            articles = _execute_custom_rule_sync(db, rule)
            return {"success": True, "articles_found": len(articles)}
        except Exception as e:
            return {"success": False, "error": str(e)}


@shared_task(name="app.tasks.feed_tasks.execute_all_custom_rules", bind=True)
def execute_all_custom_rules(self) -> dict:
    """Dispatch custom rule execution tasks for rules that are due."""
    # Use Redis lock to prevent concurrent dispatch
    redis_client = get_redis_client()
    lock = redis_client.lock("execute_all_custom_rules_dispatch_lock", timeout=60)
    
    if not lock.acquire(blocking=False):
        return {"success": True, "message": "Another dispatch is running", "skipped": True}
    
    try:
        with get_sync_session() as db:
            browser_fetch_settings = load_browser_fetch_settings_sync(db)
            now = datetime.utcnow()
            
            rules = db.execute(
                select(CustomRule).where(CustomRule.is_active == True)
            ).scalars().all()
            
            dispatched = 0
            dispatched_browser = 0
            dispatched_regular = 0
            skipped = 0
            skipped_queued = 0
            skipped_limited = 0
            due_rules: list[tuple[datetime, int, CustomRule]] = []
            
            for rule in rules:
                next_fetch = _next_fetch_at(rule.last_fetched_at, rule.fetch_interval)
                if now < next_fetch:
                    skipped += 1
                    continue
                due_rules.append((next_fetch, rule.id, rule))

            due_rules.sort(key=lambda item: (item[0], item[1]))

            for _next_fetch, _rule_id, rule in due_rules:
                uses_browser = _rule_uses_browser(rule)
                if dispatched >= CUSTOM_RULE_DISPATCH_LIMIT:
                    skipped_limited += 1
                    continue
                if (
                    uses_browser
                    and dispatched_browser >= browser_fetch_settings.custom_rule_browser_dispatch_limit
                ):
                    skipped_limited += 1
                    continue
                
                owner = f"execute_all_custom_rules:{self.request.id}:{rule.id}:{int(now.timestamp())}"
                if not _acquire_custom_rule_execution_slot(redis_client, rule.id, owner):
                    skipped_queued += 1
                    continue

                try:
                    queue_name = "browser" if uses_browser else "feed"
                    execute_single_custom_rule.apply_async(args=[rule.id, owner], queue=queue_name)
                except Exception:
                    _release_custom_rule_execution_slot(redis_client, rule.id, owner)
                    raise
                dispatched += 1
                if uses_browser:
                    dispatched_browser += 1
                else:
                    dispatched_regular += 1

            if skipped_queued:
                print(
                    "[CustomRuleDedup] "
                    f"Skipped {skipped_queued} rules already queued/running "
                    f"during dispatch task {self.request.id}"
                )
            
            return {
                "success": True,
                "rules_checked": len(rules),
                "rules_due": len(due_rules),
                "rules_dispatched": dispatched,
                "rules_dispatched_regular": dispatched_regular,
                "rules_dispatched_browser": dispatched_browser,
                "rules_skipped": skipped,
                "rules_skipped_queued": skipped_queued,
                "rules_skipped_limited": skipped_limited,
            }
    finally:
        try:
            lock.release()
        except Exception:
            pass


@shared_task(name="app.tasks.feed_tasks.execute_single_custom_rule", bind=True)
def execute_single_custom_rule(self, rule_id: int, execution_owner: str | None = None) -> dict:
    """Execute a single custom rule - designed for parallel execution."""
    redis_client = get_redis_client()
    owner = execution_owner or f"execute_single_custom_rule:{self.request.id}:{rule_id}"
    release_slot = True

    if not _refresh_custom_rule_slot_for_worker(redis_client, rule_id, owner):
        print(f"[CustomRuleDedup] Skipped rule {rule_id}: already queued or processing")
        return {
            "success": True,
            "rule_id": rule_id,
            "skipped": True,
            "reason": "already queued or processing",
        }
    
    try:
        # Use sync session to avoid asyncpg concurrent operation issues
        with get_sync_session() as db:
            rule = db.execute(
                select(CustomRule).where(CustomRule.id == rule_id)
            ).scalar_one_or_none()
            
            if not rule:
                return {"success": False, "rule_id": rule_id, "error": "Rule not found"}
            
            if not rule.is_active:
                return {"success": True, "rule_id": rule_id, "skipped": True, "reason": "inactive"}

            if _rule_uses_browser(rule) and _current_task_queue(self) != "browser":
                execute_single_custom_rule.apply_async(args=[rule.id, owner], queue="browser")
                release_slot = False
                return {
                    "success": True,
                    "rule_id": rule_id,
                    "queued": True,
                    "queue": "browser",
                    "reason": "browser rule moved to browser queue",
                }
            
            try:
                articles = _execute_custom_rule_sync(db, rule)
                print(f"Executed custom rule {rule.id} ({rule.name}): {len(articles)} articles")
                return {
                    "success": True,
                    "rule_id": rule_id,
                    "articles_found": len(articles)
                }
            except Exception as e:
                db.rollback()
                print(f"Error executing custom rule {rule.id}: {e}")
                import traceback
                traceback.print_exc()
                return {
                    "success": False,
                    "rule_id": rule_id,
                    "error": str(e)
                }
    finally:
        if release_slot:
            _release_custom_rule_execution_slot(redis_client, rule_id, owner)


@shared_task(name="app.tasks.feed_tasks.translate_feed_articles")
def translate_feed_articles(feed_id: int) -> dict:
    """Queue all untranslated articles in a feed for background translation."""
    with get_sync_session() as db:
        feed = db.execute(select(Feed).where(Feed.id == feed_id)).scalar_one_or_none()
        if not feed:
            return {"success": False, "error": "Feed not found"}
        
        # Get translate_method, default to checking auto_translate for backward compatibility
        translate_method = _translation_method_for_feed(feed)
        
        if translate_method == 'none' or not feed.target_language:
            return {"success": False, "error": "Feed does not have translation enabled"}

        # Queue articles without translation, failed articles, or legacy translations without a title.
        candidate_articles = db.execute(
            select(Article).where(
                Article.feed_id == feed_id
            )
        ).scalars().all()

        queued_article_ids: list[int] = []
        skipped = 0
        failed = 0

        for article in candidate_articles:
            if article.translation_status in {"queued", "translating"}:
                skipped += 1
                continue

            if _translation_has_title(article.translation):
                article.translation_status = "completed"
                article.translation_error = None
                skipped += 1
                continue

            if _mark_article_translation_queued(db, article, feed):
                queued_article_ids.append(article.id)
            elif article.translation_status == "failed":
                failed += 1
            else:
                skipped += 1

        if not queued_article_ids:
            db.commit()
            return {
                "success": True,
                "queued": 0,
                "dispatched": 0,
                "skipped": skipped,
                "failed": failed,
                "message": "No articles to translate",
            }

        db.commit()
        dispatched = _dispatch_queued_article_translations(db, queued_article_ids)

        return {
            "success": True,
            "queued": len(queued_article_ids),
            "dispatched": dispatched,
            "skipped": skipped,
            "failed": failed,
            "total": len(candidate_articles),
            "method": translate_method
        }


@shared_task(name="app.tasks.feed_tasks.cleanup_old_articles")
def cleanup_old_articles(days: int = 90) -> dict:
    """Clean up articles older than specified days (excluding favorites)."""
    from app.models.article import UserArticle
    
    with get_sync_session() as db:
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get IDs of favorited articles
        favorited = db.execute(
            select(UserArticle.article_id).where(UserArticle.is_favorite == True)
        )
        favorited_ids = {row[0] for row in favorited.fetchall()}
        
        # Delete old articles that are not favorited
        if favorited_ids:
            old_articles = db.execute(
                select(Article).where(
                    Article.created_at < cutoff,
                    ~Article.id.in_(favorited_ids)
                )
            ).scalars().all()
        else:
            old_articles = db.execute(
                select(Article).where(Article.created_at < cutoff)
            ).scalars().all()
        
        count = len(old_articles)
        for article in old_articles:
            db.delete(article)
        
        db.commit()
        return {"success": True, "deleted": count}


@shared_task(name="app.tasks.feed_tasks.generate_article_embedding")
def generate_article_embedding(article_id: int) -> dict:
    """Generate embedding for a single article."""
    from app.models.user import User
    
    with get_sync_session() as db:
        article = db.execute(
            select(Article).where(Article.id == article_id)
        ).scalar_one_or_none()
        
        if not article:
            return {"success": False, "error": "Article not found"}
        
        if article.embedding is not None:
            return {"success": True, "message": "Embedding already exists"}
        
        # Get the feed to find the user
        feed = db.execute(
            select(Feed).where(Feed.id == article.feed_id)
        ).scalar_one_or_none()
        
        if not feed:
            return {"success": False, "error": "Feed not found"}
        
        # Get user's embedding configuration
        user = db.execute(
            select(User).where(User.id == feed.user_id)
        ).scalar_one_or_none()
        
        if not user or not user.embedding_provider_id or not user.embedding_model:
            return {"success": False, "error": "No embedding model configured"}
        
        provider = db.execute(
            select(AIProvider).where(AIProvider.id == user.embedding_provider_id)
        ).scalar_one_or_none()
        
        if not provider:
            return {"success": False, "error": "Embedding provider not found"}
        
        # Generate embedding
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.services.embedding_service import EmbeddingService
            
            service = EmbeddingService(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=user.embedding_model
            )
            
            # Combine title and content for embedding
            text = f"{article.title} {article.content or ''}"
            embedding = loop.run_until_complete(service.generate_embedding(text))
            
            if embedding:
                article.embedding = embedding
                db.commit()
                return {"success": True, "article_id": article_id}
            else:
                return {"success": False, "error": "Failed to generate embedding"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            loop.close()


@shared_task(name="app.tasks.feed_tasks.generate_embeddings_batch", bind=True)
def generate_embeddings_batch(self, user_id: int, limit: int = 500) -> dict:
    """Generate embeddings for articles without embeddings for a user.
    
    Uses batch API calls for efficiency - processes up to 50 articles per API call.
    Supports task cancellation via Celery revoke.
    """
    from app.models.user import User
    import time
    
    with get_sync_session() as db:
        # Get articles without embeddings
        articles = db.execute(
            select(Article)
            .join(Feed, Article.feed_id == Feed.id)
            .where(
                Feed.user_id == user_id,
                Article.embedding == None
            )
            .order_by(Article.created_at.desc())
            .limit(limit)
        ).scalars().all()
        
        if not articles:
            return {"success": True, "processed": 0, "message": "No articles need embeddings"}
        
        # Get user's embedding configuration
        user = db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        
        if not user or not user.embedding_provider_id or not user.embedding_model:
            return {"success": False, "error": "No embedding model configured"}
        
        provider = db.execute(
            select(AIProvider).where(AIProvider.id == user.embedding_provider_id)
        ).scalar_one_or_none()
        
        if not provider:
            return {"success": False, "error": "Embedding provider not found"}
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        processed = 0
        errors = 0
        batch_size = 50  # Process 50 articles per API call for better throughput
        total_batches = (len(articles) + batch_size - 1) // batch_size
        
        try:
            from app.services.embedding_service import EmbeddingService
            
            service = EmbeddingService(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=user.embedding_model
            )
            
            # Process in batches
            for batch_num, i in enumerate(range(0, len(articles), batch_size)):
                # Check if task was revoked/cancelled
                if self.request.id:
                    from app.tasks.celery_app import celery_app
                    # Check revoked tasks
                    revoked = celery_app.control.inspect().revoked() or {}
                    for worker_revoked in revoked.values():
                        if self.request.id in worker_revoked:
                            print(f"Task {self.request.id} was cancelled, stopping...")
                            return {
                                "success": False,
                                "cancelled": True,
                                "processed": processed,
                                "errors": errors,
                                "message": "任务已被取消"
                            }
                
                batch_articles = articles[i:i + batch_size]
                texts = [f"{a.title} {a.content or ''}" for a in batch_articles]
                
                # Generate embeddings in batch
                try:
                    embeddings = loop.run_until_complete(
                        service.batch_generate_embeddings(texts)
                    )
                    
                    # Update articles with embeddings one by one to handle errors
                    batch_processed = 0
                    for article, embedding in zip(batch_articles, embeddings):
                        if embedding:
                            try:
                                article.embedding = embedding
                                db.flush()  # Try to flush this single update
                                batch_processed += 1
                            except Exception as update_error:
                                db.rollback()  # Rollback on error
                                print(f"Error updating article {article.id}: {update_error}")
                                errors += 1
                        else:
                            errors += 1
                    
                    # Commit successful updates
                    db.commit()
                    processed += batch_processed
                    
                    # Update task state for progress tracking
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current_batch': batch_num + 1,
                            'total_batches': total_batches,
                            'processed': processed,
                            'errors': errors,
                            'total': len(articles)
                        }
                    )
                    
                    print(f"Batch {batch_num + 1}/{total_batches} completed: processed {processed}, errors {errors}")
                    
                    # Small delay between batches to avoid rate limiting
                    if batch_num < total_batches - 1:
                        time.sleep(0.5)
                        
                except Exception as batch_error:
                    db.rollback()  # Rollback on batch error
                    print(f"Error in batch {batch_num + 1}: {batch_error}")
                    errors += len(batch_articles)
                    # Continue with next batch instead of failing completely
                    continue
            
            return {
                "success": True,
                "processed": processed,
                "errors": errors,
                "total": len(articles)
            }
        except Exception as e:
            print(f"Error in batch embedding generation: {e}")
            return {"success": False, "error": str(e), "processed": processed, "errors": errors}
        finally:
            loop.close()
