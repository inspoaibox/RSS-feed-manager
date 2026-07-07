from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.models.article import Article
from app.models.feed import Feed
from app.models.user import User
from app.tasks import feed_tasks
from app.utils.feed_parser import ParsedArticle, ParsedFeed


def _sync_session_factory(tmp_path):
    db_path = tmp_path / "postprocess.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def test_refresh_feed_dispatches_heavy_postprocess_without_sync_embedding(monkeypatch, tmp_path):
    engine, SessionLocal = _sync_session_factory(tmp_path)
    calls: list[tuple[str, int | None, bool | None]] = []

    def record_summary(article_id):
        calls.append(("summary", article_id, None))

    def record_embedding(article_id, *, auto=True):
        calls.append(("embedding", article_id, auto))

    def record_push(article_id):
        calls.append(("push", article_id, None))

    monkeypatch.setattr(feed_tasks, "_parse_feed_for_sync_refresh", lambda db, feed: ParsedFeed(
        title="Parsed Feed",
        description=None,
        site_url=None,
        icon_url=None,
        articles=[
            ParsedArticle(
                guid="postprocess-1",
                title="Postprocess item",
                link="https://example.com/postprocess-1",
                content="body",
                author=None,
                published_at=datetime.utcnow(),
            )
        ],
    ))
    monkeypatch.setattr(feed_tasks, "_dispatch_article_summary", record_summary)
    monkeypatch.setattr(feed_tasks, "_dispatch_article_embedding", record_embedding)
    monkeypatch.setattr(feed_tasks, "_dispatch_article_push", record_push)

    assert not hasattr(feed_tasks, "_generate_article_embedding_sync")

    try:
        with SessionLocal() as db:
            user = User(
                username="postprocess_user",
                email="postprocess_user@example.com",
                password_hash="x",
                auto_generate_summaries=True,
                auto_generate_embeddings=True,
                embedding_provider_id=123,
                embedding_model="text-embedding-3-small",
            )
            db.add(user)
            db.flush()
            feed = Feed(
                user_id=user.id,
                url="https://example.com/feed.xml",
                title="Postprocess Feed",
                auto_summarize=True,
            )
            db.add(feed)
            db.commit()
            db.refresh(feed)

            assert feed_tasks._refresh_feed_sync(db, feed) == 1

            article_id = db.execute(
                select(Article.id).where(Article.guid == "postprocess-1")
            ).scalar_one()

        assert calls == [
            ("summary", article_id, None),
            ("embedding", article_id, True),
            ("push", article_id, None),
        ]
    finally:
        engine.dispose()


def test_refresh_feed_does_not_dispatch_auto_embedding_when_switch_disabled(monkeypatch, tmp_path):
    engine, SessionLocal = _sync_session_factory(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(feed_tasks, "_parse_feed_for_sync_refresh", lambda db, feed: ParsedFeed(
        title="Parsed Feed",
        description=None,
        site_url=None,
        icon_url=None,
        articles=[
            ParsedArticle(
                guid="postprocess-disabled-1",
                title="Postprocess item",
                link="https://example.com/postprocess-disabled-1",
                content="body",
                author=None,
                published_at=datetime.utcnow(),
            )
        ],
    ))
    monkeypatch.setattr(
        feed_tasks,
        "_dispatch_article_summary",
        lambda article_id: calls.append("summary"),
    )
    monkeypatch.setattr(
        feed_tasks,
        "_dispatch_article_embedding",
        lambda article_id, *, auto=True: calls.append("embedding"),
    )
    monkeypatch.setattr(
        feed_tasks,
        "_dispatch_article_push",
        lambda article_id: calls.append("push"),
    )

    try:
        with SessionLocal() as db:
            user = User(
                username="postprocess_disabled_user",
                email="postprocess_disabled_user@example.com",
                password_hash="x",
                auto_generate_summaries=False,
                auto_generate_embeddings=False,
                embedding_provider_id=123,
                embedding_model="text-embedding-3-small",
            )
            db.add(user)
            db.flush()
            feed = Feed(
                user_id=user.id,
                url="https://example.com/disabled.xml",
                title="Postprocess Disabled Feed",
                auto_summarize=False,
            )
            db.add(feed)
            db.commit()
            db.refresh(feed)

            assert feed_tasks._refresh_feed_sync(db, feed) == 1

        assert calls == ["push"]
    finally:
        engine.dispose()


def test_refresh_feed_does_not_dispatch_summary_when_global_switch_disabled(monkeypatch, tmp_path):
    engine, SessionLocal = _sync_session_factory(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(feed_tasks, "_parse_feed_for_sync_refresh", lambda db, feed: ParsedFeed(
        title="Parsed Feed",
        description=None,
        site_url=None,
        icon_url=None,
        articles=[
            ParsedArticle(
                guid="summary-global-disabled-1",
                title="Summary item",
                link="https://example.com/summary-global-disabled-1",
                content="body",
                author=None,
                published_at=datetime.utcnow(),
            )
        ],
    ))
    monkeypatch.setattr(
        feed_tasks,
        "_dispatch_article_summary",
        lambda article_id: calls.append("summary"),
    )
    monkeypatch.setattr(
        feed_tasks,
        "_dispatch_article_embedding",
        lambda article_id, *, auto=True: calls.append("embedding"),
    )
    monkeypatch.setattr(
        feed_tasks,
        "_dispatch_article_push",
        lambda article_id: calls.append("push"),
    )

    try:
        with SessionLocal() as db:
            user = User(
                username="summary_global_disabled_user",
                email="summary_global_disabled_user@example.com",
                password_hash="x",
                auto_generate_summaries=False,
            )
            db.add(user)
            db.flush()
            feed = Feed(
                user_id=user.id,
                url="https://example.com/summary-disabled.xml",
                title="Summary Disabled Feed",
                auto_summarize=True,
            )
            db.add(feed)
            db.commit()
            db.refresh(feed)

            assert feed_tasks._refresh_feed_sync(db, feed) == 1

        assert calls == ["push"]
    finally:
        engine.dispose()
