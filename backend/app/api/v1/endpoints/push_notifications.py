"""Push notification API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_db
from app.repositories.push_notification_repository import PushNotificationRepository
from app.schemas.push_notification import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionListResponse,
    PushResponse,
    PushListResponse,
    PushStatsResponse,
    WebPushSubscriptionCreate,
    WebPushSubscriptionResponse,
    VAPIDPublicKeyResponse,
)
from app.core.config import settings
import json

router = APIRouter()

CurrentUserId = Depends(get_current_user_id)
DbSession = Depends(get_db)


# ============ Subscription Endpoints ============

@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def get_subscriptions(
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Get all push subscriptions for current user."""
    repo = PushNotificationRepository(db)
    subscriptions = await repo.get_user_subscriptions(user_id)

    # Enrich with target names
    enriched = []
    for sub in subscriptions:
        target_name = None
        if sub.subscription_type == 'feed' and sub.target_id:
            target_name = await repo.get_feed_name(sub.target_id)
        elif sub.subscription_type == 'category' and sub.target_id:
            target_name = await repo.get_category_name(sub.target_id)
        elif sub.subscription_type == 'keyword':
            target_name = sub.keyword

        enriched.append(
            SubscriptionResponse(
                **sub.__dict__,
                target_name=target_name
            )
        )

    return SubscriptionListResponse(
        subscriptions=enriched,
        total=len(enriched)
    )


@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    data: SubscriptionCreate,
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Create a new push subscription."""
    repo = PushNotificationRepository(db)

    # Validate subscription type and target
    if data.subscription_type in ['feed', 'category'] and not data.target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"订阅{data.subscription_type}时必须提供 target_id"
        )

    if data.subscription_type == 'keyword' and not data.keyword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订阅关键词时必须提供 keyword"
        )

    # Convert quiet_hours to JSON string
    subscription_data = data.model_dump()
    if subscription_data.get('quiet_hours'):
        subscription_data['quiet_hours'] = json.dumps(subscription_data['quiet_hours'])

    subscription = await repo.create_subscription(user_id, subscription_data)

    # Get target name
    target_name = None
    if subscription.subscription_type == 'feed' and subscription.target_id:
        target_name = await repo.get_feed_name(subscription.target_id)
    elif subscription.subscription_type == 'category' and subscription.target_id:
        target_name = await repo.get_category_name(subscription.target_id)
    elif subscription.subscription_type == 'keyword':
        target_name = subscription.keyword

    return SubscriptionResponse(
        **subscription.__dict__,
        target_name=target_name
    )


@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdate,
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Update a push subscription."""
    repo = PushNotificationRepository(db)

    subscription = await repo.get_subscription(subscription_id, user_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订阅不存在"
        )

    # Convert quiet_hours to JSON string
    update_data = data.model_dump(exclude_unset=True)
    if 'quiet_hours' in update_data and update_data['quiet_hours']:
        update_data['quiet_hours'] = json.dumps(update_data['quiet_hours'])

    subscription = await repo.update_subscription(subscription, update_data)

    # Get target name
    target_name = None
    if subscription.subscription_type == 'feed' and subscription.target_id:
        target_name = await repo.get_feed_name(subscription.target_id)
    elif subscription.subscription_type == 'category' and subscription.target_id:
        target_name = await repo.get_category_name(subscription.target_id)
    elif subscription.subscription_type == 'keyword':
        target_name = subscription.keyword

    return SubscriptionResponse(
        **subscription.__dict__,
        target_name=target_name
    )


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: int,
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Delete a push subscription."""
    repo = PushNotificationRepository(db)

    subscription = await repo.get_subscription(subscription_id, user_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订阅不存在"
        )

    await repo.delete_subscription(subscription)


@router.post("/subscriptions/{subscription_id}/toggle", response_model=SubscriptionResponse)
async def toggle_subscription(
    subscription_id: int,
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Toggle subscription enabled status."""
    repo = PushNotificationRepository(db)

    subscription = await repo.get_subscription(subscription_id, user_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订阅不存在"
        )

    subscription = await repo.toggle_subscription(subscription)

    # Get target name
    target_name = None
    if subscription.subscription_type == 'feed' and subscription.target_id:
        target_name = await repo.get_feed_name(subscription.target_id)
    elif subscription.subscription_type == 'category' and subscription.target_id:
        target_name = await repo.get_category_name(subscription.target_id)
    elif subscription.subscription_type == 'keyword':
        target_name = subscription.keyword

    return SubscriptionResponse(
        **subscription.__dict__,
        target_name=target_name
    )


