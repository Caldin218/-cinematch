from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import ApiResponse, Page
from app.core.runtime import get_db
from app.models import User
from app.modules.auth.dependencies import current_user
from app.modules.interactions.schemas import (
    CollectionRead,
    HistoryRead,
    InteractionPage,
    MovieInput,
    MovieInteractionRead,
    RatingInput,
    RatingRead,
    RatingValue,
    ViewInput,
    ViewRead,
)
from app.modules.interactions.service import InteractionService
from app.modules.movies.schemas import Identifier


def private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/interactions", tags=["interactions"], dependencies=[Depends(private_response)])


def get_service(session: Annotated[AsyncSession, Depends(get_db)]) -> InteractionService:
    return InteractionService(session)


Service = Annotated[InteractionService, Depends(get_service)]
CurrentUser = Annotated[User, Depends(current_user)]
Paging = Annotated[InteractionPage, Query()]


@router.post("/view", response_model=ApiResponse[ViewRead])
async def view(data: ViewInput, user: CurrentUser, service: Service) -> ApiResponse[ViewRead]:
    return ApiResponse(data=await service.view(user.id, data))


@router.post("/rating", status_code=201, response_model=ApiResponse[RatingRead])
async def rate(data: RatingInput, user: CurrentUser, service: Service) -> ApiResponse[RatingRead]:
    return ApiResponse(data=await service.create_rating(user.id, data))


@router.put("/rating/{movie_id}", response_model=ApiResponse[RatingRead])
async def update_rating(movie_id: Identifier, data: RatingValue, user: CurrentUser, service: Service) -> ApiResponse[RatingRead]:
    return ApiResponse(data=await service.update_rating(user.id, movie_id, data))


@router.get("/history", response_model=ApiResponse[Page[HistoryRead]])
async def history(user: CurrentUser, service: Service, page: Paging) -> ApiResponse[Page[HistoryRead]]:
    return ApiResponse(data=await service.history(user.id, page))


@router.post("/favorites", status_code=204)
async def favorite(data: MovieInput, user: CurrentUser, service: Service) -> Response:
    await service.change_collection(user.id, data.movie_id, "favorites", True)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.delete("/favorites/{movie_id}", status_code=204)
async def remove_favorite(movie_id: Identifier, user: CurrentUser, service: Service) -> Response:
    await service.change_collection(user.id, movie_id, "favorites", False)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/favorites", response_model=ApiResponse[Page[CollectionRead]])
async def favorites(user: CurrentUser, service: Service, page: Paging) -> ApiResponse[Page[CollectionRead]]:
    return ApiResponse(data=await service.collection(user.id, "favorites", page))


@router.post("/watchlist", status_code=204)
async def watchlist_add(data: MovieInput, user: CurrentUser, service: Service) -> Response:
    await service.change_collection(user.id, data.movie_id, "watchlist", True)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.delete("/watchlist/{movie_id}", status_code=204)
async def watchlist_remove(movie_id: Identifier, user: CurrentUser, service: Service) -> Response:
    await service.change_collection(user.id, movie_id, "watchlist", False)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/watchlist", response_model=ApiResponse[Page[CollectionRead]])
async def watchlist(user: CurrentUser, service: Service, page: Paging) -> ApiResponse[Page[CollectionRead]]:
    return ApiResponse(data=await service.collection(user.id, "watchlist", page))

@router.get("/movies/{movie_id}", response_model=ApiResponse[MovieInteractionRead])
async def movie_interactions(movie_id: Identifier, user: CurrentUser, service: Service):
    return ApiResponse(data=await service.movie_state(user.id, movie_id))
