from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.services.research_llm import synthesize_research
from app.services.research_source_selection import resolve_search_sources
from app.services.research_sources import SUPPORTED_SOURCES, search_publications

SynthesisMode = Literal["summary", "compare", "question"]


class AgentRunState(TypedDict, total=False):
    objective: str
    query_hint: str | None
    sources: list[str] | None
    active_sources: list[str] | None
    limit_per_source: int
    year_from: int | None
    year_to: int | None
    open_access_only: bool
    sort_by: str
    mode: str
    style: str
    question: str | None
    instructions: str | None
    max_iterations: int
    min_papers: int
    max_papers_for_synthesis: int
    current_query: str
    iteration: int
    results: list[dict[str, Any]]
    selected_papers: list[dict[str, Any]]
    source_errors: dict[str, str]
    synthesis: str
    citation_validation: str
    steps: list[dict[str, str]]


def _normalize_mode(mode: str) -> SynthesisMode:
    normalized = (mode or "summary").strip().lower()
    if normalized not in {"summary", "compare", "question"}:
        return "summary"
    return normalized  # type: ignore[return-value]


def _rank_papers(paper: dict[str, Any]) -> tuple[int, int, int]:
    has_abstract = 1 if (paper.get("abstract") or "").strip() else 0
    citations = int(paper.get("citation_count") or 0)
    year = int(paper.get("year") or 0)
    return (has_abstract, citations, year)


def _validate_citations(text: str, paper_count: int) -> str:
    refs = [int(m.group(1)) for m in re.finditer(r"\[(\d+)\]", text or "")]
    if not refs:
        return "No inline citations found. Consider regenerating for stronger traceability."
    out_of_range = sorted({ref for ref in refs if ref < 1 or ref > paper_count})
    if out_of_range:
        return f"Invalid citation indices found: {out_of_range}. Regeneration recommended."
    return f"Citations look valid ({len(refs)} references, {len(set(refs))} unique paper indices)."


async def _plan_query_node(state: AgentRunState) -> AgentRunState:
    query = (state.get("query_hint") or "").strip() or state["objective"].strip()
    if not query:
        query = "recent high quality papers"
    steps = list(state.get("steps") or [])
    steps.append({"name": "plan", "detail": f"Initial query planned: {query}"})

    resolved, src_note = await resolve_search_sources(
        objective=state["objective"],
        query_hint=state.get("query_hint"),
        planned_query=query,
        user_sources=state.get("sources"),
    )
    steps.append(
        {
            "name": "sources",
            "detail": f"Using catalogs: {', '.join(resolved)}. {src_note}",
        }
    )
    return {"current_query": query, "iteration": 0, "steps": steps, "active_sources": resolved}


async def _search_node(state: AgentRunState) -> AgentRunState:
    query = state["current_query"]
    picked = state.get("active_sources")
    raw_sources = picked if isinstance(picked, list) and len(picked) > 0 else state.get("sources")
    sources = [s for s in (raw_sources or list(SUPPORTED_SOURCES)) if s in SUPPORTED_SOURCES]
    results, source_errors = await search_publications(
        query=query,
        limit_per_source=max(1, min(int(state.get("limit_per_source", 4)), 10)),
        sources=sources,
        year_from=state.get("year_from"),
        year_to=state.get("year_to"),
        open_access_only=bool(state.get("open_access_only", False)),
        sort_by=state.get("sort_by", "relevance"),
    )
    steps = list(state.get("steps") or [])
    steps.append(
        {
            "name": "search",
            "detail": (
                f"Iteration {int(state.get('iteration', 0)) + 1}: "
                f"{len(results)} results from {len(sources)} sources."
            ),
        }
    )
    return {"results": results, "source_errors": source_errors, "steps": steps}


def _should_refine_query(state: AgentRunState) -> str:
    results = state.get("results") or []
    min_papers = max(1, int(state.get("min_papers", 4)))
    max_iterations = max(1, int(state.get("max_iterations", 2)))
    iteration = int(state.get("iteration", 0))
    if len(results) >= min_papers:
        return "select"
    if iteration + 1 >= max_iterations:
        return "select"
    return "refine"


async def _refine_query_node(state: AgentRunState) -> AgentRunState:
    old_query = state["current_query"]
    objective = state["objective"]
    iteration = int(state.get("iteration", 0)) + 1
    refinement_hint = "survey OR benchmark OR systematic review"
    new_query = f"{old_query} {refinement_hint} {objective}".strip()
    steps = list(state.get("steps") or [])
    steps.append(
        {
            "name": "refine",
            "detail": f"Refined query for next iteration: {new_query}",
        }
    )
    return {"current_query": new_query, "iteration": iteration, "steps": steps}


async def _select_papers_node(state: AgentRunState) -> AgentRunState:
    max_papers = max(1, int(state.get("max_papers_for_synthesis", 8)))
    ranked = sorted(state.get("results") or [], key=_rank_papers, reverse=True)
    selected = ranked[:max_papers]
    steps = list(state.get("steps") or [])
    steps.append(
        {
            "name": "select",
            "detail": f"Selected {len(selected)} papers for synthesis.",
        }
    )
    return {"selected_papers": selected, "steps": steps}


async def _synthesize_node(state: AgentRunState) -> AgentRunState:
    selected = state.get("selected_papers") or []
    mode = _normalize_mode(state.get("mode", "summary"))
    synthesis = await synthesize_research(
        mode=mode,
        papers=selected,
        style=state.get("style", "balanced"),
        question=state.get("question"),
        instructions=state.get("instructions"),
    )
    steps = list(state.get("steps") or [])
    steps.append({"name": "synthesize", "detail": f"Synthesis generated in mode '{mode}'."})
    return {"synthesis": synthesis, "mode": mode, "steps": steps}


async def _validate_node(state: AgentRunState) -> AgentRunState:
    validation = _validate_citations(state.get("synthesis", ""), len(state.get("selected_papers") or []))
    steps = list(state.get("steps") or [])
    steps.append({"name": "validate", "detail": validation})
    return {"citation_validation": validation, "steps": steps}


@lru_cache(maxsize=1)
def _agent_graph():
    graph = StateGraph(AgentRunState)
    graph.add_node("plan", _plan_query_node)
    graph.add_node("search", _search_node)
    graph.add_node("refine", _refine_query_node)
    graph.add_node("select", _select_papers_node)
    graph.add_node("synthesize", _synthesize_node)
    graph.add_node("validate", _validate_node)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "search")
    graph.add_conditional_edges(
        "search",
        _should_refine_query,
        {"refine": "refine", "select": "select"},
    )
    graph.add_edge("refine", "search")
    graph.add_edge("select", "synthesize")
    graph.add_edge("synthesize", "validate")
    graph.add_edge("validate", END)
    return graph.compile()


async def run_research_agent(state: AgentRunState) -> AgentRunState:
    initial_state: AgentRunState = {
        **state,
        "steps": [],
        "iteration": 0,
    }
    return await _agent_graph().ainvoke(initial_state)
