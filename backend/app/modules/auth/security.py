import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from starlette.concurrency import run_in_threadpool
from app.core.config import Settings
from app.core.errors import ApplicationError

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, type=Type.ID)

async def hash_password(password: str) -> str:
    return await run_in_threadpool(hasher.hash, password)

async def verify_password(encoded: str, password: str) -> bool:
    def verify() -> bool:
        try:
            return hasher.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            return False
    return await run_in_threadpool(verify)

def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def signing_key(settings: Settings) -> str:
    if settings.jwt_secret is None or len(settings.jwt_secret.get_secret_value().encode()) < 32 or settings.jwt_secret.get_secret_value().startswith("replace-"):
        raise ApplicationError("auth_unavailable", "Authentication is not configured", 503)
    return settings.jwt_secret.get_secret_value()

def access_token(settings: Settings, user_id: UUID, family_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "sid": str(family_id), "jti": str(uuid4()),
        "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience}, signing_key(settings), algorithm="HS256")

def decode_access(settings: Settings, token: str) -> tuple[UUID, UUID]:
    key = signing_key(settings)
    try:
        payload = jwt.decode(token, key, algorithms=["HS256"], issuer=settings.jwt_issuer,
            audience=settings.jwt_audience, options={"require": ["sub", "sid", "jti", "iat", "exp", "iss", "aud"]})
        return UUID(payload["sub"]), UUID(payload["sid"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError, AttributeError):
        raise ApplicationError("invalid_access_token", "Invalid or expired access token", 401) from None

def new_refresh() -> str:
    return secrets.token_urlsafe(48)
