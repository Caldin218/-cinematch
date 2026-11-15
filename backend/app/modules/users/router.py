from typing import Annotated
from fastapi import APIRouter, Depends, Response
from app.core.api import ApiResponse
from app.models import User
from app.modules.auth.dependencies import current_user
from app.modules.auth.schemas import PublicUser

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=ApiResponse[PublicUser])
async def me(response: Response, user: Annotated[User, Depends(current_user)]):
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse(data=PublicUser.model_validate(user))
