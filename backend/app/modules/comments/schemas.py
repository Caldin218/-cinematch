from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class CommentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]

class CommentRead(BaseModel):
    id: int
    movie_id: int
    username: str
    body: str
    created_at: datetime
    likes: int
    liked: bool

