from typing import Annotated
from fastapi import APIRouter, Depends, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.api import ApiResponse
from app.core.runtime import get_db, get_redis
from app.modules.auth.dependencies import require_admin
from app.modules.movies.schemas import Identifier
from app.modules.genres.schemas import GenreInput, GenreRead
from app.modules.genres.service import GenreService

router = APIRouter(tags=["genres"])

def get_service(session: Annotated[AsyncSession, Depends(get_db)], redis: Annotated[Redis, Depends(get_redis)]) -> GenreService:
    return GenreService(session, redis)

Service = Annotated[GenreService, Depends(get_service)]

@router.get("/genres", response_model=ApiResponse[list[GenreRead]])
async def genres(service: Service) -> ApiResponse[list[GenreRead]]:
    return ApiResponse(data=await service.listing())

@router.post("/admin/genres", status_code=201, response_model=ApiResponse[GenreRead], dependencies=[Depends(require_admin)])
async def create_genre(data: GenreInput, service: Service) -> ApiResponse[GenreRead]:
    return ApiResponse(data=await service.change(data))

@router.patch("/admin/genres/{genre_id}", response_model=ApiResponse[GenreRead], dependencies=[Depends(require_admin)])
async def update_genre(genre_id: Identifier, data: GenreInput, service: Service) -> ApiResponse[GenreRead]:
    return ApiResponse(data=await service.change(data, genre_id))

@router.delete("/admin/genres/{genre_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_genre(genre_id: Identifier, service: Service) -> Response:
    await service.change(None, genre_id)
    return Response(status_code=204)
