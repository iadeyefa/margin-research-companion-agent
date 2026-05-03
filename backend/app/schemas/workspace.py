from datetime import datetime
from typing import List, Optional

from app.schemas.common import ApiModel
from app.schemas.research import ResearchPaper


class WorkspaceCreate(ApiModel):
    title: str


class WorkspaceUpdate(ApiModel):
    title: Optional[str] = None
    notes: Optional[str] = None


class SavedPaperUpdate(ApiModel):
    abstract_override: Optional[str] = None


class SearchHistoryRead(ApiModel):
    id: int
    query: str
    sources: List[str]
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
    saved_papers: List[ResearchPaper]
    searches: List[SearchHistoryRead]


class LibraryPaper(ResearchPaper):
    workspace_id: int
    workspace_title: str
    saved_at: datetime
