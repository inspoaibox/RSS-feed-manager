"""System settings API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.repositories.user_repository import UserRepository
from app.services.browser_fetch_settings import (
    BROWSER_FETCH_SETTING_DESCRIPTIONS,
    browser_fetch_settings_from_values,
    browser_worker_runtime_settings,
    load_browser_fetch_settings,
    worker_runtime_settings,
)

router = APIRouter()


class OAuthConfig(BaseModel):
    """OAuth provider configuration."""
    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    authorize_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""


# 默认的同步间隔选项（秒）
DEFAULT_SYNC_INTERVALS = [
    {"value": 300, "label": "5 分钟"},
    {"value": 900, "label": "15 分钟"},
    {"value": 1800, "label": "30 分钟"},
    {"value": 3600, "label": "1 小时"},
    {"value": 7200, "label": "2 小时"},
    {"value": 14400, "label": "4 小时"},
    {"value": 43200, "label": "12 小时"},
    {"value": 86400, "label": "24 小时"},
]


class SyncIntervalOption(BaseModel):
    """Sync interval option."""
    value: int
    label: str


class BrowserFetchSettingsPayload(BaseModel):
    """Browser fetch settings that can be changed at runtime."""
    feed_browser_refresh_dispatch_limit: int = 50
    custom_rule_browser_dispatch_limit: int = 1
    playwright_timeout_seconds: int = 90
    cloakbrowser_timeout_seconds: int = 90
    playwright_wait_until: str = "networkidle"
    cloakbrowser_wait_until: str = "networkidle"
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str = ""
    block_images: bool = False
    block_media: bool = False
    cloakbrowser_humanize: bool = True
    cloakbrowser_geoip: bool = False


class BrowserWorkerRuntimeSettings(BaseModel):
    """Browser worker startup settings that require container restart."""
    browser_worker_concurrency: int
    browser_worker_max_tasks_per_child: int
    browser_worker_cpus: float


class WorkerRuntimeSettings(BaseModel):
    """Regular worker startup settings that require container restart."""
    worker_concurrency: int
    worker_max_tasks_per_child: int
    worker_cpus: float


class SystemSettingsResponse(BaseModel):
    """Response schema for system settings."""
    allow_registration: bool
    site_name: str
    oauth_linuxdo: OAuthConfig
    sync_intervals: list[SyncIntervalOption]
    default_sync_interval: int
    enable_feed_recommendations: bool
    show_favorites_menu: bool
    show_ai_analysis_menu: bool
    show_recommendations_menu: bool
    browser_fetch: BrowserFetchSettingsPayload
    worker_runtime: WorkerRuntimeSettings
    browser_worker_runtime: BrowserWorkerRuntimeSettings


class SystemSettingsUpdate(BaseModel):
    """Update schema for system settings."""
    allow_registration: bool | None = None
    site_name: str | None = None
    oauth_linuxdo: OAuthConfig | None = None
    sync_intervals: list[SyncIntervalOption] | None = None
    default_sync_interval: int | None = None
    enable_feed_recommendations: bool | None = None
    show_favorites_menu: bool | None = None
    show_ai_analysis_menu: bool | None = None
    show_recommendations_menu: bool | None = None
    browser_fetch: BrowserFetchSettingsPayload | None = None
    worker_runtime: WorkerRuntimeSettings | None = None
    browser_worker_runtime: BrowserWorkerRuntimeSettings | None = None


class PublicSettingsResponse(BaseModel):
    """Response schema for public settings (no auth required)."""
    site_name: str
    sync_intervals: list[SyncIntervalOption]
    default_sync_interval: int
    show_favorites_menu: bool
    show_ai_analysis_menu: bool
    show_recommendations_menu: bool


class UserListResponse(BaseModel):
    """Response schema for user list."""
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: str | None
    last_login_at: str | None

    class Config:
        from_attributes = True


class RegistrationStatusResponse(BaseModel):
    """Response schema for registration status (public)."""
    allow_registration: bool
    has_users: bool
    site_name: str


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin user."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


@router.get("/public-settings", response_model=PublicSettingsResponse)
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    """Get public settings (no auth required)."""
    settings_repo = SystemSettingsRepository(db)
    site_name = await settings_repo.get('site_name') or 'RSS 管理器'
    
    default_interval_str = await settings_repo.get('default_sync_interval')
    default_interval = int(default_interval_str) if default_interval_str else 3600
    
    return PublicSettingsResponse(
        site_name=site_name,
        sync_intervals=await get_sync_intervals(settings_repo),
        default_sync_interval=default_interval,
        show_favorites_menu=await settings_repo.get_bool('show_favorites_menu', True),
        show_ai_analysis_menu=await settings_repo.get_bool('show_ai_analysis_menu', True),
        show_recommendations_menu=await settings_repo.get_bool('show_recommendations_menu', True),
    )


@router.get("/registration-status", response_model=RegistrationStatusResponse)
async def get_registration_status(db: AsyncSession = Depends(get_db)):
    """Get registration status (public endpoint)."""
    settings_repo = SystemSettingsRepository(db)
    user_repo = UserRepository(db)
    
    allow_registration = await settings_repo.get_bool('allow_registration', True)
    user_count = await user_repo.count_users()
    site_name = await settings_repo.get('site_name') or 'RSS 管理器'
    
    return RegistrationStatusResponse(
        allow_registration=allow_registration or user_count == 0,  # Always allow if no users
        has_users=user_count > 0,
        site_name=site_name
    )


async def get_oauth_config(settings_repo: SystemSettingsRepository, provider: str) -> OAuthConfig:
    """Get OAuth config for a provider."""
    import json
    config_str = await settings_repo.get(f'oauth_{provider}')
    if config_str:
        try:
            data = json.loads(config_str)
            return OAuthConfig(**data)
        except (json.JSONDecodeError, TypeError):
            pass
    return OAuthConfig()


async def get_sync_intervals(settings_repo: SystemSettingsRepository) -> list[SyncIntervalOption]:
    """Get sync interval options."""
    import json
    intervals_str = await settings_repo.get('sync_intervals')
    if intervals_str:
        try:
            data = json.loads(intervals_str)
            return [SyncIntervalOption(**item) for item in data]
        except (json.JSONDecodeError, TypeError):
            pass
    return [SyncIntervalOption(**item) for item in DEFAULT_SYNC_INTERVALS]


async def build_system_settings_response(
    settings_repo: SystemSettingsRepository,
) -> SystemSettingsResponse:
    """Build the complete admin settings response."""
    default_interval_str = await settings_repo.get('default_sync_interval')
    default_interval = int(default_interval_str) if default_interval_str else 3600
    browser_fetch = await load_browser_fetch_settings(settings_repo)

    # Load worker runtime settings from database (for pending changes) or environment (current values)
    worker_concurrency_db = await settings_repo.get('worker_concurrency')
    worker_max_tasks_db = await settings_repo.get('worker_max_tasks_per_child')
    worker_cpus_db = await settings_repo.get('worker_cpus')

    browser_worker_concurrency_db = await settings_repo.get('browser_worker_concurrency')
    browser_worker_max_tasks_db = await settings_repo.get('browser_worker_max_tasks_per_child')
    browser_worker_cpus_db = await settings_repo.get('browser_worker_cpus')

    # Get current runtime values
    runtime_worker = worker_runtime_settings()
    runtime_browser_worker = browser_worker_runtime_settings()

    # Use database values if available, otherwise use current runtime values
    worker_config = WorkerRuntimeSettings(
        worker_concurrency=int(worker_concurrency_db) if worker_concurrency_db else runtime_worker['worker_concurrency'],
        worker_max_tasks_per_child=int(worker_max_tasks_db) if worker_max_tasks_db else runtime_worker['worker_max_tasks_per_child'],
        worker_cpus=float(worker_cpus_db) if worker_cpus_db else runtime_worker['worker_cpus'],
    )

    browser_worker_config = BrowserWorkerRuntimeSettings(
        browser_worker_concurrency=int(browser_worker_concurrency_db) if browser_worker_concurrency_db else runtime_browser_worker['browser_worker_concurrency'],
        browser_worker_max_tasks_per_child=int(browser_worker_max_tasks_db) if browser_worker_max_tasks_db else runtime_browser_worker['browser_worker_max_tasks_per_child'],
        browser_worker_cpus=float(browser_worker_cpus_db) if browser_worker_cpus_db else runtime_browser_worker['browser_worker_cpus'],
    )

    return SystemSettingsResponse(
        allow_registration=await settings_repo.get_bool('allow_registration', True),
        site_name=await settings_repo.get('site_name') or 'RSS 管理器',
        oauth_linuxdo=await get_oauth_config(settings_repo, 'linuxdo'),
        sync_intervals=await get_sync_intervals(settings_repo),
        default_sync_interval=default_interval,
        enable_feed_recommendations=await settings_repo.get_bool('enable_feed_recommendations', False),
        show_favorites_menu=await settings_repo.get_bool('show_favorites_menu', True),
        show_ai_analysis_menu=await settings_repo.get_bool('show_ai_analysis_menu', True),
        show_recommendations_menu=await settings_repo.get_bool('show_recommendations_menu', True),
        browser_fetch=BrowserFetchSettingsPayload(**browser_fetch.asdict()),
        worker_runtime=worker_config,
        browser_worker_runtime=browser_worker_config,
    )


def setting_value_to_string(value: object) -> str:
    """Serialize a setting value for the key/value settings table."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@router.get("/settings", response_model=SystemSettingsResponse)
