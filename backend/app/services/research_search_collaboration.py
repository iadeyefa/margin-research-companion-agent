"""Turn-by-turn agent that clarifies intent, then emits a grounded search payload (sources capped by user)."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from app.services.research_model import invoke_research_llm, llm_configured
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

# User wants to proceed / has nothing further when model keeps asking loop questions.
_ACK_PROCEED_SNIPPETS: frozenset[str] = frozenset(
    [
        "go",
        "ok",
        "okay",
        "yes",
        "yeah",
        "yep",
        "sure",
        "proceed",
        "continue",
        "fine",
        "nothing",
        "none",
        "no",
        "nope",
        "nah",
        "search",
        "run it",
        "run search",
        "start",
        "start search",
        "lets go",
        "let's go",
        "all set",
        "go ahead",
        "do it",
        "that's all",
        "thats all",
        "looks good",
        "sounds good",
        "that's it",
        "thats it",
        "that's fine",
        "thats fine",
        "whatever",
        "anything",
        "no preference",
        "you decide",
    ]
)


def _normalized_user_ack(text: str) -> str:
    t = text.strip().lower()
    if not t:
        return ""
    t = re.sub(r"[^\w\s']+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _is_proceed_or_no_more_detail(text: str) -> bool:
    """Treat short replies like 'nothing' / 'go' / 'that's fine' as 'no extra constraints.'"""
    normalized = _normalized_user_ack(text)
    if not normalized:
        return False
    if normalized in _ACK_PROCEED_SNIPPETS:
        return True
    if len(normalized) <= 3 and normalized in {"k", "y"}:
        return True
    extra = frozenset(
        {
            "not really",
            "idk",
            "i dont know",
            "i don't know",
            "nothing else",
            "nothing more",
            "no more",
            "no thanks",
            "that's it",
            "thats it",
        }
    )
    return normalized in extra


def _prior_assistant_text(messages: list[dict[str, str]]) -> str:
    """Assistant message immediately before the latest user utterance."""
    if len(messages) < 2:
        return ""
    for m in reversed(messages[:-1]):
        if str(m.get("role") or "") == "assistant":
            return str(m.get("content") or "")
    return ""


def _substantive_user_blob(messages: list[dict[str, str]]) -> str:
    """User lines with trailing acknowledge-only replies stripped."""
    users = [str(m.get("content") or "").strip() for m in messages if m.get("role") == "user"]
    while len(users) > 1 and _is_proceed_or_no_more_detail(users[-1]):
        users.pop()
    if users and len(users) == 1 and _is_proceed_or_no_more_detail(users[0]):
        users = []
    return "\n".join(users).strip()


def _assistant_signals_more_questions(ast: str) -> bool:
    a = ast.lower()
    markers = (
        "what else",
        "anything else",
        "should i know",
        "before we search",
        "tell me more",
        "help me narrow",
        "what area",
        "which field",
    )
    return any(m in a for m in markers)


def _should_force_heuristic_plan(messages: list[dict[str, str]]) -> bool:
    """
    Stateless loop guard: skip the planner when user affirms/no-more-detail but the transcript
    already has enough substance to search.
    """
    if len(messages) < 2 or messages[-1].get("role") != "user":
        return False
    last_user = str(messages[-1].get("content") or "")
    blob = _substantive_user_blob(messages)
    if len(blob.strip()) < 8:
        return False
    if not _is_proceed_or_no_more_detail(last_user):
        return False
    prior_ast = _prior_assistant_text(messages)
    # Already printed a catalog plan → user asking to execute / confirm.
    if "i'll search" in prior_ast.lower():
        return True
    # Offline / failure copy still committed to catalogs.
    if "offline routing" in prior_ast.lower():
        return True
    # Model stuck repeating follow-ups after user waived more detail.
    if _assistant_signals_more_questions(prior_ast):
        return True
    return False


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


