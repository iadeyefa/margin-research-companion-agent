from app.schemas.common import ApiModel


class ResearchPaper(ApiModel):
    source: str
    external_id: str
    title: str
    abstract: str | None = None
    authors: list[str] = []
    venue: str | None = None
    year: int | None = None
    publication_date: str | None = None
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    citation_count: int | None = None
    open_access: bool | None = None


class ResearchSearchRequest(ApiModel):
    query: str
    limit_per_source: int = 5
    sources: list[str] | None = None
    workspace_id: int | None = None


class ResearchSearchResponse(ApiModel):
    query: str
    results: list[ResearchPaper]
    source_errors: dict[str, str]


class ResearchSynthesisRequest(ApiModel):
    mode: str
    question: str | None = None
    papers: list[ResearchPaper]


class ResearchSynthesisResponse(ApiModel):
    mode: str
    response: str


class ResearchReadingPathRequest(ApiModel):
    objective: str | None = None
    papers: list[ResearchPaper]


class ReadingPathStep(ApiModel):
    order: int
    title: str
    source: str
    external_id: str
    rationale: str


class ResearchReadingPathResponse(ApiModel):
    objective: str
    overview: str
    steps: list[ReadingPathStep]


class ResearchExportRequest(ApiModel):
    format: str
    papers: list[ResearchPaper]


class ResearchExportResponse(ApiModel):
    format: str
    content: str
