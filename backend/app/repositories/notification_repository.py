"""Notification repository for database operations."""
from datetime import datetime, timezone
from typing import List

from sqlalchemy import and_, select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notification import Notification, UserNotificationRead


class NotificationRepository:
    """Repository for Notification database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        title: str,
        content: str,
        type: str = 'system',
        created_by: int | None = None,
        expires_at: datetime | None = None
    ) -> Notification:
        """Create a new notification."""
        notification = Notification(
            title=title,
            content=content,
            type=type,
            created_by=created_by,
            expires_at=expires_at,
            is_active=True
        )
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def get_by_id(self, notification_id: int) -> Notification | None:
        """Get notification by ID."""
        result = await self.session.execute(
            select(Notification)
            .options(selectinload(Notification.creator))
            .where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[Notification]:
        """Get all active notifications (admin view)."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Notification)
            .options(selectinload(Notification.creator))
            .where(Notification.is_active == True)
            .where(
                or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > now
                )
            )
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_all(self) -> List[Notification]:
        """Get all notifications (admin view, including inactive)."""
        result = await self.session.execute(
            select(Notification)
            .options(selectinload(Notification.creator))
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_unread_for_user(self, user_id: int) -> List[Notification]:
        """Get unread active notifications for a user."""
        now = datetime.now(timezone.utc)
        
        # Subquery to get read notification IDs for this user
        read_subquery = (
            select(UserNotificationRead.notification_id)
            .where(UserNotificationRead.user_id == user_id)
        )
        
        result = await self.session.execute(
            select(Notification)
            .options(selectinload(Notification.creator))
            .where(Notification.is_active == True)
            .where(
                or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > now
                )
            )
            .where(Notification.id.not_in(read_subquery))
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_as_read(self, user_id: int, notification_id: int) -> bool:
        """Mark a notification as read for a user."""
        # Check if already read
        existing = await self.session.execute(
            select(UserNotificationRead).where(
                and_(
                    UserNotificationRead.user_id == user_id,
                    UserNotificationRead.notification_id == notification_id
                )
            )
        )
        if existing.scalar_one_or_none():
            return False  # Already read
        
        read_record = UserNotificationRead(
            user_id=user_id,
            notification_id=notification_id,
            read_at=datetime.now(timezone.utc)
        )
        self.session.add(read_record)
        await self.session.flush()
        return True

    async def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user."""
        unread = await self.get_unread_for_user(user_id)
        count = 0
        for notification in unread:
            if await self.mark_as_read(user_id, notification.id):
                count += 1
        return count

    async def update(
        self,
        notification: Notification,
        title: str | None = None,
        content: str | None = None,
        type: str | None = None,
        is_active: bool | None = None,
        expires_at: datetime | None = None
    ) -> Notification:
        """Update a notification."""
        if title is not None:
            notification.title = title
        if content is not None:
            notification.content = content
        if type is not None:
            notification.type = type
        if is_active is not None:
            notification.is_active = is_active
        if expires_at is not None:
            notification.expires_at = expires_at
        await self.session.flush()
        return notification

    async def delete(self, notification_id: int) -> bool:
        """Delete a notification."""
        notification = await self.get_by_id(notification_id)
        if not notification:
            return False
        await self.session.delete(notification)
        await self.session.flush()
        return True

    async def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications for a user."""
        now = datetime.now(timezone.utc)
        
        read_subquery = (
            select(UserNotificationRead.notification_id)
            .where(UserNotificationRead.user_id == user_id)
        )
        
        result = await self.session.execute(
            select(func.count(Notification.id))
            .where(Notification.is_active == True)
            .where(
                or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > now
                )
            )
            .where(Notification.id.not_in(read_subquery))
        )
        return result.scalar() or 0
