from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.research_search import ResearchSearch
from app.models.research_workspace import ResearchWorkspace
from app.models.research_workspace_brief import ResearchWorkspaceBrief
from app.schemas.research import AgentRunStep, ResearchAgentRunRequest, ResearchAgentRunResponse
from app.schemas.research import ResearchExportRequest, ResearchExportResponse
from app.schemas.research import ResearchReadingPathRequest, ResearchReadingPathResponse
from app.schemas.research import ResearchSearchCollaborateRequest, ResearchSearchCollaborateResponse
from app.schemas.research import ResearchSearchRequest, ResearchSearchResponse
from app.schemas.research import ResearchSynthesisRequest, ResearchSynthesisResponse
from app.services.research_agent import run_research_agent
from app.services.research_export import export_bibtex, export_markdown
from app.services.research_llm import synthesize_research
from app.services.research_reading_path import build_reading_path
from app.services.research_search_collaboration import collaborate_search_turn
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


@router.post("/search/collaborate", response_model=ResearchSearchCollaborateResponse)
async def search_collaborate(payload: ResearchSearchCollaborateRequest):
    msgs = [{"role": m.role, "content": m.content} for m in payload.messages[-40:]]
    if msgs and msgs[-1]["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The transcript must end with your latest reply (role=user), or send messages: [] to open the session.",
        )
    try:
        raw = await collaborate_search_turn(msgs, desired_catalog_count=payload.desired_catalog_count)
        return ResearchSearchCollaborateResponse.model_validate(raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/synthesize", response_model=ResearchSynthesisResponse)
async def synthesize(payload: ResearchSynthesisRequest):
    mode = payload.mode.strip().lower()
    if mode not in {"summary", "compare", "question"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported synthesis mode")

    response = await synthesize_research(
        mode=mode,
        papers=[paper.model_dump() for paper in payload.papers],
        style=payload.style,
        question=payload.question,
        instructions=payload.instructions,
    )
    return ResearchSynthesisResponse(mode=mode, response=response)


@router.post("/reading-path", response_model=ResearchReadingPathResponse)
async def reading_path(payload: ResearchReadingPathRequest):
    result = await build_reading_path(
        objective=payload.objective,
        preferences=payload.preferences,
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


@router.post("/agent/run", response_model=ResearchAgentRunResponse)
async def run_agent(payload: ResearchAgentRunRequest, db: Session = Depends(get_db)):
    objective = payload.objective.strip()
    if not objective:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Objective is required")
    if payload.sources:
        invalid_sources = sorted(set(payload.sources) - set(SUPPORTED_SOURCES))
        if invalid_sources:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported sources: {', '.join(invalid_sources)}",
            )

    if payload.workspace_id is not None:
        workspace = db.get(ResearchWorkspace, payload.workspace_id)
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    agent_state = await run_research_agent(
        {
            "objective": objective,
            "query_hint": payload.query_hint,
            "sources": payload.sources,
            "limit_per_source": payload.limit_per_source,
            "year_from": payload.year_from,
            "year_to": payload.year_to,
            "open_access_only": payload.open_access_only,
            "sort_by": payload.sort_by,
            "mode": payload.mode,
            "style": payload.style,
            "question": payload.question,
            "instructions": payload.instructions,
            "max_iterations": payload.max_iterations,
            "min_papers": payload.min_papers,
            "max_papers_for_synthesis": payload.max_papers_for_synthesis,
        }
    )

    selected_papers = agent_state.get("selected_papers") or []
    source_errors = agent_state.get("source_errors") or {}

    sources_used = [s for s in (agent_state.get("active_sources") or []) if s in SUPPORTED_SOURCES]
    if not sources_used:
        sources_used = [s for s in (payload.sources or []) if s in SUPPORTED_SOURCES] or list(SUPPORTED_SOURCES)

    db.add(
        ResearchSearch(
            workspace_id=payload.workspace_id,
            query=agent_state.get("current_query") or objective,
            sources=sources_used,
            result_count=len(agent_state.get("results") or []),
        )
    )

    saved_brief_id = None
    if payload.workspace_id is not None and selected_papers:
        brief = ResearchWorkspaceBrief(
            workspace_id=payload.workspace_id,
            mode=(agent_state.get("mode") or payload.mode or "summary")[:32],
            style=(payload.style or "balanced")[:32],
            title=f"Agent run · {objective[:120]}",
            body=agent_state.get("synthesis") or "",
            source_papers=selected_papers,
        )
        db.add(brief)
        db.flush()
        saved_brief_id = brief.id

    db.commit()

    return ResearchAgentRunResponse(
        objective=objective,
        iterations=int(agent_state.get("iteration", 0)) + 1,
        final_query=agent_state.get("current_query") or objective,
        selected_paper_count=len(selected_papers),
        selected_papers=selected_papers,
        sources_used=sources_used,
        source_errors=source_errors,
        synthesis_mode=agent_state.get("mode") or payload.mode,
        synthesis=agent_state.get("synthesis") or "",
        citation_validation=agent_state.get("citation_validation") or "No validation produced.",
        steps=[AgentRunStep(**step) for step in agent_state.get("steps") or []],
        saved_brief_id=saved_brief_id,
    )
