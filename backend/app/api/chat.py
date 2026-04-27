import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.team import Team
from app.schemas.chat import AnalysisRead, ChatRequest
from app.services.cerebras import generate_sports_analysis, is_cerebras_configured
from app.services.llm import analysis_chain
from app.services.nba_teams import extract_mentioned_teams
from app.services.pinecone import retrieve_similar_games
from app.core.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/chat", tags=["chat"])

PLAYOFF_TERMS = ("playoff", "playoffs", "finals", "championship", "title")
PREDICTION_TERMS = ("who will win", "predict", "winner", "champion", "finals")
CURRENT_TERMS = ("this year", "this year's", "this season", "current", "2026")


def _sse(payload: dict[str, str] | str) -> str:
    if isinstance(payload, str):
        return f"data: {payload}\n\n"
    return f"data: {json.dumps(payload)}\n\n"


def _retrieved_text(similar_games: list[dict]) -> list[str]:
    return [
        str(game.get("metadata", {}).get("text", ""))
        for game in similar_games
        if game.get("metadata", {}).get("text")
    ]


def _coerce_number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _combine_filters(*filters: dict | None) -> dict | None:
    active_filters = [candidate for candidate in filters if candidate]
    if not active_filters:
        return None
    if len(active_filters) == 1:
        return active_filters[0]
    return {"$and": active_filters}


def _team_filter(team_name: str) -> dict[str, object]:
    return {"$or": [{"team": {"$eq": team_name}}, {"opponent": {"$eq": team_name}}]}


def _matchup_filter(team_names: list[str]) -> dict[str, object] | None:
    if len(team_names) < 2:
        return None
    first_team, second_team = team_names[:2]
    return {
        "$or": [
            {"$and": [{"team": {"$eq": first_team}}, {"opponent": {"$eq": second_team}}]},
            {"$and": [{"team": {"$eq": second_team}}, {"opponent": {"$eq": first_team}}]},
        ]
    }


def _build_stats_summary(similar_games: list[dict]) -> str:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for game in similar_games:
        metadata = game.get("metadata", {})
        team = metadata.get("team")
        if not team:
            continue

        grouped[team]["games"] += 1
        if str(metadata.get("result", "")).upper() == "W":
            grouped[team]["wins"] += 1

        for key in ("points", "opponent_points", "assists", "rebounds", "fg_pct", "three_pct", "plus_minus"):
            value = _coerce_number(metadata.get(key))
            if value is not None:
                grouped[team][key] += value
                grouped[team][f"{key}_count"] += 1

    if not grouped:
        return ""

    lines = ["Structured team summary from retrieved records:"]
    for team, totals in sorted(grouped.items(), key=lambda item: item[1].get("games", 0), reverse=True):
        games = int(totals.get("games", 0))
        if games == 0:
            continue
        win_rate = totals.get("wins", 0) / games
        summary = [f"{team}: {int(totals.get('wins', 0))}-{games - int(totals.get('wins', 0))} in {games} retrieved games"]

        for key, label in (
            ("points", "avg points"),
            ("opponent_points", "avg opponent points"),
            ("rebounds", "avg rebounds"),
            ("assists", "avg assists"),
            ("fg_pct", "avg FG%"),
            ("three_pct", "avg 3P%"),
            ("plus_minus", "avg plus-minus"),
        ):
            count = totals.get(f"{key}_count", 0)
            if count:
                summary.append(f"{label} {totals[key] / count:.3f}" if "pct" in key else f"{label} {totals[key] / count:.1f}")

        summary.append(f"win rate {win_rate:.3f}")
        lines.append("; ".join(summary))

    return "\n".join(lines)


def _fallback_answer(question: str, context_items: list[str]) -> str:
    if not context_items:
        return (
            "I could not find matching NBA records in Pinecone yet. "
            "Try ingesting more data, then ask again with a specific team, matchup, or stat."
        )

    lines = [
        "I found these relevant NBA records in Pinecone. A chat model is not running yet, so this is a retrieval-only answer.",
        "",
        f"Question: {question}",
        "",
        "Most relevant context:",
    ]
    for index, item in enumerate(context_items[:5], start=1):
        lines.append(f"{index}. {item}")

    return "\n".join(lines)


def _is_playoff_question(question: str) -> bool:
    lowered = question.lower()
    return any(term in lowered for term in PLAYOFF_TERMS)


def _is_prediction_question(question: str) -> bool:
    lowered = question.lower()
    return any(term in lowered for term in PREDICTION_TERMS)


def _is_current_question(question: str) -> bool:
    lowered = question.lower()
    return any(term in lowered for term in CURRENT_TERMS)


