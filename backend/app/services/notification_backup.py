"""Portable owner-scoped notification settings inside encrypted user backups."""

from sqlalchemy import select

from app.models.external_notification import NotificationChannel, NotificationRule
from app.schemas.external_notification import ChannelCreate, ChannelUpdate, RestoredRulePayload
from app.services.external_notification_service import ExternalNotificationService
from app.services.notification_sender import decrypt_channel_config


async def export_notification_settings(db, user_id: int) -> dict:
    service = ExternalNotificationService(db)
    channels = list(
        (
            await db.execute(
                select(NotificationChannel).where(
                    NotificationChannel.user_id == user_id,
                )
            )
        ).scalars()
    )
    channel_names = {channel.id: channel.name for channel in channels}
    rules = await service.list_rules(user_id)
    from app.models.category import Category
    from app.models.feed import Feed

    exported_rules = []
    for rule in rules:
        model = Feed if rule.source_type == "feed" else Category
        source = (
            await db.execute(
                select(model).where(model.id == rule.source_id, model.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not source:
            continue
        exported_rules.append(
            {
                "name": rule.name,
                "source_type": rule.source_type,
                "source": source.url if rule.source_type == "feed" else source.name,
                "channel_names": [
                    channel_names[channel_id]
                    for channel_id in rule.channel_ids
                    if channel_id in channel_names
                ],
                "is_enabled": rule.is_enabled,
            }
        )
    # The containing backup is AES-GCM encrypted with the user's backup password.
    return {
        "notification_channels": [
            {
                "name": channel.name,
                "provider": channel.provider,
                "config": decrypt_channel_config(channel.encrypted_config),
                "is_enabled": channel.is_enabled,
            }
            for channel in channels
        ],
        "notification_rules": exported_rules,
    }


async def import_notification_settings(db, user_id: int, data: dict) -> list[str]:
    service = ExternalNotificationService(db)
    errors = []
    for values in data.get("notification_channels", []):
        try:
            async with db.begin_nested():
                payload = ChannelCreate.model_validate(values)
                existing = (
                    await db.execute(
                        select(NotificationChannel).where(
                            NotificationChannel.user_id == user_id,
                            NotificationChannel.name == payload.name.strip(),
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    if existing.provider != payload.provider:
                        raise ValueError("同名频道的通知应用不同")
                    await service.update_channel(
                        user_id,
                        existing.id,
                        ChannelUpdate(
                            name=payload.name,
                            config=payload.config,
                            is_enabled=payload.is_enabled,
                        ),
                    )
                else:
                    await service.create_channel(user_id, payload)
        except Exception:
            # Validation messages may include credential values. Report only safe text.
            errors.append("一个通知频道导入失败，请检查名称、凭据或应用类型")
    from app.models.category import Category
    from app.models.feed import Feed

    for values in data.get("notification_rules", []):
        try:
            async with db.begin_nested():
                names = values.get("channel_names")
                if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
                    raise ValueError("频道名称列表无效")
                model = Feed if values.get("source_type") == "feed" else Category
                key = Feed.url if model is Feed else Category.name
                source = (
                    await db.execute(
                        select(model).where(model.user_id == user_id, key == values.get("source"))
                    )
                ).scalar_one_or_none()
                channels = list(
                    (
                        await db.execute(
                            select(NotificationChannel.id).where(
                                NotificationChannel.user_id == user_id,
                                NotificationChannel.name.in_(names),
                            )
                        )
                    ).scalars()
                )
                if not source or len(channels) != len(set(names)):
                    raise ValueError("来源或频道不存在")
                payload = RestoredRulePayload(
                    name=values.get("name"),
                    source_type=values.get("source_type"),
                    source_id=source.id,
                    channel_ids=channels,
                    is_enabled=values.get("is_enabled", True),
                )
                existing = (
                    await db.execute(
                        select(NotificationRule).where(
                            NotificationRule.user_id == user_id,
                            NotificationRule.name == payload.name,
                            NotificationRule.source_type == payload.source_type,
                            NotificationRule.source_id == payload.source_id,
                        )
                    )
                ).scalar_one_or_none()
                await service.save_rule(user_id, payload, existing.id if existing else None)
        except Exception:
            errors.append("一个通知规则导入失败，请检查来源和关联频道")
    return errors
