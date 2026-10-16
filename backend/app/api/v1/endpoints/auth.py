"""Authentication API endpoints."""

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from sqlalchemy import delete

from app.api.deps import CurrentUserId, DbSession
from app.core.config import settings
from app.core.cookies import clear_refresh_cookie, set_refresh_cookie
from app.core.security import decode_token
from app.models.push_notification import WebPushSubscription
from app.repositories.user_repository import UserRepository
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
async def register(data: UserCreate, request: Request, response: Response, db: DbSession):
    """Register a new user."""
    require_same_origin(request)
    service = AuthService(db)
    auth_response, refresh_token = await service.register(data)
    set_refresh_cookie(response, refresh_token)
    return auth_response


@router.post("/login", response_model=AuthResponse)
async def login(data: UserLogin, request: Request, response: Response, db: DbSession):
    """Login and get access tokens."""
    require_same_origin(request)
    service = AuthService(db)
    auth_response, refresh_token = await service.login(data)
    set_refresh_cookie(response, refresh_token)
    return auth_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: DbSession,
    data: RefreshTokenRequest | None = None,
    refresh_cookie: str | None = Cookie(None, alias=settings.REFRESH_COOKIE_NAME),
):
    """Refresh access token using refresh token."""
    require_same_origin(request)
    service = AuthService(db)
    token = refresh_cookie or (data.refresh_token if data else None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token"
        )
    token_response, rotated_refresh_token = await service.refresh_token(token)
    set_refresh_cookie(response, rotated_refresh_token)
    return token_response


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
async def logout(
    request: Request,
    response: Response,
    db: DbSession,
    refresh_cookie: str | None = Cookie(None, alias=settings.REFRESH_COOKIE_NAME),
):
    """Remove the browser's refresh credential."""
    require_same_origin(request)
    payload = decode_token(refresh_cookie) if refresh_cookie else None
    if payload and payload.get("type") == "refresh":
        user = await UserRepository(db).get_by_id(int(payload["sub"]))
        if user and user.token_version == payload.get("token_version"):
            user.token_version += 1
            await db.execute(
                delete(WebPushSubscription).where(WebPushSubscription.user_id == user.id)
            )
            await db.flush()
    clear_refresh_cookie(response)


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    allowed = set(settings.CORS_ORIGINS) | {str(request.base_url).rstrip("/")}
    if (origin and origin.rstrip("/") not in allowed) or request.headers.get(
        "sec-fetch-site"
    ) == "cross-site":
        raise HTTPException(status_code=403, detail="Cross-origin authentication is blocked")
