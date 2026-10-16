"""Persist notifications in the same transaction as newly ingested articles."""

import functools
from urllib.parse import urlparse

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.external_notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationRule,
    NotificationRuleChannel,
)
from app.models.feed import Feed


def article_message(article: Article, feed: Feed) -> str:
    parts = ["📰 RSS 新文章", f"标题：{article.title[:500]}", f"来源：{feed.title}"]
    if article.published_at:
        timestamp = article.published_at.isoformat()
        if article.published_at.tzinfo is None:
            timestamp += "Z"
        parts.append(f"发布时间：{timestamp}")
    if article.link and urlparse(article.link).scheme in {"http", "https"}:
        parts.append(f"原文：{article.link}")
    return "\n".join(parts)[:4000]


def enqueue_new_articles(db: Session, articles: list[Article]) -> int:
    if not articles:
        return 0
    feed_ids = {article.feed_id for article in articles}
    feeds = {
        feed.id: feed for feed in db.execute(select(Feed).where(Feed.id.in_(feed_ids))).scalars()
    }
    user_ids = {feed.user_id for feed in feeds.values()}
    routes = db.execute(
        select(NotificationRule, NotificationChannel)
        .join(NotificationRuleChannel, NotificationRuleChannel.rule_id == NotificationRule.id)
        .join(NotificationChannel, NotificationChannel.id == NotificationRuleChannel.channel_id)
        .where(
            NotificationRule.user_id.in_(user_ids),
            NotificationRule.is_enabled.is_(True),
            NotificationChannel.is_enabled.is_(True),
            NotificationChannel.user_id == NotificationRule.user_id,
        )
    ).all()
    if not routes:
        return 0
    seen = set()
    for offset in range(0, len(articles), 500):
        ids = [article.id for article in articles[offset : offset + 500]]
        seen.update(
            db.execute(
                select(NotificationDelivery.channel_id, NotificationDelivery.article_id).where(
                    NotificationDelivery.article_id.in_(ids)
                )
            ).all()
        )
    count = 0
    for article in articles:
        feed = feeds.get(article.feed_id)
        if not feed:
            continue
        for rule, channel in routes:
            if rule.user_id != feed.user_id:
                continue
            source_id = feed.id if rule.source_type == "feed" else feed.category_id
            if source_id != rule.source_id or (channel.id, article.id) in seen:
                continue
            seen.add((channel.id, article.id))
            db.add(
                NotificationDelivery(
                    user_id=feed.user_id,
                    channel_id=channel.id,
                    article_id=article.id,
                    channel_name=channel.name,
                    provider=channel.provider,
                    article_title=article.title,
                    message=article_message(article, feed),
                )
            )
            count += 1
    return count


def _remember_articles(db, _context, _instances):
    db.info["new_notification_articles"] = (
        []
        if db.info.get("suppress_external_notifications")
        else [item for item in db.new if isinstance(item, Article)]
    )


def _save_deliveries(db, _context):
    articles = db.info.pop("new_notification_articles", [])
    enqueue_new_articles(db, articles)


def install_outbox_hooks() -> None:
    if not event.contains(Session, "before_flush", _remember_articles):
        event.listen(Session, "before_flush", _remember_articles)
        event.listen(Session, "after_flush_postexec", _save_deliveries)


def suppress_import_notifications(operation):
    @functools.wraps(operation)
    async def wrapped(db, *args, **kwargs):
        previous = db.sync_session.info.get("suppress_external_notifications", False)
        db.sync_session.info["suppress_external_notifications"] = True
        try:
            return await operation(db, *args, **kwargs)
        finally:
            db.sync_session.info["suppress_external_notifications"] = previous

    return wrapped
