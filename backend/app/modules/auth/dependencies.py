from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.core.runtime import get_db
from app.models import User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security import decode_access
from app.modules.auth.service import AuthService

bearer = HTTPBearer(auto_error=False)

def get_auth_service(request: Request, session: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(session, request.app.state.settings)

async def current_user(request: Request, session: Annotated[AsyncSession, Depends(get_db)],
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
    if credentials is None:
        raise ApplicationError("authentication_required", "Authentication required", 401)
    user_id, family_id = decode_access(request.app.state.settings, credentials.credentials)
    repo = AuthRepository(session)
    user = await repo.user(user_id)
    if user is None or user.status != "active" or not await repo.live_family(user_id, family_id, datetime.now(timezone.utc)):
        raise ApplicationError("invalid_access_token", "Invalid or expired access token", 401)
    return user

async def require_admin(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != "ADMIN":
        raise ApplicationError("forbidden", "Administrator access required", 403)
    return user


async def optional_user(request: Request, session: Annotated[AsyncSession, Depends(get_db)],
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User | None:
    if credentials is None:
        return None
    return await current_user(request, session, credentials)
