"""Regression tests count actual attempted provider calls using local substitutes."""

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.security import create_access_token
from app.models.ai_provider import AIModel, AIProvider
from app.models.ai_usage import AIUsage
from app.models.article import Article
from app.models.feed import Feed
from app.models.user import User
from app.services.ai_client import AIClientError, OpenAIClient
from app.services.ai_translation_service import (
    select_translation_body_input,
    translate_text_with_chunking,
)
from app.services.ai_usage_service import usage_fields
from app.tasks import feed_tasks


def reply(text="译文", finish="stop", usage=True):
    result = {"choices": [{"message": {"content": text}, "finish_reason": finish}]}
    if usage:
        result["usage"] = {
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "total_tokens": 30,
            "prompt_tokens_details": {"cached_tokens": 5},
            "completion_tokens_details": {"reasoning_tokens": 8},
        }
    return result


@pytest.fixture
def local_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'translation.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(feed_tasks, "get_sync_session", factory)
    with factory() as db:
        user = User(username="translator", email="translator@example.test", password_hash="unused")
        db.add(user)
        db.flush()
        provider = AIProvider(
            user_id=user.id,
            name="Local fake",
            type="openai_compatible",
            base_url="https://example.test/v1",
            api_key="local-only",
        )
        db.add(provider)
        db.flush()
        model = AIModel(
            provider_id=provider.id, model_id="fake-model", name="Fake", is_default=True
        )
        feed = Feed(
            user_id=user.id,
            url="https://example.test/rss",
            title="Feed",
            translate_method="ai",
            target_language="zh-CN",
            translate_title=True,
            translate_content=True,
        )
        db.add_all([model, feed])
        db.flush()
        article = Article(
            feed_id=feed.id,
            guid="one",
            title="Original title",
            content="Body",
            translation_status="queued",
        )
        db.add(article)
        db.commit()
        ids = dict(
            user=user.id, provider=provider.id, model=model.id, feed=feed.id, article=article.id
        )
    yield factory, ids
    engine.dispose()


def run(ids, full=False):
    return feed_tasks._run_article_translation(ids["article"], "zh-CN", full, None)


@pytest.mark.parametrize(
    "html",
    [
        '<script>secret()</script><img src="data:image/png;base64,AAAA">',
        "<style>lots of css</style><noscript>hidden</noscript><svg><text>icon</text></svg>",
    ],
)
def test_non_text_markup_is_never_sent_as_fallback(html):
    assert select_translation_body_input(None, html) == ""
    assert select_translation_body_input(html, "<p>Visible text</p>") == "Visible text"


@pytest.mark.asyncio
async def test_json_prompt_is_literal_and_request_has_explicit_output_cap(monkeypatch):
    sent = []

    async def request(self, endpoint, data):
        sent.append(data)
        return reply()

    monkeypatch.setattr(OpenAIClient, "_request", request)
    client = OpenAIClient(
        "fake", model="model", token_limit_parameter="max_completion_tokens", max_output_tokens=512
    )
    await client.translate(
        "Hello", "zh-CN", 'Translate to {target_language}, format {"text":"..."}'
    )
    assert sent[0]["messages"][0]["content"] == 'Translate to zh-CN, format {"text":"..."}'
    assert sent[0]["messages"][1]["content"] == "Hello"
    assert sent[0]["max_completion_tokens"] == 512
    assert "temperature" not in sent[0]
    assert len(sent[0]["messages"]) == 2


@pytest.mark.asyncio
async def test_short_truncation_does_not_resend_identical_input(monkeypatch):
    sent = []

    async def request(self, endpoint, data):
        sent.append(data)
        return reply("", "length")

    monkeypatch.setattr(OpenAIClient, "_request", request)
    with pytest.raises(AIClientError, match="truncated"):
        await translate_text_with_chunking(OpenAIClient("fake"), "Small input", "zh-CN")
    assert len(sent) == 1


def test_body_only_completion_is_not_queued_again(local_db, monkeypatch):
    factory, ids = local_db
    sent = []

    async def request(self, endpoint, data):
        sent.append(data["messages"][1]["content"])
        return reply()

    monkeypatch.setattr(OpenAIClient, "_request", request)
    with factory() as db:
        db.get(Feed, ids["feed"]).translate_title = False
        db.commit()
    assert run(ids)["success"]
    with factory() as db:
        article, feed = db.get(Article, ids["article"]), db.get(Feed, ids["feed"])
        assert not feed_tasks._mark_article_translation_queued(db, article, feed)
    assert run(ids)["skipped"] == "already translated"
    assert sent == ["Body"]


