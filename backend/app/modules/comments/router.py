from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import ApiResponse, Page, Pagination
from app.core.runtime import get_db
from app.models import User
from app.modules.auth.dependencies import current_user, optional_user
from app.modules.movies.schemas import Identifier

from .schemas import CommentInput, CommentRead
from .service import CommentService

router = APIRouter(tags=["comments"])
Session = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]

def get_service(session: Session) -> CommentService:
    return CommentService(session)

Service = Annotated[CommentService, Depends(get_service)]

@router.get("/movies/{movie_id}/comments", response_model=ApiResponse[Page[CommentRead]])
async def comments(movie_id: Identifier, service: Service, response: Response,
        paging: Annotated[Pagination, Query()], user: Annotated[User | None, Depends(optional_user)]):
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse(data=await service.listing(movie_id, paging, user))

@router.post("/movies/{movie_id}/comments", status_code=201, response_model=ApiResponse[CommentRead])
async def add_comment(movie_id: Identifier, data: CommentInput, service: Service, user: CurrentUser, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse(data=await service.add(movie_id, user, data.body))

@router.post("/comments/{comment_id}/like", status_code=204)
async def like(comment_id: Identifier, service: Service, user: CurrentUser):
    await service.like(comment_id, user, True)
    return Response(status_code=204, headers={"Cache-Control":"no-store"})

@router.delete("/comments/{comment_id}/like", status_code=204)
async def unlike(comment_id: Identifier, service: Service, user: CurrentUser):
    await service.like(comment_id, user, False)
    return Response(status_code=204, headers={"Cache-Control":"no-store"})
