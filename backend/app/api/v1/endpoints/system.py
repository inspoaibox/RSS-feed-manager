"""System settings API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.repositories.user_repository import UserRepository

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


class SystemSettingsResponse(BaseModel):
    """Response schema for system settings."""
    allow_registration: bool
    site_name: str
    oauth_linuxdo: OAuthConfig
    sync_intervals: list[SyncIntervalOption]
    default_sync_interval: int


class SystemSettingsUpdate(BaseModel):
    """Update schema for system settings."""
    allow_registration: bool | None = None
    site_name: str | None = None
    oauth_linuxdo: OAuthConfig | None = None
    sync_intervals: list[SyncIntervalOption] | None = None
    default_sync_interval: int | None = None


class PublicSettingsResponse(BaseModel):
    """Response schema for public settings (no auth required)."""
    site_name: str
    sync_intervals: list[SyncIntervalOption]
    default_sync_interval: int


class UserListResponse(BaseModel):
    """Response schema for user list."""
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: str | None

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
        default_sync_interval=default_interval
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


@router.get("/settings", response_model=SystemSettingsResponse)
async def get_system_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get system settings (admin only)."""
    settings_repo = SystemSettingsRepository(db)
    
    default_interval_str = await settings_repo.get('default_sync_interval')
    default_interval = int(default_interval_str) if default_interval_str else 3600
    
    return SystemSettingsResponse(
        allow_registration=await settings_repo.get_bool('allow_registration', True),
        site_name=await settings_repo.get('site_name') or 'RSS 管理器',
        oauth_linuxdo=await get_oauth_config(settings_repo, 'linuxdo'),
        sync_intervals=await get_sync_intervals(settings_repo),
        default_sync_interval=default_interval
    )


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
    
    await db.commit()
    
    default_interval_str = await settings_repo.get('default_sync_interval')
    default_interval = int(default_interval_str) if default_interval_str else 3600
    
    return SystemSettingsResponse(
        allow_registration=await settings_repo.get_bool('allow_registration', True),
        site_name=await settings_repo.get('site_name') or 'RSS 管理器',
        oauth_linuxdo=await get_oauth_config(settings_repo, 'linuxdo'),
        sync_intervals=await get_sync_intervals(settings_repo),
        default_sync_interval=default_interval
    )


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
            created_at=u.created_at.isoformat() if u.created_at else None
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
        created_at=user.created_at.isoformat() if user.created_at else None
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
