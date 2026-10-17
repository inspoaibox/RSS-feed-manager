"""Reserve translation budgets before sending and retain durable provider receipts."""

import hashlib
import json
from datetime import UTC
from uuid import uuid4

from sqlalchemy import func, select

from app.core.clock import utc_now
from app.models.ai_provider import AIModel, AIProvider
from app.models.ai_usage import AIUsage
from app.models.user import User
from app.services.ai_client import AIClientError, completion_text


def estimate_input_tokens(data: dict) -> int:
    """Conservative text-byte estimate, not a model tokenizer or a billing receipt."""
    if "messages" in data:
        texts = [m.get("content", "") for m in data["messages"]]
    else:
        texts = [p.get("text", "") for c in data.get("contents", []) for p in c.get("parts", [])]
    return sum(len(t.encode("utf-8")) + 16 for t in texts) + 16


def _count(value):
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 2000000000
        else None
    )


def usage_fields(response: dict) -> dict:
    usage = response.get("usage") if isinstance(response, dict) else None
    if isinstance(usage, dict):
        incoming, outgoing = (
            _count(usage.get("prompt_tokens")),
            _count(usage.get("completion_tokens")),
        )
        prompt_details = usage.get("prompt_tokens_details")
        output_details = usage.get("completion_tokens_details")
        cached = (
            _count(prompt_details.get("cached_tokens"))
            if isinstance(prompt_details, dict)
            else None
        )
        reasoning = (
            _count(output_details.get("reasoning_tokens"))
            if isinstance(output_details, dict)
            else None
        )
        total = _count(usage.get("total_tokens"))
    else:
        usage = response.get("usageMetadata") if isinstance(response, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        incoming = _count(usage.get("promptTokenCount"))
        outgoing = _count(usage.get("candidatesTokenCount"))
        reasoning = _count(usage.get("thoughtsTokenCount"))
        if outgoing is not None:
            outgoing += reasoning or 0
        cached = _count(usage.get("cachedContentTokenCount"))
        total = _count(usage.get("totalTokenCount"))
    if incoming is not None and outgoing is not None:
        total = max(total or 0, incoming + outgoing)
    # Cached/reasoning counts are subsets, never added to OpenAI's total again.
    return dict(
        input_tokens=incoming,
        output_tokens=outgoing,
        total_tokens=total,
        cached_tokens=cached,
        reasoning_tokens=reasoning,
    )


def _completion(response: dict) -> tuple[str, str]:
    try:
        return "succeeded", completion_text(response, gemini="candidates" in response)
    except AIClientError as exc:
        return ("truncated" if "truncated" in str(exc) else "unknown"), ""


class TranslationUsageRecorder:
    """Use a short user-row lock to serialize reservations across workers."""

    def __init__(
        self,
        db,
        user_id: int,
        provider_id: int,
        model_id: int,
        *,
        article_id: int | None = None,
        revision: int = 0,
        target: str = "",
        operation: str = "translation",
    ):
        self.db = db
        self.user_id, self.provider_id, self.model_id = user_id, provider_id, model_id
        self.article_id, self.revision = article_id, revision
        self.target, self.operation = target, operation
        self.request_id = None
        self.nonce = str(uuid4()) if article_id is None else ""

    def begin(self, endpoint: str, data: dict) -> dict | None:
        db = self.db
        user = db.execute(
            select(User)
            .where(User.id == self.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()
        provider = db.get(AIProvider, self.provider_id, populate_existing=True)
        model = db.get(AIModel, self.model_id, populate_existing=True)
        if (
            not provider
            or provider.user_id != self.user_id
            or not provider.is_active
            or not model
            or model.provider_id != provider.id
            or not model.is_active
        ):
            db.rollback()
            raise AIClientError("AI 渠道或模型已停用，请选择启用的模型")
        key = hashlib.sha256(
            json.dumps(
                [
                    self.user_id,
                    self.article_id,
                    self.revision,
                    self.provider_id,
                    provider.base_url,
                    self.target,
                    self.operation,
                    self.nonce,
                    endpoint,
                    data,
                ],
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        semantic_data = {
            k: v for k, v in data.items() if k not in {"max_tokens", "max_completion_tokens"}
        }
        if "generationConfig" in semantic_data:
            semantic_data["generationConfig"] = {
                k: v for k, v in semantic_data["generationConfig"].items() if k != "maxOutputTokens"
            }
        input_key = hashlib.sha256(
            json.dumps(
                [
                    self.user_id,
                    self.article_id,
                    self.revision,
                    self.provider_id,
                    provider.base_url,
                    self.target,
                    self.operation,
                    self.nonce,
                    endpoint,
                    semantic_data,
                ],
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        previous_rows = db.scalars(
            select(AIUsage).where(AIUsage.input_key == input_key).order_by(AIUsage.id.desc())
        ).all()
        previous = next((row for row in previous_rows if row.status == "succeeded"), None)
        if previous is None:
            previous = next(
                (
                    row
                    for row in previous_rows
                    if row.cache_key is not None and row.status in {"pending", "unknown"}
                ),
                None,
            )
        if previous is None:
            previous = next((row for row in previous_rows if row.cache_key == key), None)
        if previous:
            status, text = previous.status, previous.result_text
            db.commit()
            if status not in {"succeeded", "truncated"}:
                raise AIClientError(
                    "上次请求结果尚未确认，已阻止重复发送；核对渠道用量后可重试未确认分段"
                )
            finish = "length" if status == "truncated" else "stop"
            return {
                "choices": [{"message": {"content": text or ""}, "finish_reason": finish}],
                "candidates": [
                    {
                        "content": {"parts": [{"text": text or ""}]},
                        "finishReason": "MAX_TOKENS" if status == "truncated" else "STOP",
                    }
                ],
            }
        incoming = estimate_input_tokens(data)
        output = data.get("max_completion_tokens", data.get("max_tokens"))
        if output is None:
            output = data.get("generationConfig", {}).get("maxOutputTokens")
        if not isinstance(output, int) or not 1 <= output <= user.translation_max_output_tokens:
            db.rollback()
            raise AIClientError("翻译输出上限无效或超过当前设置，请重新提交任务")
        if incoming > user.translation_max_input_tokens:
            db.rollback()
            raise AIClientError("本次输入超过翻译输入预算，请缩短提示词或提高输入预算")
        reserved = incoming + output
        now = utc_now().replace(tzinfo=UTC)
        month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly = db.scalar(
            select(func.coalesce(func.sum(AIUsage.budget_tokens), 0)).where(
                AIUsage.user_id == self.user_id, AIUsage.created_at >= month
            )
        )
        if (
            user.translation_monthly_token_limit
            and monthly + reserved > user.translation_monthly_token_limit
        ):
            db.rollback()
            raise AIClientError("已达到本月翻译 token 预算，任务暂停发送")
        if self.article_id is not None:
            spent, requests = db.execute(
                select(
                    func.coalesce(func.sum(AIUsage.budget_tokens), 0), func.count(AIUsage.id)
                ).where(AIUsage.user_id == self.user_id, AIUsage.article_id == self.article_id)
            ).one()
            if (
                spent + reserved > user.translation_article_token_limit
                or requests >= user.translation_max_requests
            ):
                db.rollback()
                raise AIClientError("已达到此文章的翻译预算或请求次数上限，已保留完成的分段")
        row = AIUsage(
            user_id=self.user_id,
            provider_id=provider.id,
            article_id=self.article_id,
            model=model.model_id,
            operation=self.operation,
            cache_key=key,
            input_key=input_key,
            status="pending",
            created_at=now,
            estimated_input_tokens=incoming,
            max_output_tokens=output,
            budget_tokens=reserved,
        )
        db.add(row)
        db.flush()
        self.request_id = row.id
        db.commit()
        return None

    def finish(self, response: dict):
        row = self.db.get(AIUsage, self.request_id)
        fields = usage_fields(response)
        for key, value in fields.items():
            setattr(row, key, value)
        if fields["total_tokens"] is not None:
            row.budget_tokens = fields["total_tokens"]
        row.status, row.result_text = _completion(response if isinstance(response, dict) else {})
        if row.status == "unknown":
            row.error = "响应没有完整译文，已阻止自动重复发送"
        self.db.commit()

    def fail(self, error: Exception):
        row = self.db.get(AIUsage, self.request_id)
        code = getattr(error, "status_code", None)
        rejected = code in {400, 401, 403, 404, 405, 413, 422, 429}
        row.status = "rejected" if rejected else "unknown"
        row.error = f"HTTP {code}" if code else "请求中断，服务商是否已计费尚未确认"
        if rejected:
            row.budget_tokens = 0
            row.cache_key = None
        self.db.commit()


class AsyncTranslationUsageRecorder:
    def __init__(self, db, *args, **kwargs):
        self.db = db
        self.recorder = TranslationUsageRecorder(db.sync_session, *args, **kwargs)

    async def begin(self, endpoint, data):
        return await self.db.run_sync(lambda _: self.recorder.begin(endpoint, data))

    async def finish(self, result):
        await self.db.run_sync(lambda _: self.recorder.finish(result))

    async def fail(self, error):
        await self.db.run_sync(lambda _: self.recorder.fail(error))
