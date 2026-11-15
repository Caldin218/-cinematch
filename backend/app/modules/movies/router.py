from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import ApiResponse, Page
from app.core.runtime import get_db
from app.models import User
from app.modules.auth.dependencies import optional_user, require_admin
from app.modules.movies.schemas import (
    CatalogQuery,
    Identifier,
    MovieCreate,
    MovieRead,
    MovieUpdate,
)
from app.modules.movies.service import MovieService

router = APIRouter(tags=["movies"])

def get_service(session: Annotated[AsyncSession, Depends(get_db)]) -> MovieService:
    return MovieService(session)

Service = Annotated[MovieService, Depends(get_service)]

@router.get("/movies", response_model=ApiResponse[Page[MovieRead]])
@router.get("/movies/search", response_model=ApiResponse[Page[MovieRead]])
async def movies(service: Service, query: Annotated[CatalogQuery, Query()], response: Response, user: Annotated[User | None, Depends(optional_user)]) -> ApiResponse[Page[MovieRead]]:
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse(data=await service.listing(query, user.id if user else None))

@router.get("/movies/{movie_id}", response_model=ApiResponse[MovieRead])
async def movie(movie_id: Identifier, service: Service) -> ApiResponse[MovieRead]:
    return ApiResponse(data=await service.detail(movie_id))

@router.post("/admin/movies", status_code=201, response_model=ApiResponse[MovieRead], dependencies=[Depends(require_admin)])
async def create_movie(data: MovieCreate, service: Service) -> ApiResponse[MovieRead]:
    return ApiResponse(data=await service.save(data))

@router.patch("/admin/movies/{movie_id}", response_model=ApiResponse[MovieRead], dependencies=[Depends(require_admin)])
async def update_movie(movie_id: Identifier, data: MovieUpdate, service: Service) -> ApiResponse[MovieRead]:
    return ApiResponse(data=await service.save(data, movie_id))

@router.delete("/admin/movies/{movie_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_movie(movie_id: Identifier, service: Service) -> Response:
    await service.delete(movie_id)
    return Response(status_code=204)
