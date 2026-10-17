"""Article embedding background tasks."""

import asyncio

from celery import shared_task
from sqlalchemy import select

from app.models.ai_provider import AIProvider
from app.models.article import Article
from app.models.feed import Feed
from app.models.user import User


def get_sync_session():
    from app.tasks.feed_tasks import get_sync_session as session

    return session()


def get_redis_client():
    from app.tasks.feed_tasks import get_redis_client as client

    return client()


@shared_task(name="app.tasks.feed_tasks.generate_article_embedding")
def generate_article_embedding(article_id: int, auto: bool = False) -> dict:
    """Generate embedding for a single article."""
    with get_sync_session() as db:
        article = db.execute(select(Article).where(Article.id == article_id)).scalar_one_or_none()

        if not article:
            return {"success": False, "error": "Article not found"}

        if article.embedding is not None:
            return {"success": True, "message": "Embedding already exists"}

        # Get the feed to find the user
        feed = db.execute(select(Feed).where(Feed.id == article.feed_id)).scalar_one_or_none()

        if not feed:
            return {"success": False, "error": "Feed not found"}

        # Get user's embedding configuration
        user = db.execute(select(User).where(User.id == feed.user_id)).scalar_one_or_none()

        if not user or not user.embedding_provider_id or not user.embedding_model:
            return {"success": False, "error": "No embedding model configured"}

        if auto and not user.auto_generate_embeddings:
            return {
                "success": True,
                "article_id": article_id,
                "skipped": "auto embedding disabled",
            }

        provider = db.execute(
            select(AIProvider).where(
                AIProvider.id == user.embedding_provider_id,
                AIProvider.user_id == user.id,
                AIProvider.is_active.is_(True),
            )
        ).scalar_one_or_none()

        if not provider:
            return {"success": False, "error": "Embedding provider not found"}

        # Generate embedding
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            from app.services.embedding_service import EmbeddingService

            service = EmbeddingService(
                api_key=provider.api_key, base_url=provider.base_url, model=user.embedding_model
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
    import time

    from app.models.user import User

    with get_sync_session() as db:
        # Get articles without embeddings
        article_ids = (
            db.execute(
                select(Article.id)
                .join(Feed, Article.feed_id == Feed.id)
                .where(Feed.user_id == user_id, Article.embedding.is_(None))
                .order_by(Article.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

        if not article_ids:
            return {"success": True, "processed": 0, "message": "No articles need embeddings"}

        # Get user's embedding configuration
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

        if not user or not user.embedding_provider_id or not user.embedding_model:
            return {"success": False, "error": "No embedding model configured"}

        provider = db.execute(
            select(AIProvider).where(
                AIProvider.id == user.embedding_provider_id,
                AIProvider.user_id == user.id,
                AIProvider.is_active.is_(True),
            )
        ).scalar_one_or_none()

        if not provider:
            return {"success": False, "error": "Embedding provider not found"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        processed = 0
        errors = 0
        batch_size = 50  # Process 50 articles per API call for better throughput
        total_batches = (len(article_ids) + batch_size - 1) // batch_size

        try:
            from app.services.embedding_service import EmbeddingService

            service = EmbeddingService(
                api_key=provider.api_key, base_url=provider.base_url, model=user.embedding_model
            )

            # Process in batches
            for batch_num, i in enumerate(range(0, len(article_ids), batch_size)):
                if self.request.id and get_redis_client().exists(
                    f"rss:embedding-cancel:{self.request.id}"
                ):
                    return {
                        "success": False,
                        "cancelled": True,
                        "processed": processed,
                        "errors": errors,
                        "message": "任务已被取消",
                    }

                batch_articles = (
                    db.execute(
                        select(Article).where(Article.id.in_(article_ids[i : i + batch_size]))
                    )
                    .scalars()
                    .all()
                )
                texts = [f"{a.title} {a.content or ''}" for a in batch_articles]

                # Generate embeddings in batch
                try:
                    embeddings = loop.run_until_complete(service.batch_generate_embeddings(texts))

                    # Update articles with embeddings one by one to handle errors
                    batch_processed = 0
                    for article, embedding in zip(batch_articles, embeddings):
                        if embedding:
                            try:
                                with db.begin_nested():
                                    article.embedding = embedding
                                    db.flush()
                                batch_processed += 1
                            except Exception as update_error:
                                print(f"Error updating article {article.id}: {update_error}")
                                errors += 1
                        else:
                            errors += 1

                    # Commit successful updates
                    db.commit()
                    processed += batch_processed

                    # Update task state for progress tracking
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current_batch": batch_num + 1,
                            "total_batches": total_batches,
                            "processed": processed,
                            "errors": errors,
                            "total": len(article_ids),
                        },
                    )

                    print(
                        f"Batch {batch_num + 1}/{total_batches} completed: "
                        f"processed {processed}, errors {errors}"
                    )

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
                "total": len(article_ids),
            }
        except Exception as e:
            print(f"Error in batch embedding generation: {e}")
            return {"success": False, "error": str(e), "processed": processed, "errors": errors}
        finally:
            loop.close()
