"""System settings API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.repositories.user_repository import UserRepository

router = APIRouter()


class SystemSettingsResponse(BaseModel):
    """Response schema for system settings."""
    allow_registration: bool


class SystemSettingsUpdate(BaseModel):
    """Update schema for system settings."""
    allow_registration: bool | None = None


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


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin user."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


@router.get("/registration-status", response_model=RegistrationStatusResponse)
async def get_registration_status(db: AsyncSession = Depends(get_db)):
    """Get registration status (public endpoint)."""
    settings_repo = SystemSettingsRepository(db)
    user_repo = UserRepository(db)
    
    allow_registration = await settings_repo.get_bool('allow_registration', True)
    user_count = await user_repo.count_users()
    
    return RegistrationStatusResponse(
        allow_registration=allow_registration or user_count == 0,  # Always allow if no users
        has_users=user_count > 0
    )


@router.get("/settings", response_model=SystemSettingsResponse)
async def get_system_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get system settings (admin only)."""
    settings_repo = SystemSettingsRepository(db)
    
    return SystemSettingsResponse(
        allow_registration=await settings_repo.get_bool('allow_registration', True)
    )


@router.put("/settings", response_model=SystemSettingsResponse)
async def update_system_settings(
    data: SystemSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update system settings (admin only)."""
    settings_repo = SystemSettingsRepository(db)
    
    if data.allow_registration is not None:
        await settings_repo.set(
            'allow_registration',
            'true' if data.allow_registration else 'false',
            '是否允许新用户注册'
        )
    
    await db.commit()
    
    return SystemSettingsResponse(
        allow_registration=await settings_repo.get_bool('allow_registration', True)
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
