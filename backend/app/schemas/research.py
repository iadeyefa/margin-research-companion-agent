from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ApiModel


class ResearchPaper(ApiModel):
    source: str
    external_id: str
    title: str
    abstract: Optional[str] = None
    abstract_override: Optional[str] = None
    authors: List[str] = []
    venue: Optional[str] = None
    year: Optional[int] = None
    publication_date: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    citation_count: Optional[int] = None
    open_access: Optional[bool] = None


class ResearchSearchRequest(ApiModel):
    query: str
    limit_per_source: int = 5
    sources: Optional[List[str]] = None
    workspace_id: Optional[int] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    open_access_only: bool = False
    sort_by: str = "relevance"


class ResearchSearchResponse(ApiModel):
    query: str
    results: List[ResearchPaper]
    source_errors: dict


class ResearchSynthesisRequest(ApiModel):
    mode: str
    style: str = "balanced"
    question: Optional[str] = None
    instructions: Optional[str] = None
    papers: List[ResearchPaper]


class ResearchSynthesisResponse(ApiModel):
    mode: str
    response: str


class ResearchReadingPathRequest(ApiModel):
    objective: Optional[str] = None
    preferences: Optional[str] = None
    papers: List[ResearchPaper]


class ReadingPathStep(ApiModel):
    order: int
    title: str
    source: str
    external_id: str
    rationale: str


class ResearchReadingPathResponse(ApiModel):
    objective: str
    overview: str
    steps: List[ReadingPathStep]


class ResearchExportRequest(ApiModel):
    format: str
    papers: List[ResearchPaper]


class ResearchExportResponse(ApiModel):
    format: str
    content: str


class CollaborateChatMessage(ApiModel):
    role: str
    content: str = Field(..., max_length=6000)

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"user", "assistant"}:
            raise ValueError('role must be "user" or "assistant"')
        return cleaned

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def nonempty_user_turn(self):
        if self.role == "user" and not self.content:
            raise ValueError("user messages cannot be empty")
        return self


class CollaborativeSearchIntent(ApiModel):
    """Resolved search draft after the dialog phase."""

    query: str
    sources: List[str]
    limit_per_source: int = 5
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    open_access_only: bool = False
    sort_by: str = "relevance"

    @field_validator("sort_by")
    @classmethod
    def sort_ok(cls, value: str) -> str:
        cleaned = (value or "relevance").strip().lower()
        if cleaned not in {"relevance", "newest", "most_cited"}:
            return "relevance"
        return cleaned


class ResearchSearchCollaborateRequest(ApiModel):
    messages: List[CollaborateChatMessage] = Field(default_factory=list)
    workspace_id: Optional[int] = None
    desired_catalog_count: int = Field(4, ge=1, le=5)


class ResearchSearchCollaborateResponse(ApiModel):
    phase: str
    assistant_message: str
    quick_replies: List[str] = []
    search: Optional[CollaborativeSearchIntent] = None


class AgentRunStep(ApiModel):
    name: str
    detail: str


class ResearchAgentRunRequest(ApiModel):
    objective: str
    workspace_id: Optional[int] = None
    query_hint: Optional[str] = None
    # If omitted or empty, catalogs are inferred from objective / query_hint via the model (or heuristics).
    sources: Optional[List[str]] = None
    limit_per_source: int = 4
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    open_access_only: bool = False
    sort_by: str = "relevance"
    mode: str = "summary"
    style: str = "balanced"
    question: Optional[str] = None
    instructions: Optional[str] = None
    max_iterations: int = 2
    min_papers: int = 4
    max_papers_for_synthesis: int = 8


class ResearchAgentRunResponse(ApiModel):
    objective: str
    iterations: int
    final_query: str
    selected_paper_count: int
    selected_papers: List[ResearchPaper]
    sources_used: List[str]
    source_errors: dict
    synthesis_mode: str
    synthesis: str
    citation_validation: str
    steps: List[AgentRunStep]
    saved_brief_id: Optional[int] = None
