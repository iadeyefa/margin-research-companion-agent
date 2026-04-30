from __future__ import annotations

import httpx

from app.core.config import get_settings


settings = get_settings()
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"


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


def _paper_context(papers: list[dict]) -> str:
    lines: list[str] = []
    for index, paper in enumerate(papers, start=1):
        lines.append(
            "\n".join(
                [
                    f"Paper {index}: {paper.get('title', 'Untitled')}",
                    f"Authors: {', '.join(paper.get('authors') or []) or 'Unknown authors'}",
                    f"Venue: {paper.get('venue') or 'Unknown venue'}",
                    f"Year: {paper.get('year') or 'Unknown'}",
                    f"Citations: {paper.get('citation_count') if paper.get('citation_count') is not None else 'Unknown'}",
                    f"Abstract: {paper.get('abstract') or 'No abstract available.'}",
                ]
            )
        )
    return "\n\n".join(lines)


async def build_reading_path(objective: str | None, papers: list[dict]) -> dict:
    if not papers:
        return {"objective": objective or "Understand this topic", "overview": "Select papers first.", "steps": []}

    if not settings.cerebras_api_key:
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
        return {
            "objective": objective or "Build a clean reading sequence",
            "overview": "This fallback reading path prioritizes overview-like papers first, then influential or newer papers.",
            "steps": steps,
        }

    prompt = f"""
You are a research companion helping a user decide what to read first.
Use only the selected papers below.
Build a reading path for this objective: {objective or "Build understanding of the topic efficiently"}.

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
{_paper_context(papers)}
"""

    payload = {
        "model": settings.cerebras_model,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise research assistant who returns valid JSON for reading plans.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 900,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {settings.cerebras_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(CEREBRAS_URL, headers=headers, json=payload)
        if response.status_code >= 400:
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
            return {
                "objective": objective or "Build a clean reading sequence",
                "overview": (
                    "Falling back to a heuristic reading order because the LLM call failed "
                    f"(status {response.status_code}). Set CEREBRAS_MODEL to a model returned by "
                    "https://api.cerebras.ai/v1/models if this keeps happening."
                ),
                "steps": steps,
            }
        data = response.json()

    import json

    return json.loads(data["choices"][0]["message"]["content"])
