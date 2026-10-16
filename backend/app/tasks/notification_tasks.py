"""Dispatch the durable notification outbox with atomic claims and bounded retry."""

import asyncio
from datetime import timedelta

from celery import shared_task
from sqlalchemy import func, or_, select, update

from app.core.clock import utc_now
from app.models.external_notification import NotificationChannel, NotificationDelivery
from app.models.user import User
from app.services.notification_rate_limit import (
    as_utc,
    channel_send_interval,
    pause_channel,
    reserve_channel_send,
)
from app.services.notification_sender import (
    NotificationSendError,
    decrypt_channel_config,
    send_notification,
)


def get_session():
    from app.tasks.feed_tasks import get_sync_session

    return get_sync_session()


def claim_delivery(db, delivery_id: int) -> dict | None:
    now = as_utc(utc_now())
    result = db.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.id == delivery_id,
            NotificationDelivery.failure_attempts < 3,
            NotificationDelivery.status.in_(["queued", "pending"]),
            or_(
                NotificationDelivery.next_attempt_at.is_(None),
                NotificationDelivery.next_attempt_at <= now,
            ),
        )
        .values(status="sending", claimed_at=now)
        .execution_options(synchronize_session="fetch")
    )
    db.commit()
    if result.rowcount != 1:
        return None
    delivery = db.get(NotificationDelivery, delivery_id)
    channel = db.get(NotificationChannel, delivery.channel_id) if delivery.channel_id else None
    user = db.get(User, delivery.user_id)
    if (
        not channel
        or channel.user_id != delivery.user_id
        or not channel.is_enabled
        or not user
        or not user.is_active
    ):
        delivery.status, delivery.error = "skipped", "频道已停用、删除或账户不可用"
        db.commit()
        return None
    try:
        config = decrypt_channel_config(channel.encrypted_config)
    except NotificationSendError as exc:
        delivery.status, delivery.error = "failed", str(exc)
        db.commit()
        return None
    blocked_until = reserve_channel_send(
        db,
        channel.id,
        delivery.user_id,
        channel.provider,
        now,
        clock=utc_now,
    )
    if blocked_until:
        delivery.status, delivery.next_attempt_at, delivery.claimed_at = (
            "pending",
            blocked_until,
            None,
        )
        db.commit()
        return None
    delivery.attempts += 1
    delivery.claimed_at = as_utc(utc_now())
    delivery.next_attempt_at = None
    db.commit()
    return {
        "provider": channel.provider,
        "config": config,
        "message": delivery.message,
        "title": delivery.article_title,
    }


def finish_delivery(db, delivery_id: int, failure: NotificationSendError | None):
    delivery = db.get(NotificationDelivery, delivery_id)
    if not delivery or delivery.status != "sending":
        return
    delivery.claimed_at = None
    if failure is None:
        delivery.status, delivery.sent_at, delivery.error = "sent", utc_now(), None
        delivery.next_attempt_at = None
    else:
        delivery.error = str(failure)[:500]
        if not failure.rate_limited:
            delivery.failure_attempts += 1
        retry = failure.retryable and delivery.failure_attempts < 3
        delivery.status = "pending" if retry else "failed"
        delay = (
            failure.retry_after
            if failure.rate_limited
            else min(300, failure.retry_after * 2 ** max(0, delivery.failure_attempts - 1))
        )
        delivery.next_attempt_at = as_utc(utc_now()) + timedelta(seconds=delay) if retry else None
        if failure.rate_limited and delivery.next_attempt_at:
            pause_channel(db, delivery.channel_id, delivery.next_attempt_at)
    db.commit()


@shared_task(name="app.tasks.notification_tasks.send_delivery", soft_time_limit=30, time_limit=45)
def send_delivery(delivery_id: int):
    with get_session() as db:
        job = claim_delivery(db, delivery_id)
    if not job:
        return {"delivery_id": delivery_id, "skipped": True}
    failure = None
    try:
        asyncio.run(
            send_notification(job["provider"], job["config"], job["message"], title=job["title"])
        )
    except NotificationSendError as exc:
        failure = exc
    except Exception:
        # A crashed/timed-out call may already have reached the provider. Require manual retry.
        failure = NotificationSendError("发送结果未知，请确认频道是否收到消息后再重试")
    with get_session() as db:
        finish_delivery(db, delivery_id, failure)
    return {"delivery_id": delivery_id, "success": failure is None}


