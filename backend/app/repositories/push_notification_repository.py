"""Repository for push notification data access."""
from datetime import datetime
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.push_notification import (
    NotificationSubscription,
    NotificationPush,
    WebPushSubscription,
)
from app.models.feed import Feed
from app.models.category import Category
from app.models.article import Article


class PushNotificationRepository:
    """Repository for push notification operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ============ Subscription CRUD ============

    async def create_subscription(
        self, user_id: int, data: dict
    ) -> NotificationSubscription:
        """Create a new subscription."""
        subscription = NotificationSubscription(user_id=user_id, **data)
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def get_subscription(
        self, subscription_id: int, user_id: int
    ) -> NotificationSubscription | None:
        """Get a subscription by ID."""
        result = await self.session.execute(
            select(NotificationSubscription).where(
                NotificationSubscription.id == subscription_id,
                NotificationSubscription.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_subscriptions(
        self, user_id: int
    ) -> list[NotificationSubscription]:
        """Get all subscriptions for a user."""
        result = await self.session.execute(
            select(NotificationSubscription)
            .where(NotificationSubscription.user_id == user_id)
            .order_by(NotificationSubscription.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_subscription(
        self, subscription: NotificationSubscription, data: dict
    ) -> NotificationSubscription:
        """Update a subscription."""
        for key, value in data.items():
            if value is not None:
                setattr(subscription, key, value)
        subscription.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def delete_subscription(self, subscription: NotificationSubscription) -> None:
        """Delete a subscription."""
        await self.session.delete(subscription)
        await self.session.commit()

    async def toggle_subscription(
        self, subscription: NotificationSubscription
    ) -> NotificationSubscription:
        """Toggle subscription enabled status."""
        subscription.is_enabled = not subscription.is_enabled
        subscription.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    # ============ Push Record Operations ============

    async def create_push(
        self, user_id: int, subscription_id: int, article_id: int
    ) -> NotificationPush:
        """Create a push record."""
        push = NotificationPush(
            user_id=user_id,
            subscription_id=subscription_id,
            article_id=article_id,
            status="sent",
            pushed_at=datetime.utcnow(),
        )
        self.session.add(push)
        await self.session.commit()
        await self.session.refresh(push)
        return push

    async def get_user_pushes(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
        status: str | None = None,
    ) -> tuple[list[NotificationPush], int]:
        """Get user's push records with pagination."""
        query = select(NotificationPush).where(NotificationPush.user_id == user_id)

        if status:
            query = query.where(NotificationPush.status == status)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.order_by(NotificationPush.pushed_at.desc())
        query = query.offset((page - 1) * size).limit(size)
        query = query.options(
            joinedload(NotificationPush.subscription),
            joinedload(NotificationPush.article),
        )

        result = await self.session.execute(query)
        pushes = list(result.scalars().all())

        return pushes, total

    async def mark_push_read(self, push_id: int, user_id: int) -> bool:
        """Mark a push as read."""
        result = await self.session.execute(
            select(NotificationPush).where(
                NotificationPush.id == push_id,
                NotificationPush.user_id == user_id,
            )
        )
        push = result.scalar_one_or_none()

        if not push:
            return False

        push.status = "read"
        push.read_at = datetime.utcnow()
        await self.session.commit()
        return True

    async def mark_push_clicked(self, push_id: int, user_id: int) -> bool:
        """Mark a push as clicked."""
        result = await self.session.execute(
            select(NotificationPush).where(
                NotificationPush.id == push_id,
                NotificationPush.user_id == user_id,
            )
        )
        push = result.scalar_one_or_none()

        if not push:
            return False

        push.status = "clicked"
        push.clicked_at = datetime.utcnow()
        if not push.read_at:
            push.read_at = datetime.utcnow()
        await self.session.commit()
        return True

    async def get_unread_push_count(self, user_id: int) -> int:
        """Get count of unread pushes."""
        result = await self.session.execute(
            select(func.count())
            .select_from(NotificationPush)
            .where(
                NotificationPush.user_id == user_id,
                NotificationPush.status == "sent",
            )
        )
        return result.scalar() or 0

    async def check_push_exists(
        self, subscription_id: int, article_id: int
    ) -> bool:
        """Check if a push already exists."""
        result = await self.session.execute(
            select(NotificationPush).where(
                NotificationPush.subscription_id == subscription_id,
                NotificationPush.article_id == article_id,
            )
        )
        return result.scalar_one_or_none() is not None

    # ============ Web Push Subscription Operations ============

    async def create_web_push_subscription(
        self, user_id: int, endpoint: str, p256dh: str, auth: str, user_agent: str | None
    ) -> WebPushSubscription:
        """Create or update Web Push subscription."""
        # Check if already exists
        result = await self.session.execute(
            select(WebPushSubscription).where(
                WebPushSubscription.user_id == user_id,
                WebPushSubscription.endpoint == endpoint,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.p256dh = p256dh
            existing.auth = auth
            existing.user_agent = user_agent
            existing.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        # Create new
        subscription = WebPushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=user_agent,
        )
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def get_web_push_subscriptions(
        self, user_id: int
    ) -> list[WebPushSubscription]:
        """Get all Web Push subscriptions for a user."""
        result = await self.session.execute(
            select(WebPushSubscription).where(
                WebPushSubscription.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def delete_web_push_subscription(
        self, user_id: int, endpoint: str
    ) -> bool:
        """Delete a Web Push subscription."""
        result = await self.session.execute(
            select(WebPushSubscription).where(
                WebPushSubscription.user_id == user_id,
                WebPushSubscription.endpoint == endpoint,
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            return False

        await self.session.delete(subscription)
        await self.session.commit()
        return True

    # ============ Helper Methods ============

    async def get_feed_name(self, feed_id: int) -> str | None:
        """Get feed name by ID."""
        result = await self.session.execute(
            select(Feed.title).where(Feed.id == feed_id)
        )
        return result.scalar_one_or_none()

    async def get_category_name(self, category_id: int) -> str | None:
        """Get category name by ID."""
        result = await self.session.execute(
            select(Category.name).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()
