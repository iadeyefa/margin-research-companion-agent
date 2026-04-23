from datetime import datetime

from app.schemas.common import ApiModel


class ChatRequest(ApiModel):
    message: str
    user_id: int
    team_id: int | None = None


class AnalysisRead(ApiModel):
    id: int
    user_id: int
    team_id: int | None = None
    question: str
    response: str
    created_at: datetime
