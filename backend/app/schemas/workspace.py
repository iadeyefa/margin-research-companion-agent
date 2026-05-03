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


class WorkspaceBriefRead(ApiModel):
    id: int
    mode: str
    style: str
    title: str
    body: str
    source_papers: List[ResearchPaper]
    created_at: datetime


class WorkspaceBriefCreate(ApiModel):
    mode: str
    style: str = "balanced"
    title: str
    body: str
    source_papers: List[ResearchPaper] = []


class WorkspaceStateRead(ApiModel):
    state_key: str
    value: dict
    updated_at: datetime


class WorkspaceStateUpdate(ApiModel):
    value: dict


class PaperNoteRead(ApiModel):
    source: str
    external_id: str
    note: str
    updated_at: datetime


class PaperNoteUpdate(ApiModel):
    note: str


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
    briefs: List[WorkspaceBriefRead]
    state: List[WorkspaceStateRead]
    paper_notes: List[PaperNoteRead]


class LibraryPaper(ResearchPaper):
    workspace_id: int
    workspace_title: str
    saved_at: datetime
