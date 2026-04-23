from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.game import GameRead


class TeamCreate(ApiModel):
    user_id: int
    team_name: str
    sport: str


class TeamRead(ApiModel):
    id: int
    user_id: int
    team_name: str
    sport: str
    created_at: datetime
    games: list[GameRead] = Field(default_factory=list)
