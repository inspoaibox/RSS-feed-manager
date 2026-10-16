"""Owner-scoped channel and notification rule management."""

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.external_notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationRule,
    NotificationRuleChannel,
)
from app.models.feed import Feed
from app.schemas.external_notification import (
    ChannelCreate,
    ChannelResponse,
    ChannelUpdate,
    DeliveryList,
    RulePayload,
    RuleResponse,
)
from app.services.notification_sender import (
    SECRET_CONFIG_FIELDS,
    NotificationSendError,
    decrypt_channel_config,
    encrypt_channel_config,
    validate_channel_config,
)


class ExternalNotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def owned_channel(self, user_id: int, channel_id: int) -> NotificationChannel:
        channel = (
            await self.db.execute(
                select(NotificationChannel).where(
                    NotificationChannel.id == channel_id,
                    NotificationChannel.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if not channel:
            raise HTTPException(status_code=404, detail="通知频道不存在")
        return channel

    @staticmethod
    def channel_response(channel: NotificationChannel) -> ChannelResponse:
        try:
            config = decrypt_channel_config(channel.encrypted_config)
        except NotificationSendError:
            config = {}
        return ChannelResponse(
            id=channel.id,
            name=channel.name,
            provider=channel.provider,
            is_enabled=channel.is_enabled,
            created_at=channel.created_at,
            has_webhook=bool(config.get("webhook_url")),
            has_signing_secret=bool(config.get("signing_secret")),
            has_bot_token=bool(config.get("bot_token")),
            chat_id=config.get("chat_id"),
            message_thread_id=config.get("message_thread_id"),
            has_server_url=bool(config.get("server_url")),
            has_device_key=bool(config.get("device_key")),
            has_pushplus_token=bool(config.get("pushplus_token")),
            has_serverchan_send_key=bool(config.get("serverchan_send_key")),
            has_smtp_password=bool(config.get("smtp_password")),
            has_webhook_headers=bool(config.get("webhook_headers")),
            has_webhook_body=bool(config.get("webhook_body")),
            **{
                key: config.get(key)
                for key in (
                    "bark_group",
                    "pushplus_channel",
                    "pushplus_topic",
                    "pushplus_option",
                    "smtp_host",
                    "smtp_port",
                    "smtp_security",
                    "smtp_username",
                    "smtp_from",
                    "webhook_method",
                )
            },
            smtp_to=config.get("smtp_to") or [],
        )

    async def list_channels(self, user_id: int):
        channels = (
            (
                await self.db.execute(
                    select(NotificationChannel)
                    .where(NotificationChannel.user_id == user_id)
                    .order_by(NotificationChannel.id.desc())
                )
            )
            .scalars()
            .all()
        )
        return [self.channel_response(channel) for channel in channels]

    async def _check_name(self, user_id: int, name: str, exclude: int | None = None):
        if not name.strip():
            raise HTTPException(status_code=422, detail="频道名称不能为空")
        query = select(NotificationChannel.id).where(
            NotificationChannel.user_id == user_id,
            NotificationChannel.name == name.strip(),
        )
        if exclude is not None:
            query = query.where(NotificationChannel.id != exclude)
        if (await self.db.execute(query)).first():
            raise HTTPException(status_code=409, detail="已存在同名通知频道")

    @staticmethod
    def checked_config(provider: str, config: dict) -> dict:
        try:
            return validate_channel_config(provider, config)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def create_channel(self, user_id: int, data: ChannelCreate):
        await self._check_name(user_id, data.name)
        config = self.checked_config(data.provider, data.config.model_dump())
        channel = NotificationChannel(
            user_id=user_id,
            name=data.name.strip(),
            provider=data.provider,
            encrypted_config=encrypt_channel_config(config),
            is_enabled=data.is_enabled,
        )
        self.db.add(channel)
        await self.db.flush()
        return self.channel_response(channel)

    async def update_channel(self, user_id: int, channel_id: int, data: ChannelUpdate):
        channel = await self.owned_channel(user_id, channel_id)
        if data.name is not None:
            await self._check_name(user_id, data.name, channel_id)
            channel.name = data.name.strip()
        if data.config is not None:
            try:
                existing = decrypt_channel_config(channel.encrypted_config)
            except NotificationSendError:
                existing = {}
            new_config = data.config.model_dump(exclude_unset=True)
            # Blank secret inputs on an edit retain the stored value; null explicitly clears it.
            for key in SECRET_CONFIG_FIELDS:
                if new_config.get(key) == "":
                    new_config.pop(key)
            config = self.checked_config(channel.provider, {**existing, **new_config})
            channel.encrypted_config = encrypt_channel_config(config)
        if data.is_enabled is not None:
            channel.is_enabled = data.is_enabled
        await self.db.flush()
        return self.channel_response(channel)

    async def delete_channel(self, user_id: int, channel_id: int):
        channel = await self.owned_channel(user_id, channel_id)
        await self.db.delete(channel)
        await self.db.flush()

    async def owned_rule(self, user_id: int, rule_id: int):
        rule = (
            await self.db.execute(
                select(NotificationRule).where(
                    NotificationRule.id == rule_id,
                    NotificationRule.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if not rule:
            raise HTTPException(status_code=404, detail="推送规则不存在")
        return rule

    async def rule_response(self, rule: NotificationRule):
        model = Feed if rule.source_type == "feed" else Category
        source = (
            await self.db.execute(
                select(model).where(
                    model.id == rule.source_id,
                    model.user_id == rule.user_id,
                )
            )
        ).scalar_one_or_none()
        channels = (
            (
                await self.db.execute(
                    select(NotificationRuleChannel.channel_id)
                    .join(NotificationChannel)
                    .where(
                        NotificationRuleChannel.rule_id == rule.id,
                        NotificationChannel.user_id == rule.user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        return RuleResponse(
            id=rule.id,
            name=rule.name,
            source_type=rule.source_type,
            source_id=rule.source_id,
            channel_ids=list(channels),
            source_name=source.title
            if isinstance(source, Feed)
            else source.name
            if source
            else None,
            is_enabled=rule.is_enabled,
        )

    async def list_rules(self, user_id: int):
        rules = (
            (
                await self.db.execute(
                    select(NotificationRule)
                    .where(NotificationRule.user_id == user_id)
                    .order_by(NotificationRule.id.desc())
                )
            )
            .scalars()
            .all()
        )
        return [await self.rule_response(rule) for rule in rules]

    async def save_rule(self, user_id: int, data: RulePayload, rule_id: int | None = None):
        rule = await self.owned_rule(user_id, rule_id) if rule_id is not None else None
        model = Feed if data.source_type == "feed" else Category
        source = (
            await self.db.execute(
                select(model.id).where(
                    model.id == data.source_id,
                    model.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        channel_ids = set(data.channel_ids)
        owned_ids = set(
            (
                await self.db.execute(
                    select(NotificationChannel.id).where(
                        NotificationChannel.id.in_(channel_ids),
                        NotificationChannel.user_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        if source is None or owned_ids != channel_ids:
            raise HTTPException(status_code=404, detail="来源或通知频道不存在")
        if not data.name.strip():
            raise HTTPException(status_code=422, detail="规则名称不能为空")
        duplicate = select(NotificationRule.id).where(
            NotificationRule.user_id == user_id,
            NotificationRule.name == data.name.strip(),
            NotificationRule.source_type == data.source_type,
            NotificationRule.source_id == data.source_id,
        )
        if rule_id is not None:
            duplicate = duplicate.where(NotificationRule.id != rule_id)
        if (await self.db.execute(duplicate)).first():
            raise HTTPException(
                status_code=409, detail="该来源已存在同名规则，请编辑原规则或使用其他名称"
            )
        if rule is None:
            rule = NotificationRule(user_id=user_id)
            self.db.add(rule)
        rule.name, rule.source_type, rule.source_id = (
            data.name.strip(),
            data.source_type,
            data.source_id,
        )
        rule.is_enabled = data.is_enabled
        await self.db.flush()
        await self.db.execute(
            delete(NotificationRuleChannel).where(NotificationRuleChannel.rule_id == rule.id)
        )
        self.db.add_all(
            [
                NotificationRuleChannel(rule_id=rule.id, channel_id=channel_id)
                for channel_id in channel_ids
            ]
        )
        await self.db.flush()
        return await self.rule_response(rule)

    async def delete_rule(self, user_id: int, rule_id: int):
        await self.db.delete(await self.owned_rule(user_id, rule_id))
        await self.db.flush()

    async def deliveries(self, user_id: int, page: int, size: int, status: str | None):
        query = select(NotificationDelivery).where(NotificationDelivery.user_id == user_id)
        if status:
            query = query.where(NotificationDelivery.status == status)
        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar()
        items = (
            (
                await self.db.execute(
                    query.order_by(NotificationDelivery.id.desc())
                    .offset((page - 1) * size)
                    .limit(size)
                )
            )
            .scalars()
            .all()
        )
        return DeliveryList(items=items, total=total or 0, page=page, page_size=size)