def test_fill_body_keeps_previously_translated_title(local_db, monkeypatch):
    factory, ids = local_db
    sent = []

    async def request(self, endpoint, data):
        sent.append(data["messages"][1]["content"])
        return reply("new body")

    monkeypatch.setattr(OpenAIClient, "_request", request)
    with factory() as db:
        db.get(Article, ids["article"]).translation = json.dumps(
            {"title": "已有标题", "content": ""}
        )
        db.get(Feed, ids["feed"]).translate_content = False
        db.commit()
    assert run(ids, full=True)["success"]
    assert sent == ["Body"]
    with factory() as db:
        assert json.loads(db.get(Article, ids["article"]).translation)["title"] == "已有标题"


def test_retry_reuses_title_and_successful_body_chunks(local_db, monkeypatch):
    factory, ids = local_db
    sent = []

    async def request(self, endpoint, data):
        text = data["messages"][1]["content"]
        sent.append(text)
        if text.startswith("B") and sent.count(text) == 1:
            raise AIClientError("Rate limited", status_code=429)
        return reply("translated " + text[:3])

    monkeypatch.setattr(OpenAIClient, "_request", request)
    with factory() as db:
        db.get(Article, ids["article"]).content = "A" * 3500 + "B" * 3500
        db.commit()
    assert not run(ids)["success"]
    assert run(ids)["success"]
    assert [len(t) for t in sent] == [14, 3500, 3500, 3500]
    assert sent.count("A" * 3500) == 1
    with factory() as db:
        receipts = db.scalars(select(AIUsage).order_by(AIUsage.id)).all()
        assert [r.status for r in receipts] == ["succeeded", "succeeded", "rejected", "succeeded"]
        assert sum(r.budget_tokens for r in receipts) == 90


def test_unknown_outcome_blocks_automatic_resend(local_db, monkeypatch):
    factory, ids = local_db
    sent = []

    async def request(self, endpoint, data):
        sent.append(data)
        raise AIClientError("Read timeout")

    monkeypatch.setattr(OpenAIClient, "_request", request)
    assert not run(ids)["success"]
    assert not run(ids)["success"]
    assert len(sent) == 1
    with factory() as db:
        receipt = db.scalar(select(AIUsage))
        assert receipt.status == "unknown" and receipt.total_tokens is None
        assert receipt.budget_tokens > 0


def test_truncated_parent_and_successful_children_are_not_resent(local_db, monkeypatch):
    factory, ids = local_db
    sent = []

    async def request(self, endpoint, data):
        text = data["messages"][1]["content"]
        sent.append(text)
        if len(text) > 2000:
            return reply("partial", "length")
        if text.startswith("B") and sent.count(text) == 1:
            raise AIClientError("Rate limited", status_code=429)
        return reply("done")

    monkeypatch.setattr(OpenAIClient, "_request", request)
    with factory() as db:
        db.get(Feed, ids["feed"]).translate_title = False
        db.get(Article, ids["article"]).content = "A" * 1750 + "B" * 1750
        db.commit()
    assert not run(ids)["success"]
    assert run(ids)["success"]
    assert [len(t) for t in sent] == [3500, 1750, 1750, 1750]


@pytest.mark.parametrize("kind", ["provider", "model"])
def test_inactive_channel_or_model_never_calls_provider(local_db, monkeypatch, kind):
    factory, ids = local_db

    async def forbidden(*args, **kwargs):
        pytest.fail("Disabled model was contacted")

    monkeypatch.setattr(OpenAIClient, "_request", forbidden)
    with factory() as db:
        db.get(AIProvider if kind == "provider" else AIModel, ids[kind]).is_active = False
        db.commit()
    assert not run(ids)["success"]


def test_budget_prevents_sending_and_unknown_usage_is_not_zero(local_db, monkeypatch):
    factory, ids = local_db
    sent = []

    async def request(self, endpoint, data):
        sent.append(data)
        return reply(usage=False)

    monkeypatch.setattr(OpenAIClient, "_request", request)
    with factory() as db:
        db.get(User, ids["user"]).translation_monthly_token_limit = 5000
        db.commit()
    assert not run(ids)["success"]  # title consumes a reservation; body is blocked
    assert len(sent) == 1
    with factory() as db:
        row = db.scalar(select(AIUsage))
        assert row.total_tokens is None and row.budget_tokens > 4096


def test_usage_breakdowns_are_not_double_counted():
    assert usage_fields(reply())["total_tokens"] == 30
    gemini = usage_fields(
        {
            "usageMetadata": {
                "promptTokenCount": 20,
                "candidatesTokenCount": 10,
                "thoughtsTokenCount": 5,
                "totalTokenCount": 35,
            }
        }
    )
    assert gemini["output_tokens"] == 15 and gemini["total_tokens"] == 35


