"""Authentication service for user management."""
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthResponse, UserCreate, UserLogin, UserResponse


class AuthService:
    """Service for authentication operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def register(self, data: UserCreate) -> AuthResponse:
        """Register a new user."""
        # Check if username exists
        if await self.user_repo.exists_by_username(data.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists"
            )
        
        # Check if email exists
        if await self.user_repo.exists_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists"
            )
        
        # Create user
        user = await self.user_repo.create(
            username=data.username,
            email=data.email,
            password=data.password
        )
        
        # Generate tokens
        tokens = self._generate_tokens(user)
        
        return AuthResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=UserResponse.model_validate(user)
        )

    async def login(self, data: UserLogin) -> AuthResponse:
        """Authenticate user and return tokens."""
        user = await self.user_repo.get_by_username(data.username)
        
        if not user or not user.verify_password(data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled"
            )
        
        tokens = self._generate_tokens(user)
        
        return AuthResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=UserResponse.model_validate(user)
        )

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token."""
        payload = decode_token(refresh_token)
        
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user_id = payload.get("sub")
        token_version = payload.get("token_version")
        
        user = await self.user_repo.get_by_id(int(user_id))
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Check token version (invalidated if password changed)
        if user.token_version != token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been invalidated"
            )
        
        tokens = self._generate_tokens(user)
        
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer"
        }

    async def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        """Change user password."""
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if not user.verify_password(current_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )
        
        await self.user_repo.update_password(user, new_password)

    async def get_current_user(self, user_id: int) -> User:
        """Get current user by ID."""
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user

    def _generate_tokens(self, user: User) -> dict:
        """Generate access and refresh tokens for user."""
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "token_version": user.token_version
        }
        
        return {
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data)
        }
