from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints
from app.modules.movies.schemas import GenreRead

class GenreInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