async def api_account(db):
    user = User(username="api-cost", email="api-cost@example.test", password_hash="unused")
    db.add(user)
    await db.flush()
    provider = AIProvider(
        user_id=user.id,
        name="Test",
        type="openai_compatible",
        api_key="fake",
        base_url="https://example.test/v1",
    )
    db.add(provider)
    await db.flush()
    model = AIModel(provider_id=provider.id, model_id="fake", name="Fake", is_default=True)
    feed = Feed(
        user_id=user.id,
        url="https://example.test/rss",
        title="Feed",
        translate_method="ai",
        target_language="zh-CN",
    )
    db.add_all([model, feed])
    await db.flush()
    article = Article(feed_id=feed.id, guid="one", title="Title", content="Body")
    db.add(article)
    await db.commit()
    token = create_access_token({"sub": str(user.id), "token_version": user.token_version})
    return user, provider, model, article, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_legacy_and_current_endpoints_share_queue(client, db_session, monkeypatch):
    _, _, _, article, headers = await api_account(db_session)
    sent = []
    monkeypatch.setattr(
        feed_tasks,
        "dispatch_article_translation",
        lambda *args, **kwargs: (sent.append((args, kwargs)) or True, None),
    )
    response = await client.post(
        f"/api/v1/ai/translate/{article.id}", headers=headers, json={"target_language": "zh-CN"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["translation_status"] == "queued"
    response = await client.post(f"/api/v1/articles/{article.id}/translate", headers=headers)
    assert response.status_code == 200 and len(sent) == 1


@pytest.mark.asyncio
async def test_model_test_records_usage_and_settings_validate(client, db_session, monkeypatch):
    _, _, model, _, headers = await api_account(db_session)
    sent = []

    async def request(self, endpoint, data):
        sent.append(data)
        return reply("你好")

    monkeypatch.setattr(OpenAIClient, "_request", request)
    response = await client.post(f"/api/v1/ai/models/{model.id}/test-translation", headers=headers)
    assert response.status_code == 200 and response.json()["success"], response.text
    assert sent[0]["max_tokens"] == 256
    usage = await client.get("/api/v1/ai/translation-usage", headers=headers)
    assert usage.json()["reported_tokens"] == 30
    assert "result_text" not in usage.json()["items"][0]
    response = await client.put(
        "/api/v1/ai/settings", headers=headers, json={"translation_monthly_token_limit": -1}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_explicit_unknown_retry_keeps_receipt_and_budget(client, db_session, monkeypatch):
    user, provider, _, article, headers = await api_account(db_session)
    article.translation_status = "failed"
    receipt = AIUsage(
        user_id=user.id,
        provider_id=provider.id,
        article_id=article.id,
        model="fake",
        operation="translation",
        cache_key="x" * 64,
        input_key="x" * 64,
        status="unknown",
        estimated_input_tokens=100,
        max_output_tokens=128,
        budget_tokens=228,
    )
    db_session.add(receipt)
    await db_session.commit()
    monkeypatch.setattr(
        feed_tasks, "dispatch_article_translation", lambda *args, **kwargs: (True, None)
    )
    response = await client.post(
        f"/api/v1/articles/{article.id}/translate?retry_unknown=true", headers=headers
    )
    assert response.status_code == 200, response.text
    await db_session.refresh(receipt)
    assert receipt.cache_key is None and receipt.budget_tokens == 228
    assert article.translation_revision == 0


def test_changing_output_limit_preserves_completed_checkpoints(local_db, monkeypatch):
    factory, ids = local_db
    sent = []

    async def request(self, endpoint, data):
        text = data["messages"][1]["content"]
        sent.append(text)
        if text.startswith("B") and sent.count(text) == 1:
            raise AIClientError("Rate limited", status_code=429)
        return reply("done")

    monkeypatch.setattr(OpenAIClient, "_request", request)
    with factory() as db:
        db.get(Article, ids["article"]).content = "A" * 3500 + "B" * 3500
        db.commit()
    assert not run(ids)["success"]
    with factory() as db:
        db.get(User, ids["user"]).translation_max_output_tokens = 8192
        db.commit()
    assert run(ids)["success"]
    assert sent.count("A" * 3500) == 1


def test_provider_paused_between_chunks_blocks_next_send(local_db, monkeypatch):
    factory, ids = local_db
    sent = []

    async def request(self, endpoint, data):
        sent.append(data)
        with factory() as db:
            db.get(AIProvider, ids["provider"]).is_active = False
            db.commit()
        return reply("done")

    monkeypatch.setattr(OpenAIClient, "_request", request)
    assert not run(ids)["success"]
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_usage_is_scoped_to_current_user(client, db_session):
    _, _, _, _, headers = await api_account(db_session)
    other = User(username="other", email="other@example.test", password_hash="unused")
    db_session.add(other)
    await db_session.flush()
    db_session.add(
        AIUsage(
            user_id=other.id,
            model="private",
            operation="translation",
            input_key="z" * 64,
            status="succeeded",
            estimated_input_tokens=100,
            max_output_tokens=256,
            budget_tokens=200,
            total_tokens=200,
            result_text="Private translation",
        )
    )
    await db_session.commit()
    response = await client.get("/api/v1/ai/translation-usage", headers=headers)
    assert response.json()["items"] == [] and response.json()["reported_tokens"] == 0