# ============ Push Record Endpoints ============

@router.get("/pushes", response_model=PushListResponse)
async def get_pushes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, regex="^(sent|read|clicked|failed)$"),
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Get push records with pagination."""
    repo = PushNotificationRepository(db)
    pushes, total = await repo.get_user_pushes(user_id, page, size, status)

    # Enrich with related data
    enriched = []
    for push in pushes:
        enriched.append(
            PushResponse(
                id=push.id,
                user_id=push.user_id,
                subscription_id=push.subscription_id,
                article_id=push.article_id,
                status=push.status,
                pushed_at=push.pushed_at,
                read_at=push.read_at,
                clicked_at=push.clicked_at,
                subscription_name=push.subscription.name,
                article_title=push.article.title,
                article_link=push.article.link,
            )
        )

    return PushListResponse(
        pushes=enriched,
        total=total,
        page=page,
        size=size
    )


@router.post("/pushes/{push_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_push_read(
    push_id: int,
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Mark a push as read."""
    repo = PushNotificationRepository(db)
    success = await repo.mark_push_read(push_id, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="推送记录不存在"
        )


@router.post("/pushes/{push_id}/click", status_code=status.HTTP_204_NO_CONTENT)
async def mark_push_clicked(
    push_id: int,
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Mark a push as clicked."""
    repo = PushNotificationRepository(db)
    success = await repo.mark_push_clicked(push_id, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="推送记录不存在"
        )


@router.get("/pushes/stats", response_model=PushStatsResponse)
async def get_push_stats(
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Get push statistics."""
    repo = PushNotificationRepository(db)

    from sqlalchemy import select, func
    from app.models.push_notification import NotificationPush

    # Get total pushes
    total_result = await db.execute(
        select(func.count())
        .select_from(NotificationPush)
        .where(NotificationPush.user_id == user_id)
    )
    total_pushes = total_result.scalar() or 0

    # Get unread pushes
    unread_pushes = await repo.get_unread_push_count(user_id)

    # Get clicked pushes
    clicked_result = await db.execute(
        select(func.count())
        .select_from(NotificationPush)
        .where(
            NotificationPush.user_id == user_id,
            NotificationPush.status == 'clicked'
        )
    )
    clicked_pushes = clicked_result.scalar() or 0

    return PushStatsResponse(
        total_pushes=total_pushes,
        unread_pushes=unread_pushes,
        clicked_pushes=clicked_pushes
    )


# ============ Web Push Endpoints ============

@router.post("/web-push/subscribe", response_model=WebPushSubscriptionResponse)
async def subscribe_web_push(
    data: WebPushSubscriptionCreate,
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Subscribe to Web Push notifications."""
    repo = PushNotificationRepository(db)

    subscription = await repo.create_web_push_subscription(
        user_id=user_id,
        endpoint=data.endpoint,
        p256dh=data.keys.get('p256dh', ''),
        auth=data.keys.get('auth', ''),
        user_agent=data.user_agent
    )

    return WebPushSubscriptionResponse(
        id=subscription.id,
        user_id=subscription.user_id,
        endpoint=subscription.endpoint,
        created_at=subscription.created_at
    )


@router.delete("/web-push/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_web_push(
    endpoint: str = Query(..., description="Push endpoint to unsubscribe"),
    user_id: int = CurrentUserId,
    db: AsyncSession = DbSession,
):
    """Unsubscribe from Web Push notifications."""
    repo = PushNotificationRepository(db)
    success = await repo.delete_web_push_subscription(user_id, endpoint)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Web Push 订阅不存在"
        )


@router.get("/web-push/public-key", response_model=VAPIDPublicKeyResponse)
async def get_vapid_public_key():
    """Get VAPID public key for Web Push."""
    public_key = getattr(settings, 'VAPID_PUBLIC_KEY', None)

    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Web Push 尚未配置"
        )

    return VAPIDPublicKeyResponse(public_key=public_key)
