"""Tests for keyword subscription source filters."""
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.article import Article, UserArticle
from app.models.category import Category
from app.models.feed import Feed
from app.models.user import User
from app.repositories.article_repository import ArticleRepository
from app.repositories.keyword_subscription_repository import KeywordSubscriptionRepository
from app.schemas.keyword_subscription import KeywordSubscriptionCreate, KeywordSubscriptionUpdate
from app.services.keyword_subscription_service import KeywordSubscriptionService


@pytest.mark.asyncio
async def test_keyword_subscription_excluded_sources_filter_articles_and_counts(db_session):
    """Excluded categories and feeds should not appear in keyword results."""
    user = User(
        username="keyword-user",
        email="keyword-user@example.com",
        password_hash="test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    keep_category = Category(user_id=user.id, name="Keep", description=None, position=0)
    blocked_category = Category(user_id=user.id, name="Blocked", description=None, position=1)
    db_session.add_all([keep_category, blocked_category])
    await db_session.flush()

    keep_feed = Feed(
        user_id=user.id,
        category_id=keep_category.id,
        url="https://keep.example.com/rss",
        title="Keep Feed",
        position=0,
    )
    blocked_category_feed = Feed(
        user_id=user.id,
        category_id=blocked_category.id,
        url="https://blocked-category.example.com/rss",
        title="Blocked Category Feed",
        position=1,
    )
    blocked_feed = Feed(
        user_id=user.id,
        category_id=None,
        url="https://blocked-feed.example.com/rss",
        title="Blocked Feed",
        position=2,
    )
    db_session.add_all([keep_feed, blocked_category_feed, blocked_feed])
    await db_session.flush()

    now = datetime.utcnow()
    db_session.add_all(
        [
            Article(
                feed_id=keep_feed.id,
                guid="keep-1",
                link="https://keep.example.com/articles/1",
                title="alpha keep",
                content="alpha content",
                published_at=now,
            ),
            Article(
                feed_id=blocked_category_feed.id,
                guid="blocked-category-1",
                link="https://blocked-category.example.com/articles/1",
                title="alpha blocked by category",
                content="alpha content",
                published_at=now,
            ),
            Article(
                feed_id=blocked_feed.id,
                guid="blocked-feed-1",
                link="https://blocked-feed.example.com/articles/1",
                title="alpha blocked by feed",
                content="alpha content",
                published_at=now,
            ),
        ]
    )
    await db_session.flush()

    keyword_repo = KeywordSubscriptionRepository(db_session)
    keyword = await keyword_repo.create(
        user_id=user.id,
        keyword="alpha",
        name="alpha",
        excluded_category_ids=[blocked_category.id],
        excluded_feed_ids=[blocked_feed.id],
    )

    article_repo = ArticleRepository(db_session)
    articles, total = await article_repo.get_articles_paginated(
        user_id=user.id,
        keyword=keyword,
        page=1,
        page_size=50,
    )

    assert total == 1
    assert len(articles) == 1
    assert articles[0]["article"].feed_id == keep_feed.id

    counts = await keyword_repo.get_article_counts(user.id, [keyword])
    assert counts[keyword.id]["article_count"] == 1
    assert counts[keyword.id]["unread_count"] == 1

    marked = await article_repo.mark_all_read_by_keyword(user.id, keyword)
    assert marked == 1

    counts_after_mark_read = await keyword_repo.get_article_counts(user.id, [keyword])
    assert counts_after_mark_read[keyword.id]["article_count"] == 1
    assert counts_after_mark_read[keyword.id]["unread_count"] == 0


@pytest.mark.asyncio
async def test_keyword_subscription_counts_multiple_keywords(db_session):
    """Keyword counts should be calculated for multiple subscriptions together."""
    user = User(
        username="keyword-counts-user",
        email="keyword-counts-user@example.com",
        password_hash="test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    feed = Feed(
        user_id=user.id,
        category_id=None,
        url="https://counts.example.com/rss",
        title="Counts Feed",
        position=0,
    )
    db_session.add(feed)
    await db_session.flush()

    now = datetime.utcnow()
    alpha_article = Article(
        feed_id=feed.id,
        guid="alpha-1",
        link="https://counts.example.com/alpha",
        title="alpha launch",
        content="plain content",
        published_at=now,
    )
    beta_article = Article(
        feed_id=feed.id,
        guid="beta-1",
        link="https://counts.example.com/beta",
        title="other launch",
        content="beta content",
        published_at=now,
    )
    db_session.add_all([alpha_article, beta_article])
    await db_session.flush()
    db_session.add(
        UserArticle(
            user_id=user.id,
            article_id=beta_article.id,
            is_read=True,
            read_at=now,
        )
    )
    await db_session.flush()

    keyword_repo = KeywordSubscriptionRepository(db_session)
    alpha_keyword = await keyword_repo.create(user_id=user.id, keyword="alpha", name="alpha")
    beta_keyword = await keyword_repo.create(user_id=user.id, keyword="beta", name="beta")

    counts = await keyword_repo.get_article_counts(user.id, [alpha_keyword, beta_keyword])

    assert counts[alpha_keyword.id]["article_count"] == 1
    assert counts[alpha_keyword.id]["unread_count"] == 1
    assert counts[beta_keyword.id]["article_count"] == 1
    assert counts[beta_keyword.id]["unread_count"] == 0


@pytest.mark.asyncio
async def test_keyword_subscription_service_returns_counts_after_create_and_update(db_session):
    """Create and update responses should include current article counts."""
    user = User(
        username="keyword-service-user",
        email="keyword-service-user@example.com",
        password_hash="test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    feed = Feed(
        user_id=user.id,
        category_id=None,
        url="https://service-counts.example.com/rss",
        title="Service Counts Feed",
        position=0,
    )
    db_session.add(feed)
    await db_session.flush()

    now = datetime.utcnow()
    db_session.add_all(
        [
            Article(
                feed_id=feed.id,
                guid="service-alpha",
                link="https://service-counts.example.com/alpha",
                title="alpha launch",
                content="plain content",
                published_at=now,
            ),
            Article(
                feed_id=feed.id,
                guid="service-beta",
                link="https://service-counts.example.com/beta",
                title="beta launch",
                content="plain content",
                published_at=now,
            ),
        ]
    )
    await db_session.flush()

    service = KeywordSubscriptionService(db_session)
    created = await service.create(
        user.id,
        KeywordSubscriptionCreate(keyword="alpha", name="alpha"),
    )

    assert created.article_count == 1
    assert created.unread_count == 1

    updated = await service.update(
        user.id,
        created.id,
        KeywordSubscriptionUpdate(keyword="beta", name="beta"),
    )

    assert updated.article_count == 1
    assert updated.unread_count == 1


@pytest.mark.asyncio
async def test_mark_all_read_by_feed_batches_user_article_state(db_session):
    """Mark-all-read should update existing states and create missing states in bulk."""
    user = User(
        username="bulk-read-user",
        email="bulk-read-user@example.com",
        password_hash="test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    feed = Feed(
        user_id=user.id,
        category_id=None,
        url="https://bulk.example.com/rss",
        title="Bulk Feed",
        position=0,
    )
    db_session.add(feed)
    await db_session.flush()

    now = datetime.utcnow()
    articles = [
        Article(
            feed_id=feed.id,
            guid=f"bulk-{idx}",
            link=f"https://bulk.example.com/{idx}",
            title=f"bulk article {idx}",
            content="content",
            published_at=now,
        )
        for idx in range(3)
    ]
    db_session.add_all(articles)
    await db_session.flush()
    db_session.add_all(
        [
            UserArticle(
                user_id=user.id,
                article_id=articles[0].id,
                is_read=False,
                is_favorite=True,
            ),
            UserArticle(
                user_id=user.id,
                article_id=articles[1].id,
                is_read=True,
                read_at=now,
            ),
        ]
    )
    await db_session.flush()

    article_repo = ArticleRepository(db_session)
    marked = await article_repo.mark_all_read_by_feed(user.id, feed.id)

    assert marked == 2
    states = (
        await db_session.execute(
            select(UserArticle).where(UserArticle.user_id == user.id)
        )
    ).scalars().all()
    state_by_article = {state.article_id: state for state in states}
    assert len(state_by_article) == 3
    assert all(state.is_read for state in state_by_article.values())
    assert state_by_article[articles[0].id].is_favorite is True
