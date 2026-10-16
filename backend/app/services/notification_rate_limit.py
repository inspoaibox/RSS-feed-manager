"""Database-backed per-channel pacing shared by workers and test sends."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update

from app.models.external_notification import NotificationChannel


def channel_send_interval(provider: str) -> float:
    # WeCom and Telegram groups allow 20/minute; leave a small margin at the boundary.
    return {"wecom": 3.1, "telegram": 3.1, "feishu": 0.7}.get(provider, 1.0)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def reserve_channel_send(
    db,
    channel_id: int,
    user_id: int,
    provider: str,
    now: datetime,
    *,
    allow_disabled: bool = False,
    clock=None,
):
    # Acquire the row/write lock before sampling time; a slow dispatcher must not leave
    # a sender with a timestamp from before it waited for the database lock.
    db.execute(
        update(NotificationChannel)
        .where(
            NotificationChannel.id == channel_id,
            NotificationChannel.user_id == user_id,
            or_(NotificationChannel.is_enabled.is_(True), allow_disabled),
        )
        .values(
            next_send_at=NotificationChannel.next_send_at, updated_at=NotificationChannel.updated_at
        )
        .execution_options(synchronize_session=False)
    )
    if clock is not None:
        now = clock()
    now = as_utc(now)
    next_slot = now + timedelta(seconds=channel_send_interval(provider))
    result = db.execute(
        update(NotificationChannel)
        .where(
            NotificationChannel.id == channel_id,
            NotificationChannel.user_id == user_id,
            or_(NotificationChannel.is_enabled.is_(True), allow_disabled),
            or_(
                NotificationChannel.next_send_at.is_(None), NotificationChannel.next_send_at <= now
            ),
        )
        .values(next_send_at=next_slot)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 1:
        return None
    blocked_until = db.execute(
        select(NotificationChannel.next_send_at).where(NotificationChannel.id == channel_id)
    ).scalar_one_or_none()
    return as_utc(blocked_until) if blocked_until else next_slot


def pause_channel(db, channel_id: int | None, until: datetime) -> None:
    if channel_id is None:
        return
    until = as_utc(until)
    db.execute(
        update(NotificationChannel)
        .where(
            NotificationChannel.id == channel_id,
            or_(
                NotificationChannel.next_send_at.is_(None), NotificationChannel.next_send_at < until
            ),
        )
        .values(next_send_at=until)
        .execution_options(synchronize_session=False)
    )