def _format_offline_failure_reason(reason: str, *, per_part: int = 120, max_parts: int = 4) -> str:
    """Show each provider's error; avoid one long message hiding the next (e.g. Google 429 vs Ollama)."""
    if not reason:
        return ""
    body = reason
    prefix = "All LLM providers failed: "
    if body.startswith(prefix):
        body = body[len(prefix) :]
    parts = [p.strip() for p in body.split(" | ") if p.strip()]
    if not parts:
        tail = "…" if len(reason) > per_part else ""
        return (reason[:per_part] + tail) if len(reason) > per_part else reason
    out: list[str] = []
    for p in parts[:max_parts]:
        if len(p) > per_part:
            out.append(p[: per_part - 1] + "…")
        else:
            out.append(p)
    return " | ".join(out)


def opening_turn() -> dict[str, Any]:
    return {
        "phase": "asking",
        "assistant_message": _OPENER_ASSISTANT,
        "quick_replies": list(_QUICK_AFTER_OPENER),
        "search": None,
    }


def _heuristic_plan_ready(
    user_blob: str,
    desired_catalog_count: int,
    reason: str | None = None,
    *,
    narrative: Literal["offline", "execute"] = "offline",
) -> dict[str, Any]:
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
    if narrative == "execute":
        detail = ""
    elif reason:
        detail = (
            "Offline routing picked catalogs because live provider call failed "
            f"({_format_offline_failure_reason(reason)})."
        )
    else:
        detail = "Offline routing picked catalogs because no live LLM provider is available."
    lead = f"I'll search {', '.join(sources)} (up to {cap} catalogs)."
    if narrative == "execute":
        assistant_message = f"{lead} Running the search using your answers."
    else:
        assistant_message = f"{lead} {detail}".strip()
    return {
        "phase": "ready",
        "assistant_message": assistant_message,
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

    # Loop guard: planner model often returns phase=asking after the user says "go"/"nothing"
    # even though the transcript already holds a usable topic (stateless transcript only).
    if llm_configured() and _should_force_heuristic_plan(messages):
        blob = _substantive_user_blob(messages)
        base = blob if len(blob.strip()) >= 8 else combined_user
        return _heuristic_plan_ready(base, desired, reason=None, narrative="execute")

    if not llm_configured():
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
        "If the user says they have NO more detail to add (nothing / go / OK) and the topic is already clear, "
        'use phase \"ready\" with a complete search object immediately—do not ask again.\n'
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

    try:
        transcript = "\n".join(f"{m['role']}: {str(m['content'])[:1000]}" for m in messages)
        raw, _ = await invoke_research_llm(
            system_prompt=system_prompt,
            user_prompt=transcript,
            temperature=0.25,
        )
    except Exception as exc:  # noqa: BLE001
        return _heuristic_plan_ready(combined_user, desired, reason=str(exc))

    parsed = _extract_json(str(raw))
    if not parsed:
        return _heuristic_plan_ready(combined_user, desired, reason="model did not return valid JSON")

    phase = str(parsed.get("phase") or "asking").lower()
    assistant_message = str(parsed.get("assistant_message") or "").strip() or (
        "What else should I know before we search?"
    )
    qr = parsed.get("quick_replies")
    quick_replies: list[str] = []
    if isinstance(qr, list):
        quick_replies = [str(item).strip() for item in qr if str(item).strip()][:6]

    last_user_txt = str(messages[-1].get("content") or "")
    substantive = _substantive_user_blob(messages)
    asm_lower = assistant_message.lower()
    model_stuck_loop = (
        phase != "ready"
        and len(substantive.strip()) >= 8
        and _is_proceed_or_no_more_detail(last_user_txt)
        and (
            _assistant_signals_more_questions(assistant_message)
            or "what else should i know" in asm_lower
        )
    )
    if model_stuck_loop:
        return _heuristic_plan_ready(substantive, desired, reason=None, narrative="execute")

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
