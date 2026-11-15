from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Settings
from app.core.errors import ApplicationError
from app.models import User, RefreshToken
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import Registration, Credentials, Tokens
from app.modules.auth.security import hash_password, verify_password, token_hash, new_refresh, access_token, signing_key

class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session, self.settings = session, settings
        self.repo = AuthRepository(session)

    async def register(self, data: Registration) -> User:
        encoded = await hash_password(data.password.get_secret_value())
        user = User(email=str(data.email), display_name=data.display_name, password_hash=encoded, role="USER")
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise ApplicationError("email_exists", "Email is already registered", 409) from None
            raise
        await self.session.refresh(user)
        return user

    async def issue(self, user: User, family_id=None, expires_at=None) -> Tokens:
        family_id = family_id or uuid4()
        expires_at = expires_at or datetime.now(timezone.utc) + timedelta(days=self.settings.refresh_token_days)
        encoded_access = access_token(self.settings, user.id, family_id)
        raw = new_refresh()
        self.session.add(RefreshToken(user_id=user.id, family_id=family_id,
            token_hash=token_hash(raw), expires_at=expires_at))
        await self.session.commit()
        return Tokens(access_token=encoded_access, refresh_token=raw,
                      expires_in=self.settings.access_token_minutes * 60)

    async def login(self, data: Credentials) -> Tokens:
        signing_key(self.settings)
        user = await self.repo.by_email(str(data.email))
        if user is None:
            # Perform the same Argon2 work even for unknown identities.
            await hash_password(data.password.get_secret_value())
            raise ApplicationError("invalid_credentials", "Invalid email or password", 401)
        original_hash = user.password_hash
        valid = await verify_password(original_hash, data.password.get_secret_value())
        user = await self.repo.user(user.id, lock=True)
        if not valid or user is None or user.status != "active" or user.password_hash != original_hash:
            raise ApplicationError("invalid_credentials", "Invalid email or password", 401)
        return await self.issue(user)

    async def rotate(self, raw: str) -> Tokens:
        signing_key(self.settings)
        token = await self.repo.token(token_hash(raw))
        if token is None:
            raise ApplicationError("invalid_refresh_token", "Invalid refresh token", 401)
        user = await self.repo.user(token.user_id, lock=True)
        token = await self.repo.token(token_hash(raw))
        now = datetime.now(timezone.utc)
        if token.consumed_at is not None:
            await self.repo.revoke(token.user_id, token.family_id, now)
            await self.session.commit()
            raise ApplicationError("refresh_reuse", "Refresh token reuse detected; sign in again", 401)
        if token.revoked_at is not None or token.expires_at <= now or user is None or user.status != "active":
            raise ApplicationError("invalid_refresh_token", "Invalid refresh token", 401)
        token.consumed_at = now
        return await self.issue(user, token.family_id, token.expires_at)

    async def logout(self, raw: str) -> None:
        token = await self.repo.token(token_hash(raw))
        if token is not None:
            await self.repo.user(token.user_id, lock=True)
            await self.repo.revoke(token.user_id, token.family_id, datetime.now(timezone.utc))
            await self.session.commit()
