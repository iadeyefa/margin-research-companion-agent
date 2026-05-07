"""Pick catalog sources for literature search based on the user's objective (LLM + heuristics)."""

from __future__ import annotations

import json
import re

from app.services.research_model import invoke_research_llm, llm_configured
from app.services.research_sources import SUPPORTED_SOURCES

_SOURCE_GUIDE = """
Available sources (use these exact identifiers only):
- arxiv — CS, ML, NLP, CV, robotics, mathematics, physics preprints (not peer‑review filtering).
- semantic_scholar — broad CS / ML papers with citation signals.
- openalex — global scholarly works across disciplines with strong coverage IDs.
- crossref — DOI-linked journal/book metadata; useful for cited DOIs and general publications.
- pubmed — biomedical, clinical, health, life sciences literature.

Pick 2 to 4 sources that best serve the user's goal. Prefer focused sets over querying everything."""

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def _dedupe_keep_order(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in ids:
        if s in SUPPORTED_SOURCES and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _ensure_minimum(sources: list[str], minimum: int = 2) -> list[str]:
    out = _dedupe_keep_order(sources)
    if len(out) >= minimum:
        return out[:4]
    for fallback in SUPPORTED_SOURCES:
        if fallback not in out:
            out.append(fallback)
        if len(out) >= minimum:
            break
    return _dedupe_keep_order(out)[:4]


def heuristic_sources_for(text: str) -> list[str]:
    """Deterministic fallback when LLM is off or parsing fails."""
    t = text.lower()
    picks: list[str] = []

    bio_keys = (
        "clinical",
        "patient",
        "trial",
        "medical",
        "health",
        "disease",
        "covid",
        "cancer",
        "gene",
        "protein",
        "drug",
        "therapy",
        "hospital",
        "diagnosis",
        "biomark",
        "pathology",
        "pubmed",
        "lifesci",
    )
    if any(k in t for k in bio_keys):
        picks.extend(["pubmed", "openalex"])

    cs_keys = (
        "arxiv",
        "machine learning",
        "deep learning",
        "language model",
        "llm",
        "transformer",
        "neural",
        "nlp",
        "computer vision",
        "reinforcement",
        "benchmark",
        "algorithm",
        "gpu",
        "tensor",
    )
    if any(k in t for k in cs_keys):
        picks.extend(["arxiv", "semantic_scholar"])

    math_phys = ("quantum", "topology", "pde ", "astro", "cond-mat")
    if any(k in t for k in math_phys):
        if "arxiv" not in picks:
            picks.insert(0, "arxiv")

    if not picks:
        picks = ["openalex", "semantic_scholar", "crossref"]

    return _ensure_minimum(picks)


def _parse_sources_json(raw: str) -> list[str] | None:
    text = raw.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(text)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    src = data.get("sources")
    if not isinstance(src, list):
        return None
    ids = [str(x).strip().lower().replace("-", "_") for x in src]
    normalized: list[str] = []
    for x in ids:
        if x in SUPPORTED_SOURCES:
            normalized.append(x)
    cleaned = _dedupe_keep_order(normalized)
    return cleaned if len(cleaned) >= 1 else None


async def resolve_search_sources(
    objective: str,
    query_hint: str | None,
    planned_query: str,
    user_sources: list[str] | None,
) -> tuple[list[str], str]:
    """Return (sources, rationale) for an agent/search run."""

    explicit = [s for s in (user_sources or []) if s in SUPPORTED_SOURCES]
    if user_sources is not None and len(user_sources) > 0 and explicit:
        return _ensure_minimum(explicit), "Using client-specified sources."

    blended = "\n".join(
        segment for segment in (objective.strip(), (query_hint or "").strip(), planned_query.strip()) if segment
    )
    if not llm_configured():
        h = heuristic_sources_for(blended)
        return _ensure_minimum(h), f"Heuristic selection (no LLM key): {', '.join(h)}."

    user_msg = (
        f"{_SOURCE_GUIDE}\n\nUser objective:\n{objective.strip()}\n\n"
        f"Query hint:\n{(query_hint or '').strip() or '(none)'}\n\n"
        f"Planned search query:\n{planned_query.strip()}\n\n"
        'Respond with JSON only, no prose outside the object:\n'
        '{"sources":["source_id",...],"rationale":"one short sentence"}'
    )
    try:
        raw_content, provider = await invoke_research_llm(
            system_prompt=(
                "You route academic search requests to the best open metadata catalogs. "
                "Never invent catalog names; only use identifiers from the user message guide. "
                "Output JSON only."
            ),
            user_prompt=user_msg,
            temperature=0.1,
        )
    except Exception:
        h = heuristic_sources_for(blended)
        return _ensure_minimum(h), f"Provider unavailable; heuristic: {', '.join(h)}."

    parsed_ids = _parse_sources_json(raw_content)
    rationale = ""
    try:
        obj = json.loads(raw_content.strip()) if raw_content.strip().startswith("{") else None
        if isinstance(obj, dict) and isinstance(obj.get("rationale"), str):
            rationale = obj["rationale"].strip()
    except json.JSONDecodeError:
        pass
    if parsed_ids:
        ensured = _ensure_minimum(parsed_ids)
        detail = rationale or f"Model-selected catalogs ({provider})."
        return ensured, detail
    h = heuristic_sources_for(blended)
    return (
        _ensure_minimum(h),
        f"Could not parse model JSON; heuristic: {', '.join(h)}.",
    )
