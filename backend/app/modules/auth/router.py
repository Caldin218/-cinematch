from typing import Annotated
from fastapi import APIRouter, Depends, Response
from app.core.api import ApiResponse
from app.modules.auth.dependencies import get_auth_service
from app.modules.auth.limiter import AuthLimiter, get_limiter
from app.modules.auth.schemas import Registration, Credentials, RefreshInput, PublicUser, Tokens
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
Service = Annotated[AuthService, Depends(get_auth_service)]
Limiter = Annotated[AuthLimiter, Depends(get_limiter)]

@router.post("/register", status_code=201, response_model=ApiResponse[PublicUser])
async def register(data: Registration, service: Service, limiter: Limiter):
    await limiter.check("register", str(data.email))
    return ApiResponse(data=PublicUser.model_validate(await service.register(data)))

@router.post("/login", response_model=ApiResponse[Tokens])
async def login(data: Credentials, response: Response, service: Service, limiter: Limiter):
    await limiter.check("login", str(data.email))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return ApiResponse(data=await service.login(data))

@router.post("/refresh", response_model=ApiResponse[Tokens])
async def refresh(data: RefreshInput, response: Response, service: Service, limiter: Limiter):
    await limiter.check("refresh")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return ApiResponse(data=await service.rotate(data.refresh_token.get_secret_value()))

@router.post("/logout", status_code=204)
async def logout(data: RefreshInput, service: Service, limiter: Limiter):
    await limiter.check("logout")
    await service.logout(data.refresh_token.get_secret_value())
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
