"""Per-user external notification configuration and delivery history."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.core.clock import utc_now
from app.models.external_notification import NotificationDelivery
from app.schemas.external_notification import (
    ChannelCreate,
    ChannelResponse,
    ChannelUpdate,
    DeliveryList,
    DeliveryStatus,
    RulePayload,
    RuleResponse,
)
from app.services.external_notification_service import ExternalNotificationService
from app.services.notification_rate_limit import as_utc, pause_channel, reserve_channel_send
from app.services.notification_sender import (
    NotificationSendError,
    decrypt_channel_config,
    send_notification,
)


class NotificationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # FastAPI otherwise includes invalid credential inputs in validation responses.
                detail = [
                    {key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()
                ]
                raise HTTPException(status_code=422, detail=detail) from None

        return safe_handler


router = APIRouter(route_class=NotificationRoute)


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(user_id: CurrentUserId, db: DbSession):
    return await ExternalNotificationService(db).list_channels(user_id)


@router.post("/channels", response_model=ChannelResponse, status_code=201)
async def create_channel(data: ChannelCreate, user_id: CurrentUserId, db: DbSession):
    return await ExternalNotificationService(db).create_channel(user_id, data)


@router.put("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: int, data: ChannelUpdate, user_id: CurrentUserId, db: DbSession
):
    return await ExternalNotificationService(db).update_channel(user_id, channel_id, data)


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(channel_id: int, user_id: CurrentUserId, db: DbSession):
    await ExternalNotificationService(db).delete_channel(user_id, channel_id)


@router.post("/channels/{channel_id}/test")
async def test_channel(channel_id: int, user_id: CurrentUserId, db: DbSession):
    channel = await ExternalNotificationService(db).owned_channel(user_id, channel_id)
    delivery = NotificationDelivery(
        user_id=user_id,
        channel_id=channel.id,
        channel_name=channel.name,
        provider=channel.provider,
        article_title="测试通知",
        message="🔔 RSS 通知测试\n频道配置成功。",
        is_test=True,
        status="sending",
        attempts=1,
    )
    db.add(delivery)
    await db.flush()
    try:
        config = decrypt_channel_config(channel.encrypted_config)
        now = as_utc(utc_now())
        blocked_until = await db.run_sync(
            lambda session: reserve_channel_send(
                session,
                channel.id,
                user_id,
                channel.provider,
                now,
                allow_disabled=True,
                clock=utc_now,
            )
        )
        if blocked_until:
            delivery.attempts = 0
            raise NotificationSendError("频道发送频率受限，请稍后再次测试")
        # Commit the slot before network I/O; other workers must see the reservation immediately.
        delivery.claimed_at = as_utc(utc_now())
        await db.commit()
        await send_notification(
            channel.provider, config, delivery.message, title=delivery.article_title
        )
        delivery.status, delivery.sent_at = "sent", utc_now()
    except NotificationSendError as exc:
        delivery.status, delivery.error = "failed", str(exc)
        if exc.rate_limited:
            cooldown_until = as_utc(utc_now()) + timedelta(seconds=exc.retry_after)
            await db.run_sync(
                lambda session: pause_channel(
                    session,
                    channel.id,
                    cooldown_until,
                )
            )
    delivery.claimed_at = None
    await db.flush()
    return {
        "success": delivery.status == "sent",
        "message": delivery.error or "测试消息已提交，请在目标应用中确认接收",
    }


@router.get("/rules", response_model=list[RuleResponse])
async def list_rules(user_id: CurrentUserId, db: DbSession):
    return await ExternalNotificationService(db).list_rules(user_id)


@router.post("/rules", response_model=RuleResponse, status_code=201)
async def create_rule(data: RulePayload, user_id: CurrentUserId, db: DbSession):
    return await ExternalNotificationService(db).save_rule(user_id, data)


@router.put("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: int, data: RulePayload, user_id: CurrentUserId, db: DbSession):
    return await ExternalNotificationService(db).save_rule(user_id, data, rule_id)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, user_id: CurrentUserId, db: DbSession):
    await ExternalNotificationService(db).delete_rule(user_id, rule_id)


@router.get("/deliveries", response_model=DeliveryList)
async def list_deliveries(
    user_id: CurrentUserId,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: DeliveryStatus | None = None,
):
    return await ExternalNotificationService(db).deliveries(user_id, page, page_size, status)


@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery(delivery_id: int, user_id: CurrentUserId, db: DbSession):
    delivery = (
        await db.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.id == delivery_id,
                NotificationDelivery.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not delivery:
        raise HTTPException(status_code=404, detail="发送记录不存在")
    if delivery.status != "failed" or delivery.is_test:
        raise HTTPException(status_code=409, detail="仅失败的文章通知可以重新发送")
    if delivery.channel_id is None:
        raise HTTPException(status_code=409, detail="通知频道已删除")
    channel = await ExternalNotificationService(db).owned_channel(user_id, delivery.channel_id)
    if not channel.is_enabled:
        raise HTTPException(status_code=409, detail="通知频道已停用")
    delivery.status, delivery.attempts, delivery.error = "pending", 0, None
    delivery.failure_attempts = 0
    delivery.next_attempt_at, delivery.claimed_at = None, None
    await db.flush()
    return {"success": True, "message": "通知已加入重试队列"}
