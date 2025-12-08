"""Authentication API endpoints."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserId, DbSession
from app.schemas.auth import (
    AuthResponse,
    PasswordChange,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: DbSession):
    """Register a new user."""
    service = AuthService(db)
    return await service.register(data)


@router.post("/login", response_model=AuthResponse)
async def login(data: UserLogin, db: DbSession):
    """Login and get access tokens."""
    service = AuthService(db)
    return await service.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshTokenRequest, db: DbSession):
    """Refresh access token using refresh token."""
    service = AuthService(db)
    return await service.refresh_token(data.refresh_token)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(data: PasswordChange, user_id: CurrentUserId, db: DbSession):
    """Change current user's password."""
    service = AuthService(db)
    await service.change_password(user_id, data.current_password, data.new_password)


@router.get("/me", response_model=UserResponse)
async def get_current_user(user_id: CurrentUserId, db: DbSession):
    """Get current authenticated user."""
    service = AuthService(db)
    user = await service.get_current_user(user_id)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    """Logout current user (client should discard tokens)."""
    # JWT tokens are stateless, so logout is handled client-side
    # by discarding the tokens. This endpoint exists for API completeness.
    return None
