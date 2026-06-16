"""Browser-backed fetch settings helpers."""
from dataclasses import asdict, dataclass, field
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.models.system_settings import SystemSettings
from app.repositories.system_settings_repository import SystemSettingsRepository


DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
VALID_WAIT_UNTIL = {"domcontentloaded", "load", "networkidle"}


@dataclass(frozen=True)
class BrowserFetchSettings:
    """Runtime settings for Playwright and CloakBrowser fetches."""

    feed_browser_refresh_dispatch_limit: int = 50
    custom_rule_browser_dispatch_limit: int = 1
    playwright_timeout_seconds: int = 90
    cloakbrowser_timeout_seconds: int = 90
    playwright_wait_until: str = "networkidle"
    cloakbrowser_wait_until: str = "networkidle"
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str = DEFAULT_BROWSER_USER_AGENT
    user_agent_pool: list[str] = field(default_factory=list)  # User-Agent 池
    user_agent_rotate: bool = False  # 是否随机轮换 UA
    block_images: bool = False
    block_media: bool = False
    cloakbrowser_humanize: bool = True
    cloakbrowser_geoip: bool = False

    def asdict(self) -> dict:
        return asdict(self)


BROWSER_FETCH_SETTING_DESCRIPTIONS = {
    "feed_browser_refresh_dispatch_limit": "浏览器模式 RSS 每轮派发数量",
    "custom_rule_browser_dispatch_limit": "浏览器模式自定义规则每轮派发数量",
    "playwright_timeout_seconds": "Playwright 页面超时时间",
    "cloakbrowser_timeout_seconds": "CloakBrowser 页面超时时间",
    "playwright_wait_until": "Playwright 页面等待策略",
    "cloakbrowser_wait_until": "CloakBrowser 页面等待策略",
    "viewport_width": "浏览器视口宽度",
    "viewport_height": "浏览器视口高度",
    "user_agent": "浏览器默认 User-Agent",
    "user_agent_pool": "User-Agent 池（JSON 数组）",
    "user_agent_rotate": "是否随机轮换 User-Agent",
    "block_images": "浏览器抓取是否拦截图片",
    "block_media": "浏览器抓取是否拦截媒体和字体",
    "cloakbrowser_humanize": "CloakBrowser humanize 开关",
    "cloakbrowser_geoip": "CloakBrowser geoip 开关",
}


def default_browser_fetch_settings() -> BrowserFetchSettings:
    """Build defaults from environment and app settings."""
    return BrowserFetchSettings(
        feed_browser_refresh_dispatch_limit=_coerce_int(
            os.environ.get("FEED_BROWSER_REFRESH_DISPATCH_LIMIT"),
            50,
            1,
            500,
        ),
        custom_rule_browser_dispatch_limit=_coerce_int(
            os.environ.get("CUSTOM_RULE_BROWSER_DISPATCH_LIMIT"),
            1,
            1,
            100,
        ),
        cloakbrowser_humanize=bool(app_settings.CLOAKBROWSER_HUMANIZE),
        cloakbrowser_geoip=bool(app_settings.CLOAKBROWSER_GEOIP),
    )


def browser_worker_runtime_settings() -> dict:
    """Return worker startup settings that require container restart to change."""
    return {
        "browser_worker_concurrency": _coerce_int(
            os.environ.get("BROWSER_WORKER_CONCURRENCY"),
            3,
            1,
            20,
        ),
        "browser_worker_max_tasks_per_child": _coerce_int(
            os.environ.get("BROWSER_WORKER_MAX_TASKS_PER_CHILD"),
            20,
            1,
            500,
        ),
        "browser_worker_cpus": _coerce_float(
            os.environ.get("BROWSER_WORKER_CPUS"),
            0.0,
            0.0,
            64.0,
        ),
    }


def worker_runtime_settings() -> dict:
    """Return regular worker startup settings that require container restart to change."""
    return {
        "worker_concurrency": _coerce_int(
            os.environ.get("WORKER_CONCURRENCY"),
            5,
            1,
            64,
        ),
        "worker_max_tasks_per_child": _coerce_int(
            os.environ.get("WORKER_MAX_TASKS_PER_CHILD"),
            20,
            1,
            500,
        ),
        "worker_cpus": _coerce_float(
            os.environ.get("WORKER_CPUS"),
            1.0,
            0.0,
            64.0,
        ),
    }


