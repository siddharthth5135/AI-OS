import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    """
    Repository for asynchronous database operations on the User model.
    """

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Retrieve a user by their UUID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Retrieve a user by their email address."""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """Retrieve a user by their username."""
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, username: str, email: str, password_hash: str) -> User:
        """Create a new user record."""
        user = User(
            username=username,
            email=email,
            password_hash=password_hash
        )
        db.add(user)
        await db.flush()  # Flush to get the ID without committing yet
        await db.refresh(user)
        return user

    @staticmethod
    async def update_last_login(db: AsyncSession, user_id: uuid.UUID) -> None:
        """Update the last_login_at timestamp for a user."""
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )

    @staticmethod
    async def deactivate(db: AsyncSession, user_id: uuid.UUID) -> None:
        """Set a user's is_active status to False."""
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_active=False)
        )
