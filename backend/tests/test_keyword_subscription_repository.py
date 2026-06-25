"""Tests for keyword subscription source filters."""
from datetime import datetime

import pytest

from app.models.article import Article
from app.models.category import Category
from app.models.feed import Feed
from app.models.user import User
from app.repositories.article_repository import ArticleRepository
from app.repositories.keyword_subscription_repository import KeywordSubscriptionRepository


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