async def load_browser_fetch_settings(
    settings_repo: SystemSettingsRepository,
) -> BrowserFetchSettings:
    """Load browser fetch settings from the async repository."""
    values: dict[str, str | None] = {}
    for key in BROWSER_FETCH_SETTING_DESCRIPTIONS:
        values[key] = await settings_repo.get(key)
    return browser_fetch_settings_from_values(values)


def load_browser_fetch_settings_sync(db: Session) -> BrowserFetchSettings:
    """Load browser fetch settings from a sync SQLAlchemy session."""
    keys = list(BROWSER_FETCH_SETTING_DESCRIPTIONS)
    rows = db.execute(select(SystemSettings).where(SystemSettings.key.in_(keys))).scalars().all()
    return browser_fetch_settings_from_values({row.key: row.value for row in rows})


def browser_fetch_settings_from_values(values: dict[str, str | None]) -> BrowserFetchSettings:
    """Coerce raw key/value settings into a typed settings object."""
    import json
    defaults = default_browser_fetch_settings()

    # 解析 user_agent_pool
    user_agent_pool = []
    pool_value = values.get("user_agent_pool")
    if pool_value:
        try:
            parsed = json.loads(pool_value)
            if isinstance(parsed, list):
                user_agent_pool = [str(ua) for ua in parsed if ua]
        except (json.JSONDecodeError, TypeError):
            pass

    return BrowserFetchSettings(
        feed_browser_refresh_dispatch_limit=_coerce_int(
            values.get("feed_browser_refresh_dispatch_limit"),
            defaults.feed_browser_refresh_dispatch_limit,
            1,
            500,
        ),
        custom_rule_browser_dispatch_limit=_coerce_int(
            values.get("custom_rule_browser_dispatch_limit"),
            defaults.custom_rule_browser_dispatch_limit,
            1,
            100,
        ),
        playwright_timeout_seconds=_coerce_int(
            values.get("playwright_timeout_seconds"),
            defaults.playwright_timeout_seconds,
            5,
            300,
        ),
        cloakbrowser_timeout_seconds=_coerce_int(
            values.get("cloakbrowser_timeout_seconds"),
            defaults.cloakbrowser_timeout_seconds,
            5,
            300,
        ),
        playwright_wait_until=_coerce_wait_until(
            values.get("playwright_wait_until"),
            defaults.playwright_wait_until,
        ),
        cloakbrowser_wait_until=_coerce_wait_until(
            values.get("cloakbrowser_wait_until"),
            defaults.cloakbrowser_wait_until,
        ),
        viewport_width=_coerce_int(values.get("viewport_width"), defaults.viewport_width, 320, 3840),
        viewport_height=_coerce_int(values.get("viewport_height"), defaults.viewport_height, 240, 2160),
        user_agent=_coerce_str(values.get("user_agent"), defaults.user_agent, 500),
        user_agent_pool=user_agent_pool,
        user_agent_rotate=_coerce_bool(values.get("user_agent_rotate"), False),
        block_images=_coerce_bool(values.get("block_images"), defaults.block_images),
        block_media=_coerce_bool(values.get("block_media"), defaults.block_media),
        cloakbrowser_humanize=_coerce_bool(
            values.get("cloakbrowser_humanize"),
            defaults.cloakbrowser_humanize,
        ),
        cloakbrowser_geoip=_coerce_bool(values.get("cloakbrowser_geoip"), defaults.cloakbrowser_geoip),
    )


def _coerce_int(value: str | int | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _coerce_float(
    value: str | float | int | None,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _coerce_bool(value: str | bool | None, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.lower() in {"true", "1", "yes", "on"}


def _coerce_wait_until(value: str | None, default: str) -> str:
    normalized = (value or default).strip().lower()
    return normalized if normalized in VALID_WAIT_UNTIL else default


def _coerce_str(value: str | None, default: str, max_length: int) -> str:
    normalized = (value or "").strip()
    if not normalized:
        normalized = default
    return normalized[:max_length]
