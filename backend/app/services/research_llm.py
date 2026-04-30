from __future__ import annotations

from typing import Literal

import httpx

from app.core.config import get_settings


settings = get_settings()
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"

SynthesisMode = Literal["summary", "compare", "question"]


def _paper_context(papers: list[dict]) -> str:
    lines: list[str] = []
    for index, paper in enumerate(papers, start=1):
        authors = ", ".join(paper.get("authors") or []) or "Unknown authors"
        lines.append(
            "\n".join(
                [
                    f"Paper {index}: {paper.get('title', 'Untitled')}",
                    f"Source: {paper.get('source', 'unknown')}",
                    f"Authors: {authors}",
                    f"Venue: {paper.get('venue') or 'Unknown venue'}",
                    f"Year: {paper.get('year') or 'Unknown'}",
                    f"Citations: {paper.get('citation_count') if paper.get('citation_count') is not None else 'Unknown'}",
                    f"Abstract: {paper.get('abstract') or 'No abstract available.'}",
                ]
            )
        )
    return "\n\n".join(lines)


def _prompt_for_mode(mode: SynthesisMode, question: str | None) -> str:
    if mode == "summary":
        return (
            "Write a concise but high-signal synthesis of the selected papers.\n"
            "Use these section headers exactly:\n"
            "Overview\n"
            "Key Themes\n"
            "Method Patterns\n"
            "What To Read First\n"
            "Gaps Or Caveats"
        )
    if mode == "compare":
        return (
            "Compare the selected papers directly.\n"
            "Use these section headers exactly:\n"
            "Research Question\n"
            "Methods And Evidence\n"
            "Where They Agree\n"
            "Where They Differ\n"
            "Strengths And Limitations\n"
            "Practical Takeaway"
        )
    return (
        f"Answer this research question using only the selected papers: {question or 'No question provided.'}\n"
        "Use these section headers exactly:\n"
        "Short Answer\n"
        "Evidence From The Selected Papers\n"
        "Limits Of The Evidence"
    )


def is_research_llm_configured() -> bool:
    return bool(settings.cerebras_api_key)


async def synthesize_research(
    mode: SynthesisMode,
    papers: list[dict],
    question: str | None = None,
) -> str:
    if not papers:
        return "Select at least one paper first."

    if not settings.cerebras_api_key:
        titles = ", ".join(paper.get("title", "Untitled") for paper in papers[:5])
        if mode == "summary":
            return f"Selected papers: {titles}. Add a Cerebras API key to generate a deeper synthesis."
        if mode == "compare":
            return f"Selected papers for comparison: {titles}. Add a Cerebras API key to generate a full comparison."
        return f"Selected papers: {titles}. Add a Cerebras API key to answer research questions across them."

    prompt = f"""
You are a careful research companion. Use only the selected paper metadata and abstracts below.
Do not invent findings that are not supported by the provided papers.
When comparing papers, be explicit about uncertainty and missing details.
Write in clear sections with the requested headers.

Task:
{_prompt_for_mode(mode, question)}

Selected papers:
{_paper_context(papers)}
"""

    payload = {
        "model": settings.cerebras_model,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise research assistant who synthesizes papers carefully.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 900,
    }

    headers = {
        "Authorization": f"Bearer {settings.cerebras_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(CEREBRAS_URL, headers=headers, json=payload)
        if response.status_code >= 400:
            try:
                error_payload = response.json()
                detail = error_payload.get("message") or error_payload.get("error") or response.text
            except Exception:
                detail = response.text
            return (
                "The synthesis model returned an error.\n"
                f"Status: {response.status_code}\n"
                f"Model: {settings.cerebras_model}\n"
                f"Detail: {detail}\n\n"
                "If this says the model does not exist, set CEREBRAS_MODEL in backend/.env to one of "
                "the models listed at https://api.cerebras.ai/v1/models."
            )
        data = response.json()

    return data["choices"][0]["message"]["content"]