def _retrieval_query(question: str) -> str:
    teams = extract_mentioned_teams(question)
    team_hint = f" Teams mentioned: {', '.join(teams)}." if teams else ""
    if _is_prediction_question(question):
        return (
            f"{question} NBA playoffs contender team performance wins losses scoring rebounds assists "
            f"field goal percentage three point percentage plus-minus championship current season{team_hint}"
        )
    if _is_playoff_question(question):
        return f"{question} NBA playoffs postseason team performance box score plus-minus{team_hint}"
    return f"{question}{team_hint}"


async def _retrieve_context(question: str) -> list[dict]:
    team_names = extract_mentioned_teams(question)
    wants_current = _is_current_question(question) or _is_prediction_question(question)

    base_filter = None
    if _is_playoff_question(question):
        base_filter = _combine_filters(base_filter, {"game_type": {"$eq": "Playoffs"}})
    if wants_current:
        base_filter = _combine_filters(base_filter, {"season_year": {"$eq": settings.current_nba_season_year}})

    queries: list[tuple[str, int, dict | None]] = [
        (_retrieval_query(question), 12 if _is_prediction_question(question) else 8, base_filter)
    ]

    if len(team_names) >= 2:
        queries.append(
            (
                f"{team_names[0]} vs {team_names[1]} matchup head-to-head team performance",
                8,
                _combine_filters(base_filter, _matchup_filter(team_names)),
            )
        )
    elif len(team_names) == 1:
        queries.append(
            (
                f"{team_names[0]} recent team performance scoring rebounds assists plus-minus",
                6,
                _combine_filters(base_filter, _team_filter(team_names[0])),
            )
        )

    merged_matches: dict[str, dict] = {}
    for query, top_k, metadata_filter in queries:
        matches = await retrieve_similar_games(query, top_k=top_k, metadata_filter=metadata_filter)
        for match in matches:
            match_id = str(match.get("id"))
            existing = merged_matches.get(match_id)
            if existing is None or float(match.get("score") or 0) > float(existing.get("score") or 0):
                merged_matches[match_id] = match

    return sorted(
        merged_matches.values(),
        key=lambda match: float(match.get("score") or 0),
        reverse=True,
    )


@router.post("/")
async def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    if not payload.message or not payload.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required fields")

    team_context = ""
    sport = "NBA"
    if payload.team_id:
        team = db.scalar(
            select(Team)
            .where(Team.id == payload.team_id)
            .options(selectinload(Team.games))
        )
        if team:
            sport = team.sport
            recent_games = sorted(team.games, key=lambda game: game.date, reverse=True)[:5]
            games_text = ", ".join(
                f"{team.team_name} {game.score}-{game.opponent_score} vs {game.opponent}"
                for game in recent_games
            )
            team_context = f"Team: {team.team_name} ({team.sport})\nRecent games: {games_text}"

    try:
        similar_games = await _retrieve_context(payload.message)
    except Exception as exc:
        print(f"Skipping Pinecone retrieval: {exc}")
        similar_games = []

    context_items = _retrieved_text(similar_games)
    stats_summary = _build_stats_summary(similar_games)
    rag_context = "\n\n".join(item for item in [stats_summary, *context_items] if item)
    context = rag_context or team_context or "No specific game data available"

    async def stream_response():
        full_response = ""
        try:
            if is_cerebras_configured():
                full_response = await generate_sports_analysis(payload.message, context, sport)
                yield _sse({"text": full_response})
            else:
                async for chunk in analysis_chain.astream(
                    {"context": context, "question": payload.message, "sport": sport}
                ):
                    full_response += chunk
                    yield _sse({"text": chunk})

            yield _sse("[DONE]")

            analysis = Analysis(
                user_id=payload.user_id,
                team_id=payload.team_id,
                question=payload.message,
                response=full_response,
            )
            db.add(analysis)
            db.commit()
        except Exception as exc:
            db.rollback()
            fallback = _fallback_answer(payload.message, context_items)
            full_response = fallback
            yield _sse({"text": fallback})
            yield _sse("[DONE]")

            analysis = Analysis(
                user_id=payload.user_id,
                team_id=payload.team_id,
                question=payload.message,
                response=full_response,
            )
            db.add(analysis)
            db.commit()
            print(f"Chat model unavailable, returned retrieval fallback: {exc}")

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/history/{user_id}", response_model=list[AnalysisRead])
def chat_history(user_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(Analysis)
        .where(Analysis.user_id == user_id)
        .order_by(Analysis.created_at.desc())
        .limit(20)
    ).all()