async def get_system_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get system settings (admin only)."""
    settings_repo = SystemSettingsRepository(db)
    return await build_system_settings_response(settings_repo)


@router.put("/settings", response_model=SystemSettingsResponse)
async def update_system_settings(
    data: SystemSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update system settings (admin only)."""
    import json
    settings_repo = SystemSettingsRepository(db)
    
    if data.allow_registration is not None:
        await settings_repo.set(
            'allow_registration',
            'true' if data.allow_registration else 'false',
            '是否允许新用户注册'
        )
    
    if data.site_name is not None:
        await settings_repo.set(
            'site_name',
            data.site_name.strip() or 'RSS 管理器',
            '网站名称'
        )
    
    if data.oauth_linuxdo is not None:
        await settings_repo.set(
            'oauth_linuxdo',
            json.dumps(data.oauth_linuxdo.model_dump()),
            'Linux.do OAuth 配置'
        )
    
    if data.sync_intervals is not None:
        await settings_repo.set(
            'sync_intervals',
            json.dumps([item.model_dump() for item in data.sync_intervals]),
            '可用的同步间隔选项'
        )
    
    if data.default_sync_interval is not None:
        await settings_repo.set(
            'default_sync_interval',
            str(data.default_sync_interval),
            '默认同步间隔'
        )
    
    if data.enable_feed_recommendations is not None:
        await settings_repo.set(
            'enable_feed_recommendations',
            'true' if data.enable_feed_recommendations else 'false',
            '是否开启订阅推荐功能'
        )

    if data.show_favorites_menu is not None:
        await settings_repo.set(
            'show_favorites_menu',
            'true' if data.show_favorites_menu else 'false',
            '是否在左侧菜单显示收藏入口'
        )

    if data.show_ai_analysis_menu is not None:
        await settings_repo.set(
            'show_ai_analysis_menu',
            'true' if data.show_ai_analysis_menu else 'false',
            '是否在左侧菜单显示 AI 分析入口'
        )

    if data.show_recommendations_menu is not None:
        await settings_repo.set(
            'show_recommendations_menu',
            'true' if data.show_recommendations_menu else 'false',
            '是否在左侧菜单显示订阅推荐入口'
        )

    if data.browser_fetch is not None:
        raw_browser_fetch = data.browser_fetch.model_dump(exclude_unset=True)
        current_browser_fetch = await load_browser_fetch_settings(settings_repo)
        merged_browser_fetch = {
            **current_browser_fetch.asdict(),
            **raw_browser_fetch,
        }
        normalized_browser_fetch = browser_fetch_settings_from_values(
            {key: setting_value_to_string(value) for key, value in merged_browser_fetch.items()}
        )
        for key, value in normalized_browser_fetch.asdict().items():
            await settings_repo.set(
                key,
                setting_value_to_string(value),
                BROWSER_FETCH_SETTING_DESCRIPTIONS.get(key),
            )

    # Save worker runtime settings to database
    if data.worker_runtime is not None:
        await settings_repo.set(
            'worker_concurrency',
            str(data.worker_runtime.worker_concurrency),
            '普通 Worker 并发数'
        )
        await settings_repo.set(
            'worker_max_tasks_per_child',
            str(data.worker_runtime.worker_max_tasks_per_child),
            '普通 Worker 子进程最大任务数'
        )
        await settings_repo.set(
            'worker_cpus',
            str(data.worker_runtime.worker_cpus),
            '普通 Worker CPU 限额 (0=不限制)'
        )

    # Save browser worker runtime settings to database
    if data.browser_worker_runtime is not None:
        await settings_repo.set(
            'browser_worker_concurrency',
            str(data.browser_worker_runtime.browser_worker_concurrency),
            '浏览器 Worker 并发数'
        )
        await settings_repo.set(
            'browser_worker_max_tasks_per_child',
            str(data.browser_worker_runtime.browser_worker_max_tasks_per_child),
            '浏览器 Worker 子进程最大任务数'
        )
        await settings_repo.set(
            'browser_worker_cpus',
            str(data.browser_worker_runtime.browser_worker_cpus),
            '浏览器 Worker CPU 限额 (0=不限制)'
        )

    await db.commit()
    return await build_system_settings_response(settings_repo)


