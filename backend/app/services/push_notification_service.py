"""Push notification service for triggering and sending notifications."""
import json
import logging
from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import Session

from app.models.push_notification import NotificationSubscription, NotificationPush, WebPushSubscription
from app.models.article import Article
from app.models.feed import Feed

if TYPE_CHECKING:
    from app.models.user import User

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Service for handling push notifications."""

    def __init__(self, db: Session):
        self.db = db

    def check_and_trigger_pushes(self, article: Article) -> int:
        """Check if article matches any subscriptions and trigger pushes.

        Returns:
            Number of pushes sent
        """
        feed = article.feed
        if not feed:
            return 0

        category_id = feed.category_id if feed else None

        # Find matching subscriptions
        subscriptions = self._find_matching_subscriptions(article, feed.id, category_id)

        if not subscriptions:
            return 0

        pushes_sent = 0
        for subscription in subscriptions:
            # Check if already pushed
            if self._push_exists(subscription.id, article.id):
                continue

            # Check quiet hours
            if self._is_in_quiet_hours(subscription.quiet_hours):
                logger.info(f"Skipping push for subscription {subscription.id} (quiet hours)")
                continue

            # Send push
            try:
                self._send_push(subscription, article)
                pushes_sent += 1
            except Exception as e:
                logger.error(f"Failed to send push for subscription {subscription.id}: {e}")

        return pushes_sent

    def _find_matching_subscriptions(
        self, article: Article, feed_id: int, category_id: int | None
    ) -> list[NotificationSubscription]:
        """Find subscriptions that match this article."""
        conditions = []

        # Feed subscription
        conditions.append(
            and_(
                NotificationSubscription.subscription_type == 'feed',
                NotificationSubscription.target_id == feed_id
            )
        )

        # Category subscription
        if category_id:
            conditions.append(
                and_(
                    NotificationSubscription.subscription_type == 'category',
                    NotificationSubscription.target_id == category_id
                )
            )

        # Keyword subscription
        # Check if article title or content contains keyword (case-insensitive)
        keyword_subs = self.db.execute(
            select(NotificationSubscription)
            .where(
                NotificationSubscription.subscription_type == 'keyword',
                NotificationSubscription.is_enabled == True
            )
        ).scalars().all()

        matching_keyword_subs = []
        for sub in keyword_subs:
            if sub.keyword:
                keyword_lower = sub.keyword.lower()
                title_lower = (article.title or '').lower()
                content_lower = (article.content or '').lower()

                if keyword_lower in title_lower or keyword_lower in content_lower:
                    matching_keyword_subs.append(sub.id)

        # Query feed/category subscriptions
        query = select(NotificationSubscription).where(
            NotificationSubscription.is_enabled == True,
            or_(*conditions) if conditions else False
        )

        feed_category_subs = list(self.db.execute(query).scalars().all())

        # Query keyword subscriptions
        if matching_keyword_subs:
            keyword_query = select(NotificationSubscription).where(
                NotificationSubscription.id.in_(matching_keyword_subs)
            )
            keyword_results = list(self.db.execute(keyword_query).scalars().all())
            return feed_category_subs + keyword_results

        return feed_category_subs

    def _push_exists(self, subscription_id: int, article_id: int) -> bool:
        """Check if push already exists."""
        result = self.db.execute(
            select(NotificationPush).where(
                NotificationPush.subscription_id == subscription_id,
                NotificationPush.article_id == article_id
            )
        )
        return result.scalar_one_or_none() is not None

    def _is_in_quiet_hours(self, quiet_hours: str | None) -> bool:
        """Check if current time is within quiet hours."""
        if not quiet_hours:
            return False

        try:
            hours_data = json.loads(quiet_hours)
            start_str = hours_data.get('start')
            end_str = hours_data.get('end')

            if not start_str or not end_str:
                return False

            # Parse time strings
            start_time = datetime.strptime(start_str, '%H:%M').time()
            end_time = datetime.strptime(end_str, '%H:%M').time()
            current_time = datetime.now().time()

            # Handle quiet hours that span midnight
            if start_time <= end_time:
                # Normal case: start < end (e.g., 08:00 - 18:00)
                return start_time <= current_time <= end_time
            else:
                # Spans midnight: start > end (e.g., 23:00 - 07:00)
                return current_time >= start_time or current_time <= end_time

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Invalid quiet_hours format: {quiet_hours}, error: {e}")
            return False

    def _send_push(self, subscription: NotificationSubscription, article: Article) -> None:
        """Send push notification."""
        user = subscription.user

        # Create push record
        push = NotificationPush(
            user_id=user.id,
            subscription_id=subscription.id,
            article_id=article.id,
            status='sent',
            pushed_at=datetime.utcnow()
        )
        self.db.add(push)
        self.db.flush()  # Get push ID

        # Construct notification content
        title = f"📰 {subscription.name}"
        body = article.title[:100] if article.title else "新文章"
        url = f"/articles/{article.id}"

        # Send Web Push if enabled
        if subscription.browser_notification:
            self._send_web_push(user.id, title, body, url, push.id)

        # Desktop notification is handled by frontend via WebSocket
        # We'll add WebSocket support later
        if subscription.desktop_notification:
            logger.info(f"Desktop notification for push {push.id} (handled by frontend)")

        self.db.commit()
        logger.info(f"Push sent: subscription={subscription.id}, article={article.id}, push={push.id}")

    def _send_web_push(self, user_id: int, title: str, body: str, url: str, push_id: int) -> None:
        """Send Web Push notification."""
        try:
            from pywebpush import webpush, WebPushException
            from app.core.config import settings
        except ImportError:
            logger.warning("pywebpush not installed, skipping Web Push")
            return

        # Get user's Web Push subscriptions
        web_subs = self.db.execute(
            select(WebPushSubscription).where(WebPushSubscription.user_id == user_id)
        ).scalars().all()

        if not web_subs:
            logger.info(f"No Web Push subscriptions for user {user_id}")
            return

        # Check VAPID keys
        vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        vapid_contact_email = getattr(settings, 'VAPID_CONTACT_EMAIL', None)

        if not vapid_private_key or not vapid_contact_email:
            logger.warning("VAPID keys not configured, skipping Web Push")
            return

        payload = json.dumps({
            'title': title,
            'body': body,
            'icon': '/icon.png',
            'badge': '/badge.png',
            'url': url,
            'push_id': push_id,
            'tag': f'push-{push_id}',
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        })

        for web_sub in web_subs:
            try:
                webpush(
                    subscription_info={
                        'endpoint': web_sub.endpoint,
                        'keys': {
                            'p256dh': web_sub.p256dh,
                            'auth': web_sub.auth
                        }
                    },
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={
                        'sub': f'mailto:{vapid_contact_email}'
                    },
                    timeout=10
                )
                logger.info(f"Web Push sent to user {user_id}, endpoint: {web_sub.endpoint[:50]}...")
            except WebPushException as e:
                logger.error(f"Web Push failed for user {user_id}: {e}")

                # If subscription is expired or invalid, mark push as failed
                if e.response and e.response.status_code in [404, 410]:
                    logger.info(f"Removing expired Web Push subscription: {web_sub.id}")
                    self.db.delete(web_sub)

                # Update push status
                push = self.db.get(NotificationPush, push_id)
                if push:
                    push.status = 'failed'

                self.db.commit()
            except Exception as e:
                logger.error(f"Unexpected error sending Web Push: {e}")


def trigger_push_notifications_for_article(db: Session, article_id: int) -> None:
    """Trigger push notifications for an article (to be called from tasks)."""
    article = db.execute(
        select(Article).where(Article.id == article_id)
    ).scalar_one_or_none()

    if not article:
        logger.warning(f"Article {article_id} not found for push notifications")
        return

    service = PushNotificationService(db)
    pushes_sent = service.check_and_trigger_pushes(article)

    if pushes_sent > 0:
        logger.info(f"Sent {pushes_sent} push notifications for article {article_id}")
