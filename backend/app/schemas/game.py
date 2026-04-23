from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel


class PlayerStatRead(ApiModel):
    id: int
    game_id: int
    player_name: str
    points: int
    rebounds: int | None = None
    assists: int | None = None
    created_at: datetime


class GameCreate(ApiModel):
    team_id: int
    opponent: str
    score: int
    opponent_score: int
    date: datetime
    venue: str | None = None
    game_status: str = "completed"


class GameRead(ApiModel):
    id: int
    team_id: int
    opponent: str
    score: int
    opponent_score: int
    date: datetime
    venue: str | None = None
    game_status: str
    created_at: datetime
    player_stats: list[PlayerStatRead] = Field(default_factory=list)