def queue_pending_deliveries(db) -> list[int]:
    now = as_utc(utc_now())
    db.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.status == "sending",
            NotificationDelivery.claimed_at < now - timedelta(minutes=2),
        )
        .values(status="failed", error="发送进程中断，结果未知，请确认后手动重试", claimed_at=None)
    )
    db.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.status == "queued",
            func.coalesce(NotificationDelivery.next_attempt_at, NotificationDelivery.claimed_at)
            < now - timedelta(minutes=5),
        )
        .values(status="pending", claimed_at=None)
    )
    due = or_(
        NotificationDelivery.next_attempt_at.is_(None), NotificationDelivery.next_attempt_at <= now
    )
    candidates = list(
        db.execute(
            select(NotificationDelivery.id)
            .where(
                NotificationDelivery.status == "pending",
                NotificationDelivery.failure_attempts < 3,
                due,
            )
            .order_by(NotificationDelivery.id)
            .limit(100)
        ).scalars()
    )
    ids = []
    if candidates:
        deliveries = list(
            db.execute(
                select(NotificationDelivery)
                .where(NotificationDelivery.id.in_(candidates))
                .order_by(NotificationDelivery.id)
            ).scalars()
        )
        channel_ids = {delivery.channel_id for delivery in deliveries if delivery.channel_id}
        # Lock in a stable order so overlapping dispatchers cannot reserve the same channel slots.
        channels = {
            channel.id: channel
            for channel in db.execute(
                select(NotificationChannel)
                .where(NotificationChannel.id.in_(channel_ids))
                .order_by(NotificationChannel.id)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            ).scalars()
        }
        latest = dict(
            db.execute(
                select(
                    NotificationDelivery.channel_id, func.max(NotificationDelivery.next_attempt_at)
                )
                .where(
                    NotificationDelivery.channel_id.in_(channel_ids),
                    NotificationDelivery.status.in_(["queued", "sending"]),
                )
                .group_by(NotificationDelivery.channel_id)
            ).all()
        )
        planned = {}
        for delivery in deliveries:
            channel = channels.get(delivery.channel_id)
            if (
                delivery.channel_id
                and not channel
                and db.get(NotificationChannel, delivery.channel_id)
            ):
                # A live channel locked by another dispatcher will be picked up next time.
                continue
            interval = channel_send_interval(channel.provider) + 0.2 if channel else 0
            if delivery.channel_id not in planned:
                bounds = [now]
                if channel and channel.next_send_at:
                    bounds.append(as_utc(channel.next_send_at))
                if latest.get(delivery.channel_id):
                    bounds.append(as_utc(latest[delivery.channel_id]) + timedelta(seconds=interval))
                planned[delivery.channel_id] = max(bounds)
            scheduled_at = planned[delivery.channel_id]
            claimed = db.execute(
                update(NotificationDelivery)
                .where(
                    NotificationDelivery.id == delivery.id,
                    NotificationDelivery.status == "pending",
                    due,
                )
                .values(status="queued", claimed_at=now, next_attempt_at=scheduled_at)
                .returning(NotificationDelivery.id)
                .execution_options(synchronize_session="fetch")
            ).scalar_one_or_none()
            if claimed is not None:
                ids.append(claimed)
                planned[delivery.channel_id] = scheduled_at + timedelta(seconds=interval)
    db.commit()
    return ids


@shared_task(name="app.tasks.notification_tasks.dispatch_pending")
def dispatch_pending():
    from app.tasks.celery_app import celery_app

    with get_session() as db:
        ids = queue_pending_deliveries(db)
        schedule = (
            dict(
                db.execute(
                    select(NotificationDelivery.id, NotificationDelivery.next_attempt_at).where(
                        NotificationDelivery.id.in_(ids)
                    )
                ).all()
            )
            if ids
            else {}
        )
    for position, delivery_id in enumerate(ids):
        try:
            celery_app.send_task(
                "app.tasks.notification_tasks.send_delivery",
                args=[delivery_id],
                queue="celery",
                retry=False,
                countdown=max(
                    0, (as_utc(schedule[delivery_id]) - as_utc(utc_now())).total_seconds()
                ),
            )
        except Exception:
            # Return unpublished rows to pending. Already-claimed rows are never reset.
            with get_session() as db:
                db.execute(
                    update(NotificationDelivery)
                    .where(
                        NotificationDelivery.id.in_(ids[position:]),
                        NotificationDelivery.status == "queued",
                    )
                    .values(
                        status="pending", claimed_at=None, error="通知队列暂时不可用，稍后自动重试"
                    )
                )
                db.commit()
            return {"dispatched": position, "queue_unavailable": True}
    return {"dispatched": len(ids)}
