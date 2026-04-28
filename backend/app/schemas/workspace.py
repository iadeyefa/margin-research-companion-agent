from datetime import datetime

from app.schemas.common import ApiModel
from app.schemas.research import ResearchPaper


class WorkspaceCreate(ApiModel):
    title: str


class WorkspaceUpdate(ApiModel):
    title: str | None = None
    notes: str | None = None


class SearchHistoryRead(ApiModel):
    id: int
    query: str
    sources: list[str]
    result_count: int
    created_at: datetime


class WorkspaceSummary(ApiModel):
    id: int
    title: str
    notes: str
    saved_paper_count: int
    search_count: int
    created_at: datetime
    updated_at: datetime


class WorkspaceDetail(WorkspaceSummary):
    saved_papers: list[ResearchPaper]
    searches: list[SearchHistoryRead]
