"""Turn-by-turn agent that clarifies intent, then emits a grounded search payload (sources capped by user)."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

import httpx

from app.core.config import get_settings
from app.services.research_llm import CEREBRAS_URL
from app.services.research_source_selection import _dedupe_keep_order, heuristic_sources_for
from app.services.research_sources import SUPPORTED_SOURCES

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")

CollaboratePhase = Literal["asking", "ready"]

_OPENER_ASSISTANT = (
    "What are you hoping to discover in the literature? Describe your topic or question "
    "(a sentence or two is fine)."
)

_QUICK_AFTER_OPENER = [
    "Biomedical / clinical / health",
    "Computer science / machine learning",
    "Social science / policy / humanities",
    "I'm not sure — help me narrow it down",
]


def _extract_json(raw: str) -> dict[str, Any] | None:
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
    return data if isinstance(data, dict) else None


def _clamp_catalog_count(n: int | None) -> int:
    if n is None:
        return 4
    return max(1, min(int(n), 5))


def _cap_sources(ids: list[str], cap: int) -> list[str]:
    cleaned = _dedupe_keep_order([s for s in ids if s in SUPPORTED_SOURCES])
    cap = max(1, cap)
    return cleaned[:cap]


def opening_turn() -> dict[str, Any]:
    return {
        "phase": "asking",
        "assistant_message": _OPENER_ASSISTANT,
        "quick_replies": list(_QUICK_AFTER_OPENER),
        "search": None,
    }


def _heuristic_plan_ready(user_blob: str, desired_catalog_count: int) -> dict[str, Any]:
    cap = _clamp_catalog_count(desired_catalog_count)
    trimmed = user_blob.strip()[:800]
    if len(trimmed) < 8:
        return {
            "phase": "asking",
            "assistant_message": "Say a bit more about your topic or question so we can choose catalogs.",
            "quick_replies": [],
            "search": None,
        }
    resolved = heuristic_sources_for(trimmed)
    sources = _cap_sources(list(resolved), cap)
    return {
        "phase": "ready",
        "assistant_message": (
            f"I'll search {', '.join(sources)} (up to {cap} catalogs). "
            "Offline routing picked catalogs — configure the assistant API key on the server for deeper back‑and‑forth."
        ).strip(),
        "quick_replies": [],
        "search": {
            "query": trimmed[:400],
            "sources": sources,
            "limit_per_source": 5,
            "year_from": None,
            "year_to": None,
            "open_access_only": False,
            "sort_by": "relevance",
        },
    }


async def collaborate_search_turn(
    messages: list[dict[str, str]],
    *,
    desired_catalog_count: int,
) -> dict[str, Any]:
    """
    Stateless turn: ``messages`` is the full transcript (user + assistant).
    First call with ``[]`` yields the opener (no upstream model).
    """

    desired = _clamp_catalog_count(desired_catalog_count)

    if not messages:
        return opening_turn()

    # Last turn must be the user's latest reply
    if messages[-1].get("role") != "user":
        raise ValueError("The latest message must be from the user.")

    combined_user = "\n".join(m["content"] for m in messages if m.get("role") == "user")

    settings = get_settings()
    if not settings.cerebras_api_key:
        return _heuristic_plan_ready(combined_user, desired)

    system_prompt = (
        "You coordinate a SHORT collaborative literature search. "
        "Ask ONE concise follow‑up question at a time until you can run a search. "
        f"The user chose to query at most {desired} DIFFERENT catalogs this run "
        "(each catalog is one id in allowed_sources). Respect that ceiling.\n\n"
        "Cover if missing: disciplinary area (biomedical vs CS vs broad), whether they "
        "care about recent years, open access preference, and the best keyword query string.\n\n"
        f"Allowed source ids ONLY: {', '.join(SUPPORTED_SOURCES)}\n\n"
        "Respond with JSON ONLY and no prose outside the object:\n"
        '{"phase":"asking"|"ready",'
        '"assistant_message":"friendly text shown to user (one paragraph max)",'
        '"quick_replies":["optional chip labels up to four short strings"],'
        '"search":null OR {'
        '"query":"focused search query",'
        '"sources":["catalog_id"],'
        '"limit_per_source":1-10,'
        '"year_from":null|integer,'
        '"year_to":null|integer,'
        '"open_access_only":boolean,'
        '"sort_by":"relevance"|"newest"|"most_cited"'
        "}}"
    )

    chat_payload: dict[str, Any] = {
        "model": settings.cerebras_model,
        "messages": [{"role": "system", "content": system_prompt}]
        + [{"role": str(m["role"]), "content": str(m["content"])[:6000]} for m in messages],
        "temperature": 0.25,
        "max_tokens": 700,
    }
    headers = {
        "Authorization": f"Bearer {settings.cerebras_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=55) as client:
            resp = await client.post(CEREBRAS_URL, headers=headers, json=chat_payload)
    except httpx.HTTPError:
        return _heuristic_plan_ready(combined_user, desired)

    if resp.status_code >= 400:
        return _heuristic_plan_ready(combined_user, desired)

    try:
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return _heuristic_plan_ready(combined_user, desired)

    parsed = _extract_json(str(raw))
    if not parsed:
        return _heuristic_plan_ready(combined_user, desired)

    phase = str(parsed.get("phase") or "asking").lower()
    assistant_message = str(parsed.get("assistant_message") or "").strip() or (
        "What else should I know before we search?"
    )
    qr = parsed.get("quick_replies")
    quick_replies: list[str] = []
    if isinstance(qr, list):
        quick_replies = [str(item).strip() for item in qr if str(item).strip()][:6]

    if phase != "ready":
        return {"phase": "asking", "assistant_message": assistant_message, "quick_replies": quick_replies, "search": None}

    search_obj = parsed.get("search")
    if not isinstance(search_obj, dict):
        return {
            "phase": "asking",
            "assistant_message": assistant_message
            or "I still need database settings—what catalogs should we favor?",
            "quick_replies": quick_replies,
            "search": None,
        }

    query = str(search_obj.get("query") or "").strip()
    raw_sources = search_obj.get("sources")
    ids: list[str] = []
    if isinstance(raw_sources, list):
        ids = [str(x).strip().lower().replace("-", "_") for x in raw_sources]

    sources = _cap_sources(ids, desired)
    if not query:
        query = combined_user.strip()[:400] or "recent research"
    if len(sources) < 1:
        sources = _cap_sources(heuristic_sources_for(query + " " + combined_user), desired)

    limit_raw = search_obj.get("limit_per_source", 5)
    try:
        limit_per_source = max(1, min(int(limit_raw), 10))
    except (TypeError, ValueError):
        limit_per_source = 5

    def _nullable_int(field: str) -> int | None:
        v = search_obj.get(field)
        if v is None or v == "null":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    oa_raw = search_obj.get("open_access_only", False)
    open_access_only = bool(oa_raw) if isinstance(oa_raw, bool) else str(oa_raw).lower() in {"1", "true", "yes"}

    sort_candidate = str(search_obj.get("sort_by") or "relevance").lower()
    if sort_candidate not in {"relevance", "newest", "most_cited"}:
        sort_candidate = "relevance"

    return {
        "phase": "ready",
        "assistant_message": assistant_message,
        "quick_replies": [],
        "search": {
            "query": query[:800],
            "sources": sources,
            "limit_per_source": limit_per_source,
            "year_from": _nullable_int("year_from"),
            "year_to": _nullable_int("year_to"),
            "open_access_only": open_access_only,
            "sort_by": sort_candidate,
        },
    }
