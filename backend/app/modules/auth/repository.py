from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, RefreshToken

class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def user(self, user_id: UUID, lock: bool = False) -> User | None:
        query = select(User).where(User.id == user_id).execution_options(populate_existing=True)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def token(self, digest: str) -> RefreshToken | None:
        return await self.session.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest).execution_options(populate_existing=True))

    async def live_family(self, user_id: UUID, family_id: UUID, now) -> bool:
        return await self.session.scalar(select(RefreshToken.id).where(
            RefreshToken.user_id == user_id, RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None), RefreshToken.consumed_at.is_(None),
            RefreshToken.expires_at > now).limit(1)) is not None

    async def revoke(self, user_id: UUID, family_id: UUID, now) -> None:
        await self.session.execute(update(RefreshToken).where(RefreshToken.user_id == user_id,
            RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now))
