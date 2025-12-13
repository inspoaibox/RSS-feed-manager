"""User repository for database operations."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository for User database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, username: str, email: str, password: str, is_admin: bool = False) -> User:
        """Create a new user."""
        user = User(username=username, email=email, token_version=0, is_admin=is_admin)
        user.set_password(password)
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update_password(self, user: User, new_password: str) -> User:
        """Update user password."""
        user.set_password(new_password)
        await self.session.flush()
        return user

    async def exists_by_username(self, username: str) -> bool:
        """Check if username exists."""
        result = await self.session.execute(
            select(User.id).where(User.username == username).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def exists_by_email(self, email: str) -> bool:
        """Check if email exists."""
        result = await self.session.execute(
            select(User.id).where(User.email == email).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def count_users(self) -> int:
        """Count total users."""
        from sqlalchemy import func
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar() or 0

    async def has_any_users(self) -> bool:
        """Check if any users exist."""
        result = await self.session.execute(select(User.id).limit(1))
        return result.scalar_one_or_none() is not None

    async def get_all_users(self) -> list[User]:
        """Get all users (admin only)."""
        result = await self.session.execute(select(User).order_by(User.id))
        return list(result.scalars().all())

    async def get_by_oauth(self, provider: str, oauth_id: str) -> User | None:
        """Get user by OAuth provider and ID."""
        result = await self.session.execute(
            select(User).where(
                User.oauth_provider == provider,
                User.oauth_id == oauth_id
            )
        )
        return result.scalar_one_or_none()

    async def create_oauth_user(
        self,
        username: str,
        email: str,
        oauth_provider: str,
        oauth_id: str
    ) -> User:
        """Create a new user from OAuth login."""
        import secrets
        
        # Ensure unique username
        base_username = username
        counter = 1
        while await self.exists_by_username(username):
            username = f"{base_username}_{counter}"
            counter += 1
        
        # Generate random password (user won't use it, they'll login via OAuth)
        random_password = secrets.token_urlsafe(32)
        
        user = User(
            username=username,
            email=email,
            token_version=0,
            oauth_provider=oauth_provider,
            oauth_id=oauth_id
        )
        user.set_password(random_password)
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_last_login(self, user: User) -> None:
        """Update user's last login time."""
        from datetime import datetime, timezone
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()
