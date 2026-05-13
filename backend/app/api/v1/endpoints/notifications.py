"""Notification API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_id, get_db
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import (
    NotificationCreate,
    NotificationUpdate,
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
)

router = APIRouter()


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin user."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return user


def _notification_to_response(notification) -> NotificationResponse:
    """Convert notification model to response schema."""
    return NotificationResponse(
        id=notification.id,
        title=notification.title,
        content=notification.content,
        type=notification.type,
        is_active=notification.is_active,
        created_by=notification.created_by,
        creator_name=notification.creator.username if notification.creator else None,
        expires_at=notification.expires_at,
        created_at=notification.created_at,
    )


# ============ User endpoints (must be before /{notification_id}) ============

@router.get("/unread", response_model=NotificationListResponse)
async def get_unread_notifications(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get unread notifications for current user."""
    repo = NotificationRepository(db)
    notifications = await repo.get_unread_for_user(user_id)
    return NotificationListResponse(
        notifications=[_notification_to_response(n) for n in notifications],
        total=len(notifications)
    )


@router.get("/unread/count", response_model=UnreadCountResponse)
async def get_unread_count(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get count of unread notifications."""
    repo = NotificationRepository(db)
    count = await repo.get_unread_count(user_id)
    return UnreadCountResponse(count=count)


@router.post("/read-all", response_model=MarkReadResponse)
async def mark_all_read(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Mark all notifications as read."""
    repo = NotificationRepository(db)
    count = await repo.mark_all_as_read(user_id)
    await db.commit()
    
    return MarkReadResponse(
        success=True,
        message=f"已将 {count} 条通知标记为已读"
    )


# ============ Admin endpoints ============

@router.get("", response_model=NotificationListResponse)
async def get_all_notifications(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all notifications (admin only)."""
    repo = NotificationRepository(db)
    notifications = await repo.get_all()
    return NotificationListResponse(
        notifications=[_notification_to_response(n) for n in notifications],
        total=len(notifications)
    )


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    data: NotificationCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new notification (admin only)."""
    repo = NotificationRepository(db)
    notification = await repo.create(
        title=data.title,
        content=data.content,
        type=data.type,
        created_by=admin.id,
        expires_at=data.expires_at
    )
    await db.commit()
    
    # Reload to get creator relationship
    notification = await repo.get_by_id(notification.id)
    return _notification_to_response(notification)


# ============ Endpoints with path parameters (must be last) ============

@router.post("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_notification_read(
    notification_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Mark a notification as read."""
    repo = NotificationRepository(db)
    
    # Check notification exists
    notification = await repo.get_by_id(notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    success = await repo.mark_as_read(user_id, notification_id)
    await db.commit()
    
    return MarkReadResponse(
        success=True,
        message="已标记为已读" if success else "该通知已读"
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a notification by ID (admin only)."""
    repo = NotificationRepository(db)
    notification = await repo.get_by_id(notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    return _notification_to_response(notification)


@router.put("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: int,
    data: NotificationUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a notification (admin only)."""
    repo = NotificationRepository(db)
    notification = await repo.get_by_id(notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    notification = await repo.update(
        notification,
        title=data.title,
        content=data.content,
        type=data.type,
        is_active=data.is_active,
        expires_at=data.expires_at
    )
    await db.commit()
    
    return _notification_to_response(notification)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a notification (admin only)."""
    repo = NotificationRepository(db)
    success = await repo.delete(notification_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    await db.commit()
