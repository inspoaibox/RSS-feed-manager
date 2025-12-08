"""User repository for database operations."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository for User database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, username: str, email: str, password: str) -> User:
        """Create a new user."""
        user = User(username=username, email=email, token_version=0)
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
