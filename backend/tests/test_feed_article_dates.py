from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.article import Article
from app.models.feed import Feed
from app.models.user import User
from app.services.feed_service import FeedService
from app.utils.feed_parser import ParsedArticle, ParsedFeed


@pytest.mark.asyncio
async def test_save_articles_uses_fetch_time_when_published_at_missing(db_session):
    user = User(
        username="date_user",
        email="date_user@example.com",
        password_hash="x",
    )
    db_session.add(user)
    await db_session.flush()

    feed = Feed(
        user_id=user.id,
        url="https://example.com/feed.xml",
        title="No Date Feed",
    )
    db_session.add(feed)
    await db_session.commit()
    await db_session.refresh(feed)

    before_save = datetime.utcnow()
    count = await FeedService(db_session)._save_articles(
        user.id,
        feed,
        ParsedFeed(
            title="No Date Feed",
            description=None,
            site_url=None,
            icon_url=None,
            articles=[
                ParsedArticle(
                    guid="no-date-1",
                    title="No date item",
                    link="https://example.com/no-date-1",
                    content=None,
                    author=None,
                    published_at=None,
                )
            ],
        ),
    )
    after_save = datetime.utcnow()

    article = (
        await db_session.execute(select(Article).where(Article.guid == "no-date-1"))
    ).scalar_one()

    assert count == 1
    assert article.published_at is not None
    assert before_save <= article.published_at <= after_save
