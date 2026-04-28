from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.research_search import ResearchSearch
from app.schemas.research import ResearchExportRequest, ResearchExportResponse
from app.schemas.research import ResearchReadingPathRequest, ResearchReadingPathResponse
from app.schemas.research import ResearchSearchRequest, ResearchSearchResponse
from app.schemas.research import ResearchSynthesisRequest, ResearchSynthesisResponse
from app.services.research_export import export_bibtex, export_markdown
from app.services.research_llm import synthesize_research
from app.services.research_reading_path import build_reading_path
from app.services.research_sources import SUPPORTED_SOURCES, search_publications


router = APIRouter(prefix="/research", tags=["research"])


@router.post("/search", response_model=ResearchSearchResponse)
async def search_research(payload: ResearchSearchRequest, db: Session = Depends(get_db)):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query is required")

    if payload.sources:
        invalid_sources = sorted(set(payload.sources) - set(SUPPORTED_SOURCES))
        if invalid_sources:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported sources: {', '.join(invalid_sources)}",
            )

    results, source_errors = await search_publications(
        query=query,
        limit_per_source=max(1, min(payload.limit_per_source, 10)),
        sources=payload.sources,
        year_from=payload.year_from,
        year_to=payload.year_to,
        open_access_only=payload.open_access_only,
        sort_by=payload.sort_by,
    )
    db.add(
        ResearchSearch(
            workspace_id=payload.workspace_id,
            query=query,
            sources=payload.sources or list(SUPPORTED_SOURCES),
            result_count=len(results),
        )
    )
    db.commit()
    return ResearchSearchResponse(query=query, results=results, source_errors=source_errors)


@router.post("/synthesize", response_model=ResearchSynthesisResponse)
async def synthesize(payload: ResearchSynthesisRequest):
    mode = payload.mode.strip().lower()
    if mode not in {"summary", "compare", "question"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported synthesis mode")

    response = await synthesize_research(
        mode=mode,
        papers=[paper.model_dump() for paper in payload.papers],
        question=payload.question,
    )
    return ResearchSynthesisResponse(mode=mode, response=response)


@router.post("/reading-path", response_model=ResearchReadingPathResponse)
async def reading_path(payload: ResearchReadingPathRequest):
    result = await build_reading_path(
        objective=payload.objective,
        papers=[paper.model_dump() for paper in payload.papers],
    )
    return ResearchReadingPathResponse(**result)


@router.post("/export", response_model=ResearchExportResponse)
async def export_research(payload: ResearchExportRequest):
    export_format = payload.format.strip().lower()
    papers = [paper.model_dump() for paper in payload.papers]

    if export_format == "bibtex":
        return ResearchExportResponse(format="bibtex", content=export_bibtex(papers))
    if export_format == "markdown":
        return ResearchExportResponse(format="markdown", content=export_markdown(papers))

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format")
