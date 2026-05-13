import httpx
import json
from functools import lru_cache
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import END, StateGraph

from app.services.paper_prompt import papers_to_llm_context
from app.services.research_model import invoke_research_llm, llm_configured
from app.services.research_sources import enrich_missing_abstracts


def _heuristic_priority(paper: dict) -> tuple[int, int, int]:
    title = (paper.get("title") or "").lower()
    year = int(paper.get("year") or 0)
    citations = int(paper.get("citation_count") or 0)

    survey_bonus = 0
    for keyword in ("survey", "review", "tutorial", "overview", "benchmark"):
        if keyword in title:
            survey_bonus = 1
            break

    return (survey_bonus, citations, year)


def _heuristic_rationale(paper: dict, index: int) -> str:
    title = (paper.get("title") or "").lower()
    if any(keyword in title for keyword in ("survey", "review", "tutorial", "overview")):
        return "Start here for broad orientation and terminology before diving into narrower papers."
    if "benchmark" in title:
        return "Read early to anchor the evaluation setup and common tasks used in the area."
    if index == 0:
        return "This looks like the best entry point based on influence and breadth."
    return "Read after the overview papers to deepen your understanding with a more specific contribution."


class ReadingPathState(TypedDict, total=False):
    objective: Optional[str]
    preferences: Optional[str]
    papers: List[Dict[str, Any]]
    prompt: str
    result: Dict[str, Any]


def _heuristic_result(objective: Optional[str], papers: List[Dict[str, Any]], extra_overview: str = "") -> Dict[str, Any]:
    ordered = sorted(papers, key=_heuristic_priority, reverse=True)
    steps = [
        {
            "order": index,
            "title": paper.get("title", "Untitled"),
            "source": paper.get("source", "unknown"),
            "external_id": paper.get("external_id", ""),
            "rationale": _heuristic_rationale(paper, index),
        }
        for index, paper in enumerate(ordered, start=1)
    ]
    overview = "This fallback reading path prioritizes overview-like papers first, then influential or newer papers."
    if extra_overview:
        overview = f"{overview} {extra_overview}"
    return {
        "objective": objective or "Build a clean reading sequence",
        "overview": overview,
        "steps": steps,
    }


async def _prepare_prompt_node(state: ReadingPathState) -> ReadingPathState:
    papers = state.get("papers") or []
    if not papers:
        return {"result": {"objective": state.get("objective") or "Understand this topic", "overview": "Select papers first.", "steps": []}}
    preferences = (state.get("preferences") or "").strip()
    pref_block = f"\nUser preferences to satisfy:\n{preferences}\n" if preferences else ""
    prompt = f"""
You are a research companion helping a user decide what to read first.
Use only the selected papers below.
Build a reading path for this objective: {state.get("objective") or "Build understanding of the topic efficiently"}.
{pref_block}
Return JSON with this shape only:
{{
  "objective": "...",
  "overview": "...",
  "steps": [
    {{
      "order": 1,
      "title": "...",
      "source": "...",
      "external_id": "...",
      "rationale": "..."
    }}
  ]
}}

Selected papers:
{papers_to_llm_context(papers)}
"""
    return {"prompt": prompt}


async def _generate_plan_node(state: ReadingPathState) -> ReadingPathState:
    if state.get("result"):
        return {}
    papers = state.get("papers") or []
    objective = state.get("objective")
    if not llm_configured():
        return {"result": _heuristic_result(objective, papers)}
    async with httpx.AsyncClient(timeout=60) as client:
        await enrich_missing_abstracts(client, papers)
    try:
        raw, _provider = await invoke_research_llm(
            system_prompt="You are a precise research assistant who returns valid JSON for reading plans.",
            user_prompt=state["prompt"],
            temperature=0.2,
        )
        return {"result": json.loads(raw)}
    except Exception as exc:
        return {
            "result": _heuristic_result(
                objective,
                papers,
                f"Falling back to heuristic ordering because the model call failed ({exc}).",
            )
        }


@lru_cache(maxsize=1)
def _build_graph():
    graph = StateGraph(ReadingPathState)
    graph.add_node("prepare_prompt", _prepare_prompt_node)
    graph.add_node("generate_plan", _generate_plan_node)
    graph.set_entry_point("prepare_prompt")
    graph.add_edge("prepare_prompt", "generate_plan")
    graph.add_edge("generate_plan", END)
    return graph.compile()


async def build_reading_path(
    objective: Optional[str], papers: List[Dict[str, Any]], preferences: Optional[str] = None
) -> Dict[str, Any]:
    state: ReadingPathState = {"objective": objective, "preferences": preferences, "papers": papers}
    out = await _build_graph().ainvoke(state)
    return out.get("result") or {"objective": objective or "Understand this topic", "overview": "No plan generated.", "steps": []}
