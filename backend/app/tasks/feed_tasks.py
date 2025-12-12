"""Feed-related background tasks."""
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.article import Article
from app.models.feed import Feed
from app.models.custom_rule import CustomRule
from app.models.ai_provider import AIModel, AIProvider
from app.utils.feed_parser import parse_feed, ParsedFeed


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


def get_sync_session():
    """Get a sync database session, initializing engine if needed."""
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        _sync_engine = create_engine(get_sync_database_url())
        _SyncSessionLocal = sessionmaker(bind=_sync_engine)
    return _SyncSessionLocal()


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


def _process_article_with_ai(db: Session, article: Article, feed: Feed) -> None:
    """Process article with AI (translate/summarize) if enabled."""
    from app.models.user import User
    
    if not feed.auto_translate and not feed.auto_summarize:
        return
    
    # Get default model for the feed's user
    default_model = db.execute(
        select(AIModel).where(AIModel.is_default == True)
    ).scalar_one_or_none()
    
    if not default_model:
        return
    
    provider = db.execute(
        select(AIProvider).where(AIProvider.id == default_model.provider_id)
    ).scalar_one_or_none()
    
    if not provider:
        return
    
    # Get user's custom prompts
    user = db.execute(
        select(User).where(User.id == feed.user_id)
    ).scalar_one_or_none()
    
    translate_prompt = user.translate_prompt if user and user.translate_prompt else None
    summarize_prompt = user.summarize_prompt if user and user.summarize_prompt else None
    
    content = article.content or article.title
    if not content:
        return
    
    # Run AI operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from app.services.ai_client import create_ai_client, AIClientError
        client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
        
        if feed.auto_translate and feed.target_language:
            try:
                translation = loop.run_until_complete(client.translate(content, feed.target_language, translate_prompt))
                article.translation = translation
            except AIClientError as e:
                print(f"AI translate error for article {article.id}: {e}")
        
        if feed.auto_summarize:
            try:
                summary = loop.run_until_complete(client.summarize(content, summarize_prompt))
                article.summary = summary
            except AIClientError as e:
                print(f"AI summarize error for article {article.id}: {e}")
        
        db.commit()
    except Exception as e:
        print(f"AI processing error: {e}")
    finally:
        loop.close()


def _refresh_feed_sync(db: Session, feed: Feed) -> int:
    """Refresh a single feed and return number of new articles (sync version)."""
    try:
        # Run async parse_feed in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            parsed: Optional[ParsedFeed] = loop.run_until_complete(
                parse_feed(feed.url, use_playwright=feed.use_playwright)
            )
        finally:
            loop.close()
        
        if not parsed:
            feed.last_error = "Failed to parse feed"
            feed.error_count += 1
            db.commit()
            return 0
        
        new_count = 0
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
            
            # Process with AI if enabled
            _process_article_with_ai(db, article, feed)
            
            # Generate embedding for the new article (async, non-blocking)
            _generate_article_embedding_sync(db, article, feed.user_id)
            
            new_count += 1
        
        feed.last_fetched_at = datetime.utcnow()
        feed.last_error = None
        feed.error_count = 0
        db.commit()
        
        return new_count
    except Exception as e:
        feed.last_error = str(e)[:500]
        feed.error_count += 1
        db.commit()
        return 0


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
    """Refresh feeds that are due based on their fetch_interval."""
    import redis
    import os
    
    # Use Redis lock to prevent concurrent execution
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url)
    lock = redis_client.lock("refresh_due_feeds_lock", timeout=300)  # 5 min timeout
    
    if not lock.acquire(blocking=False):
        return {"success": True, "message": "Another refresh task is running", "skipped": True}
    
    try:
        with get_sync_session() as db:
            now = datetime.utcnow()
            
            # Get all active feeds
            feeds = db.execute(
                select(Feed).where(Feed.is_active == True)
            ).scalars().all()
            
            total_new = 0
            processed = 0
            errors = 0
            
            for feed in feeds:
                # Check if feed is due for refresh
                if feed.last_fetched_at:
                    last_fetched = feed.last_fetched_at.replace(tzinfo=None) if feed.last_fetched_at.tzinfo else feed.last_fetched_at
                    next_fetch = last_fetched + timedelta(seconds=feed.fetch_interval)
                    if now < next_fetch:
                        continue  # Not due yet
                
                try:
                    new_count = _refresh_feed_sync(db, feed)
                    total_new += new_count
                    processed += 1
                    print(f"Refreshed feed {feed.id} ({feed.title}): {new_count} new articles")
                except Exception as e:
                    db.rollback()
                    errors += 1
                    print(f"Error refreshing feed {feed.id}: {e}")
            
            return {
                "success": True,
                "feeds_checked": len(feeds),
                "feeds_refreshed": processed,
                "new_articles": total_new,
                "errors": errors
            }
    finally:
        try:
            lock.release()
        except Exception:
            pass



