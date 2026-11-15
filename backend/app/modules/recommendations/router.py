from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import ApiResponse
from app.core.runtime import get_db, get_redis
from app.models import User
from app.modules.auth.dependencies import current_user
from app.modules.interactions.router import private_response

from .schemas import RecommendationRead, RefreshRead
from .service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"],
                   dependencies=[Depends(private_response)])


def get_service(request: Request, session: Annotated[AsyncSession, Depends(get_db)],
                redis=Depends(get_redis)) -> RecommendationService:
    return RecommendationService(session, redis, request.app.state.settings)


Service = Annotated[RecommendationService, Depends(get_service)]
CurrentUser = Annotated[User, Depends(current_user)]


@router.get("/me", response_model=ApiResponse[RecommendationRead])
async def recommendations(user: CurrentUser, service: Service,
        n: Annotated[int | None, Query(ge=1, le=100)] = None):
    return ApiResponse(data=await service.get(user.id, n))


@router.post("/refresh", status_code=202, response_model=ApiResponse[RefreshRead])
async def refresh(user: CurrentUser, service: Service, response: Response):
    response.headers["Location"] = "/api/v1/recommendations/me"
    return ApiResponse(data=await service.refresh(user.id))
