import json

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
from app.services.pinecone import retrieve_similar_games

router = APIRouter(prefix="/chat", tags=["chat"])

PLAYOFF_TERMS = ("playoff", "playoffs", "finals", "championship", "title")
PREDICTION_TERMS = ("who will win", "predict", "winner", "champion", "finals")
CURRENT_TERMS = ("this year", "this year's", "current", "2026")


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
    if _is_prediction_question(question):
        return (
            f"{question} NBA playoffs contender team performance wins losses scoring rebounds assists "
            "field goal percentage three point percentage plus-minus championship"
        )
    if _is_playoff_question(question):
        return f"{question} NBA playoffs postseason team performance box score plus-minus"
    return question


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
        metadata_filter = None
        if _is_playoff_question(payload.message) and _is_current_question(payload.message):
            metadata_filter = {"$and": [{"game_type": {"$eq": "Playoffs"}}, {"season_year": {"$eq": 2026}}]}
        elif _is_playoff_question(payload.message):
            metadata_filter = {"game_type": {"$eq": "Playoffs"}}
        similar_games = await retrieve_similar_games(
            _retrieval_query(payload.message),
            12 if _is_prediction_question(payload.message) else 8,
            metadata_filter=metadata_filter,
        )
    except Exception as exc:
        print(f"Skipping Pinecone retrieval: {exc}")
        similar_games = []

    context_items = _retrieved_text(similar_games)
    rag_context = "\n\n".join(context_items)
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