@shared_task(name="app.tasks.feed_tasks.execute_custom_rule")
def execute_custom_rule(rule_id: int) -> dict:
    """Execute a single custom rule."""
    # Custom rules need async, run in event loop
    async def _run():
        from app.core.database import async_session_maker
        from app.services.custom_rule_service import CustomRuleService
        
        async with async_session_maker() as db:
            result = await db.execute(
                select(CustomRule).where(CustomRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()
            if not rule:
                return {"success": False, "error": "Rule not found"}
            
            service = CustomRuleService(db)
            try:
                articles = await service.execute_rule(rule)
                return {"success": True, "articles_found": len(articles)}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@shared_task(name="app.tasks.feed_tasks.execute_all_custom_rules", bind=True)
def execute_all_custom_rules(self) -> dict:
    """Execute all active custom rules that are due."""
    import redis
    import os
    
    # Use Redis lock to prevent concurrent execution
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url)
    lock = redis_client.lock("execute_all_custom_rules_lock", timeout=300)
    
    if not lock.acquire(blocking=False):
        return {"success": True, "message": "Another custom rules task is running", "skipped": True}
    
    try:
        async def _run_all():
            from app.core.database import async_session_maker
            from app.services.custom_rule_service import CustomRuleService
            
            now = datetime.utcnow()
            
            # First, get all rules with a separate session
            async with async_session_maker() as db:
                result = await db.execute(
                    select(CustomRule).where(CustomRule.is_active == True)
                )
                rules = result.scalars().all()
                # Extract rule data we need before closing session
                rule_data = [
                    {
                        "id": r.id,
                        "name": r.name,
                        "last_fetched_at": r.last_fetched_at,
                        "fetch_interval": r.fetch_interval
                    }
                    for r in rules
                ]
            
            processed = 0
            total_articles = 0
            errors = 0
            skipped = 0
            
            for rd in rule_data:
                # Check if rule is due for fetch
                if rd["last_fetched_at"]:
                    last_fetched = rd["last_fetched_at"].replace(tzinfo=None) if rd["last_fetched_at"].tzinfo else rd["last_fetched_at"]
                    next_fetch = last_fetched + timedelta(seconds=rd["fetch_interval"])
                    if now < next_fetch:
                        skipped += 1
                        continue
                
                # Use separate session for each rule execution
                try:
                    async with async_session_maker() as db:
                        result = await db.execute(
                            select(CustomRule).where(CustomRule.id == rd["id"])
                        )
                        rule = result.scalar_one_or_none()
                        if not rule:
                            continue
                        
                        service = CustomRuleService(db)
                        articles = await service.execute_rule(rule)
                        total_articles += len(articles)
                        processed += 1
                        print(f"Executed custom rule {rd['id']} ({rd['name']}): {len(articles)} articles")
                except Exception as e:
                    errors += 1
                    print(f"Exception executing custom rule {rd['id']}: {e}")
            
            return {
                "success": True,
                "rules_checked": len(rule_data),
                "rules_processed": processed,
                "rules_skipped": skipped,
                "articles_found": total_articles,
                "errors": errors
            }
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_all())
        finally:
            loop.close()
    finally:
        try:
            lock.release()
        except Exception:
            pass


@shared_task(name="app.tasks.feed_tasks.translate_feed_articles")
def translate_feed_articles(feed_id: int) -> dict:
    """Translate all untranslated articles in a feed."""
    from app.models.user import User
    
    with get_sync_session() as db:
        feed = db.execute(select(Feed).where(Feed.id == feed_id)).scalar_one_or_none()
        if not feed:
            return {"success": False, "error": "Feed not found"}
        
        if not feed.auto_translate or not feed.target_language:
            return {"success": False, "error": "Feed does not have translation enabled"}
        
        # Get default model
        default_model = db.execute(
            select(AIModel).where(AIModel.is_default == True)
        ).scalar_one_or_none()
        
        if not default_model:
            return {"success": False, "error": "No default AI model configured"}
        
        provider = db.execute(
            select(AIProvider).where(AIProvider.id == default_model.provider_id)
        ).scalar_one_or_none()
        
        if not provider:
            return {"success": False, "error": "AI provider not found"}
        
        # Get user's custom translate prompt
        user = db.execute(
            select(User).where(User.id == feed.user_id)
        ).scalar_one_or_none()
        translate_prompt = user.translate_prompt if user and user.translate_prompt else None
        
        # Get untranslated articles
        articles = db.execute(
            select(Article).where(
                Article.feed_id == feed_id,
                Article.translation == None
            )
        ).scalars().all()
        
        if not articles:
            return {"success": True, "translated": 0, "message": "No articles to translate"}
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        translated_count = 0
        errors = 0
        
        try:
            from app.services.ai_client import create_ai_client, AIClientError
            client = create_ai_client(provider.type, provider.api_key, provider.base_url, default_model.model_id)
            
            for article in articles:
                content = article.content or article.title
                if not content:
                    continue
                
                try:
                    translation = loop.run_until_complete(client.translate(content, feed.target_language, translate_prompt))
                    article.translation = translation
                    db.commit()
                    translated_count += 1
                    print(f"Translated article {article.id}: {article.title[:50]}...")
                except AIClientError as e:
                    print(f"AI translate error for article {article.id}: {e}")
                    errors += 1
                except Exception as e:
                    print(f"Error translating article {article.id}: {e}")
                    errors += 1
        finally:
            loop.close()
        
        return {
            "success": True,
            "translated": translated_count,
            "errors": errors,
            "total": len(articles)
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
