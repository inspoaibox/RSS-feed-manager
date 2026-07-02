import pytest
from sqlalchemy import select

from app.models.custom_rule import CustomRule
from app.models.feed import Feed
from app.models.user import User
from app.schemas.feed import FeedCreate
from app.services.custom_rule_service import CustomRuleService
from app.services.feed_service import FeedService


@pytest.mark.asyncio
async def test_create_whmcs_monitor_keeps_feed_when_initial_fetch_fails(db_session, monkeypatch):
    user = User(
        username="whmcs_user",
        email="whmcs_user@example.com",
        password_hash="x",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    async def fail_execute_rule(self, rule):
        raise RuntimeError("temporary fetch failure")

    monkeypatch.setattr(CustomRuleService, "execute_rule", fail_execute_rule)

    result = await FeedService(db_session).create(
        user.id,
        FeedCreate(
            url="https://example.com/index.php?rp=/store/vps/example-vps",
            source_type="whmcs",
            browser_engine="http",
            fetch_interval=300,
        ),
    )

    rule = (
        await db_session.execute(
            select(CustomRule).where(CustomRule.feed_id == result.id)
        )
    ).scalar_one()
    feed = (
        await db_session.execute(select(Feed).where(Feed.id == result.id))
    ).scalar_one()

    assert result.article_count == 0
    assert rule.rule_type == "whmcs"
    assert rule.last_error == "temporary fetch failure"
    assert rule.error_count == 1
    assert feed.last_error == "temporary fetch failure"
    assert feed.error_count == 1
