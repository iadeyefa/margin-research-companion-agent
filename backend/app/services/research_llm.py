from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Literal, TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app.services.paper_prompt import papers_to_llm_context
from app.services.research_model import invoke_research_llm, llm_configured
from app.services.research_sources import enrich_missing_abstracts

SynthesisMode = Literal["summary", "compare", "question"]

_PLAIN_OUTPUT_RULE = (
    "Formatting: plain text only. Do not use Markdown (no ** or __ for bold, no # headings, no backticks). "
    "Write section titles as a single plain line, then a blank line, then the section body."
)


def _strip_markdown_noise(text: str) -> str:
    """Remove common Markdown tokens the model may still emit."""
    s = text
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"__([^_]+)__", r"\1", s)
    s = re.sub(r"(?m)^#{1,6}\s+", "", s)
    return s


def _style_instruction(style: str) -> str:
    normalized = (style or "balanced").strip().lower()
    if normalized == "concise":
        return "Keep the synthesis short: 1-2 tight paragraphs or 3-5 bullets per section."
    if normalized == "deep":
        return "Write a deeper research brief with more detail on methods, evidence, and caveats."
    if normalized == "methods":
        return "Emphasize methods, datasets, evaluation setup, assumptions, and reproducibility."
    if normalized == "limitations":
        return "Emphasize limitations, missing evidence, threats to validity, and open questions."
    return "Balance high-level takeaways with enough detail for a researcher deciding what to read next."


def _prompt_for_mode(mode: SynthesisMode, question: str | None, style: str) -> str:
    if mode == "summary":
        return (
            "Write a concise but high-signal synthesis of the selected papers.\n"
            f"{_style_instruction(style)}\n"
            f"{_PLAIN_OUTPUT_RULE}\n"
            "Citations: reference papers inline using [1], [2], etc. matching the Paper numbers below.\n"
            "Use these section headers exactly (plain lines, no asterisks):\n"
            "Overview\n"
            "Key Themes\n"
            "Method Patterns\n"
            "What To Read First\n"
            "Gaps Or Caveats"
        )
    if mode == "compare":
        return (
            "Compare the selected papers directly.\n"
            f"{_style_instruction(style)}\n"
            f"{_PLAIN_OUTPUT_RULE}\n"
            "Citations: reference papers inline using [1], [2], etc. matching the Paper numbers below.\n"
            "Use these section headers exactly (plain lines, no asterisks):\n"
            "Research Question\n"
            "Methods And Evidence\n"
            "Where They Agree\n"
            "Where They Differ\n"
            "Strengths And Limitations\n"
            "Practical Takeaway"
        )
    return (
        f"Answer this research question using only the selected papers: {question or 'No question provided.'}\n"
        f"{_style_instruction(style)}\n"
        f"{_PLAIN_OUTPUT_RULE}\n"
        "Citations: reference papers inline using [1], [2], etc. matching the Paper numbers below.\n"
        "Use these section headers exactly (plain lines, no asterisks):\n"
        "Short Answer\n"
        "Evidence From The Selected Papers\n"
        "Limits Of The Evidence"
    )


def _instructions_suffix(instructions: str | None) -> str:
    text = (instructions or "").strip()
    if not text:
        return ""
    return (
        "Additional user instructions (prioritize these while still following evidence constraints):\n"
        f"{text}\n"
    )


def is_research_llm_configured() -> bool:
    return llm_configured()


class SynthesisState(TypedDict, total=False):
    mode: SynthesisMode
    papers: list[dict]
    style: str
    question: str | None
    instructions: str | None
    prompt: str
    response: str
    error: str


async def _prepare_prompt_node(state: SynthesisState) -> SynthesisState:
    papers = state["papers"]
    prompt = f"""
You are a careful research companion. Use only the selected paper metadata and abstract blocks below.
When an abstract is missing from catalogs, follow the instructions in that paper's block: do not treat thin metadata as full evidence.
Do not invent findings that are not supported by the provided papers.
When comparing papers, be explicit about uncertainty and missing details.
Write in clear sections with the requested headers. Remember: plain text only, no Markdown emphasis.

Task:
{_prompt_for_mode(state["mode"], state.get("question"), state.get("style", "balanced"))}
{_instructions_suffix(state.get("instructions"))}
Selected papers:
{papers_to_llm_context(papers)}
"""
    return {"prompt": prompt}


async def _call_model_node(state: SynthesisState) -> SynthesisState:
    papers = state["papers"]
    mode = state["mode"]
    if not llm_configured():
        titles = ", ".join(paper.get("title", "Untitled") for paper in papers[:5])
        if mode == "summary":
            return {"response": f"Selected papers: {titles}. Configure Google or Ollama to generate a deeper synthesis."}
        if mode == "compare":
            return {"response": f"Selected papers for comparison: {titles}. Configure Google or Ollama to generate a full comparison."}
        return {"response": f"Selected papers: {titles}. Configure Google or Ollama to answer research questions across them."}

    async with httpx.AsyncClient(timeout=60) as client:
        await enrich_missing_abstracts(client, papers)
    try:
        text, provider = await invoke_research_llm(
            system_prompt=(
                "You are a precise research assistant who synthesizes papers carefully. "
                "Always respond in plain text: no Markdown bold/italic markers (no ** or __), "
                "no hash headings, no fenced code unless the user explicitly asks for code."
            ),
            user_prompt=state["prompt"],
            temperature=0.2,
        )
        return {"response": _strip_markdown_noise(text), "error": f"provider={provider}"}
    except Exception as exc:  # noqa: BLE001
        return {"response": f"The synthesis model failed. Detail: {exc}"}


@lru_cache(maxsize=1)
def _synthesis_graph():
    graph = StateGraph(SynthesisState)
    graph.add_node("prepare_prompt", _prepare_prompt_node)
    graph.add_node("call_model", _call_model_node)
    graph.set_entry_point("prepare_prompt")
    graph.add_edge("prepare_prompt", "call_model")
    graph.add_edge("call_model", END)
    return graph.compile()


async def synthesize_research(
    mode: SynthesisMode,
    papers: list[dict],
    style: str = "balanced",
    question: str | None = None,
    instructions: str | None = None,
) -> str:
    if not papers:
        return "Select at least one paper first."
    state: SynthesisState = {
        "mode": mode,
        "papers": papers,
        "style": style,
        "question": question,
        "instructions": instructions,
    }
    result: dict[str, Any] = await _synthesis_graph().ainvoke(state)
    return str(result.get("response") or "Synthesis failed unexpectedly.")
