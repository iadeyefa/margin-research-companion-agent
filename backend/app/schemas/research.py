from typing import List, Optional

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
    question: Optional[str] = None
    papers: List[ResearchPaper]


class ResearchSynthesisResponse(ApiModel):
    mode: str
    response: str


class ResearchReadingPathRequest(ApiModel):
    objective: Optional[str] = None
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
