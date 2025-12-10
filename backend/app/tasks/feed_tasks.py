"""Feed-related background tasks."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.article import Article
from app.models.feed import Feed
from app.models.custom_rule import CustomRule
from app.models.ai_provider import AIModel, AIProvider
from app.utils.feed_parser import parse_feed, ParsedFeed


# Create sync engine for Celery tasks
# Convert async URL to sync URL
def get_sync_database_url() -> str:
    url = settings.DATABASE_URL
    if "postgresql+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    elif "sqlite+aiosqlite" in url:
        return url.replace("sqlite+aiosqlite", "sqlite")
    return url


sync_engine = create_engine(get_sync_database_url())
SyncSessionLocal = sessionmaker(bind=sync_engine)


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
    with SyncSessionLocal() as db:
        feed = db.execute(select(Feed).where(Feed.id == feed_id)).scalar_one_or_none()
        if not feed:
            return {"success": False, "error": "Feed not found"}
        
        new_count = _refresh_feed_sync(db, feed)
        return {"success": True, "new_articles": new_count}


@shared_task(name="app.tasks.feed_tasks.refresh_all_feeds")
def refresh_all_feeds() -> dict:
    """Refresh all active feeds."""
    with SyncSessionLocal() as db:
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


@shared_task(name="app.tasks.feed_tasks.refresh_due_feeds")
def refresh_due_feeds() -> dict:
    """Refresh feeds that are due based on their fetch_interval."""
    with SyncSessionLocal() as db:
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
                # Remove timezone info for comparison (PostgreSQL returns tz-aware)
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
                errors += 1
                print(f"Error refreshing feed {feed.id}: {e}")
        
        return {
            "success": True,
            "feeds_checked": len(feeds),
            "feeds_refreshed": processed,
            "new_articles": total_new,
            "errors": errors
        }



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


@shared_task(name="app.tasks.feed_tasks.execute_all_custom_rules")
def execute_all_custom_rules() -> dict:
    """Execute all active custom rules that are due."""
    with SyncSessionLocal() as db:
        now = datetime.utcnow()
        rules = db.execute(
            select(CustomRule).where(CustomRule.is_active == True)
        ).scalars().all()
        
        processed = 0
        total_articles = 0
        errors = 0
        skipped = 0
        
        for rule in rules:
            # Check if rule is due for fetch
            if rule.last_fetched_at:
                # Remove timezone info for comparison (PostgreSQL returns tz-aware)
                last_fetched = rule.last_fetched_at.replace(tzinfo=None) if rule.last_fetched_at.tzinfo else rule.last_fetched_at
                next_fetch = last_fetched + timedelta(seconds=rule.fetch_interval)
                # Ensure next_fetch is also naive
                if hasattr(next_fetch, 'tzinfo') and next_fetch.tzinfo:
                    next_fetch = next_fetch.replace(tzinfo=None)
                if now < next_fetch:
                    skipped += 1
                    continue  # Not due yet
            
            try:
                result = execute_custom_rule(rule.id)
                if result.get("success"):
                    total_articles += result.get("articles_found", 0)
                    processed += 1
                    print(f"Executed custom rule {rule.id} ({rule.name}): {result.get('articles_found', 0)} articles")
                else:
                    errors += 1
                    print(f"Error executing custom rule {rule.id}: {result.get('error')}")
            except Exception as e:
                errors += 1
                print(f"Exception executing custom rule {rule.id}: {e}")
        
        return {
            "success": True,
            "rules_checked": len(rules),
            "rules_processed": processed,
            "rules_skipped": skipped,
            "articles_found": total_articles,
            "errors": errors
        }


@shared_task(name="app.tasks.feed_tasks.translate_feed_articles")
def translate_feed_articles(feed_id: int) -> dict:
    """Translate all untranslated articles in a feed."""
    from app.models.user import User
    
    with SyncSessionLocal() as db:
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
    
    with SyncSessionLocal() as db:
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
    
    with SyncSessionLocal() as db:
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


@shared_task(name="app.tasks.feed_tasks.generate_embeddings_batch")
def generate_embeddings_batch(user_id: int, limit: int = 50) -> dict:
    """Generate embeddings for articles without embeddings for a user."""
    from app.models.user import User
    
    with SyncSessionLocal() as db:
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
        
        try:
            from app.services.embedding_service import EmbeddingService
            
            service = EmbeddingService(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=user.embedding_model
            )
            
            # Prepare texts for batch processing
            texts = [f"{a.title} {a.content or ''}" for a in articles]
            
            # Generate embeddings in batch
            embeddings = loop.run_until_complete(
                service.batch_generate_embeddings(texts)
            )
            
            # Update articles with embeddings
            for article, embedding in zip(articles, embeddings):
                if embedding:
                    article.embedding = embedding
                    processed += 1
                else:
                    errors += 1
            
            db.commit()
            
            return {
                "success": True,
                "processed": processed,
                "errors": errors,
                "total": len(articles)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            loop.close()