@router.get("/users", response_model=list[UserListResponse])
async def get_all_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get all users (admin only)."""
    user_repo = UserRepository(db)
    users = await user_repo.get_all_users()
    
    return [
        UserListResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            is_active=u.is_active,
            is_admin=u.is_admin,
            created_at=u.created_at.isoformat() if u.created_at else None,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None
        )
        for u in users
    ]


class UserUpdateRequest(BaseModel):
    """Request schema for updating user."""
    is_active: bool | None = None
    is_admin: bool | None = None


@router.put("/users/{user_id}", response_model=UserListResponse)
async def update_user(
    user_id: int,
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update a user (admin only)."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改自己的账户状态"
        )
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if data.is_active is not None:
        user.is_active = data.is_active
        # Invalidate tokens when deactivating
        if not data.is_active:
            user.token_version += 1
    
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    
    await db.commit()
    
    return UserListResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete a user and all their data (admin only)."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户"
        )
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # Delete user (cascade will delete all related data)
    await db.delete(user)
    await db.commit()


@router.get("/manifest.json")
async def get_manifest(db: AsyncSession = Depends(get_db)):
    """Generate dynamic PWA manifest with site name from settings."""
    settings_repo = SystemSettingsRepository(db)
    site_name = await settings_repo.get('site_name') or 'RSS 管理器'
    
    manifest = {
        "name": site_name,
        "short_name": site_name[:12] if len(site_name) > 12 else site_name,
        "description": "RSS 订阅管理器",
        "theme_color": "#3b82f6",
        "background_color": "#ffffff",
        "display": "standalone",
        "orientation": "portrait",
        "scope": "/",
        "start_url": "/",
        "icons": [
            {
                "src": "/pwa-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/pwa-512x512.png",
                "sizes": "512x512",
                "type": "image/png"
            },
            {
                "src": "/pwa-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    
    return JSONResponse(content=manifest, media_type="application/manifest+json")
