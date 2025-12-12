"""OAuth authentication endpoints."""
import json
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import create_access_token, create_refresh_token
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.repositories.user_repository import UserRepository

router = APIRouter()

# Store OAuth states temporarily (in production, use Redis)
oauth_states: dict[str, dict] = {}


class OAuthLoginResponse(BaseModel):
    """Response for OAuth login initiation."""
    auth_url: str


class PublicOAuthStatus(BaseModel):
    """Public OAuth provider status."""
    linuxdo_enabled: bool
    linuxdo_auth_url: str | None = None


@router.get("/status", response_model=PublicOAuthStatus)
async def get_oauth_status(db: AsyncSession = Depends(get_db)):
    """Get public OAuth provider status (no auth required)."""
    settings_repo = SystemSettingsRepository(db)
    
    linuxdo_enabled = False
    linuxdo_auth_url = None
    config_str = await settings_repo.get('oauth_linuxdo')
    if config_str:
        try:
            config = json.loads(config_str)
            # Check both enabled flag and client_id exists
            if isinstance(config, dict):
                linuxdo_enabled = bool(config.get('enabled', False) and config.get('client_id'))
                
                # Build auth URL directly for frontend to use
                if linuxdo_enabled and config.get('authorize_url'):
                    state = secrets.token_urlsafe(32)
                    oauth_states[state] = {"provider": "linuxdo"}
                    
                    params = {
                        "client_id": config["client_id"],
                        "response_type": "code",
                        "redirect_uri": f"{get_base_url()}/api/v1/auth/callback/linuxdo",
                        "state": state,
                        "scope": "read",
                    }
                    linuxdo_auth_url = f"{config['authorize_url']}?{urlencode(params)}"
        except (json.JSONDecodeError, TypeError, ValueError):
            # Invalid JSON or not a dict, ignore
            pass
    
    return PublicOAuthStatus(linuxdo_enabled=linuxdo_enabled, linuxdo_auth_url=linuxdo_auth_url)


@router.get("/linuxdo/login")
async def linuxdo_login(db: AsyncSession = Depends(get_db)):
    """Initiate Linux.do OAuth login."""
    settings_repo = SystemSettingsRepository(db)
    
    config_str = await settings_repo.get('oauth_linuxdo')
    if not config_str:
        raise HTTPException(status_code=400, detail="Linux.do OAuth 未配置")
    
    try:
        config = json.loads(config_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="OAuth 配置无效")
    
    if not isinstance(config, dict):
        raise HTTPException(status_code=400, detail="OAuth 配置格式错误")
    
    if not config.get('enabled'):
        raise HTTPException(status_code=400, detail="Linux.do OAuth 未启用")
    
    if not config.get('client_id'):
        raise HTTPException(status_code=400, detail="OAuth Client ID 未配置")
    
    if not config.get('authorize_url'):
        raise HTTPException(status_code=400, detail="OAuth Authorization URL 未配置")
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {"provider": "linuxdo"}
    
    # Build authorization URL
    base_url = get_base_url()
    params = {
        "client_id": config["client_id"],
        "response_type": "code",
        "redirect_uri": f"{base_url}/api/v1/auth/callback/linuxdo",
        "state": state,
        "scope": "read",
    }
    
    auth_url = f"{config['authorize_url']}?{urlencode(params)}"
    print(f"OAuth redirect to: {auth_url}")
    
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback/linuxdo")
async def linuxdo_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Handle Linux.do OAuth callback."""
    if error:
        return RedirectResponse(url=f"/login?error=oauth_error&message={error}")
    
    if not code or not state:
        return RedirectResponse(url="/login?error=oauth_error&message=missing_params")
    
    # Verify state
    if state not in oauth_states:
        return RedirectResponse(url="/login?error=oauth_error&message=invalid_state")
    
    del oauth_states[state]
    
    settings_repo = SystemSettingsRepository(db)
    config_str = await settings_repo.get('oauth_linuxdo')
    
    if not config_str:
        return RedirectResponse(url="/login?error=oauth_error&message=not_configured")
    
    try:
        config = json.loads(config_str)
    except json.JSONDecodeError:
        return RedirectResponse(url="/login?error=oauth_error&message=invalid_config")
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(
                config["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "code": code,
                    "redirect_uri": f"{get_base_url()}/api/v1/auth/callback/linuxdo",
                },
                headers={"Accept": "application/json"},
                timeout=30.0
            )
            token_response.raise_for_status()
            token_data = token_response.json()
        except Exception as e:
            print(f"Token exchange error: {e}")
            return RedirectResponse(url="/login?error=oauth_error&message=token_exchange_failed")
        
        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(url="/login?error=oauth_error&message=no_access_token")
        
        # Get user info
        try:
            userinfo_response = await client.get(
                config["userinfo_url"],
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                },
                timeout=30.0
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()
        except Exception as e:
            print(f"Userinfo error: {e}")
            return RedirectResponse(url="/login?error=oauth_error&message=userinfo_failed")
    
    # Extract user info (Discourse format)
    oauth_id = str(userinfo.get("id") or userinfo.get("sub"))
    username = userinfo.get("username") or userinfo.get("name") or f"user_{oauth_id}"
    email = userinfo.get("email") or f"{username}@linuxdo.oauth"
    
    if not oauth_id:
        return RedirectResponse(url="/login?error=oauth_error&message=no_user_id")
    
    # Find or create user
    user_repo = UserRepository(db)
    
    # Try to find user by OAuth ID
    user = await user_repo.get_by_oauth("linuxdo", oauth_id)
    
    if not user:
        # Try to find by email
        user = await user_repo.get_by_email(email)
        
        if user:
            # Link OAuth to existing user
            user.oauth_provider = "linuxdo"
            user.oauth_id = oauth_id
        else:
            # Check if registration is allowed before creating new user
            allow_registration = await settings_repo.get('allow_registration')
            has_users = await user_repo.has_any_users()
            
            # Only allow new OAuth registration if:
            # 1. Registration is enabled, OR
            # 2. No users exist (first user setup)
            if allow_registration != 'true' and has_users:
                return RedirectResponse(url="/login?error=oauth_error&message=registration_disabled")
            
            # Create new user
            user = await user_repo.create_oauth_user(
                username=username,
                email=email,
                oauth_provider="linuxdo",
                oauth_id=oauth_id
            )
    
    await db.commit()
    
    # Generate tokens
    app_access_token = create_access_token({"sub": str(user.id), "token_version": user.token_version})
    refresh_token = create_refresh_token({"sub": str(user.id), "token_version": user.token_version})
    
    # Redirect to login page with tokens (login page handles OAuth callback)
    redirect_url = f"/login?oauth_success=true&access_token={app_access_token}&refresh_token={refresh_token}"
    return RedirectResponse(url=redirect_url)


def get_base_url() -> str:
    """Get the base URL for callbacks."""
    import os
    return os.environ.get("BASE_URL", "https://rss.8y.cx")
