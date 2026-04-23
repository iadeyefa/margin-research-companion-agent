import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.team import Team
from app.schemas.chat import AnalysisRead, ChatRequest
from app.services.llm import analysis_chain
from app.services.pinecone import retrieve_similar_games

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(payload: dict[str, str] | str) -> str:
    if isinstance(payload, str):
        return f"data: {payload}\n\n"
    return f"data: {json.dumps(payload)}\n\n"


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
        similar_games = await retrieve_similar_games(payload.message, 5)
    except Exception as exc:
        print(f"Skipping Pinecone retrieval: {exc}")
        similar_games = []

    rag_context = "\n\n".join(
        str(game.get("metadata", {}).get("text", ""))
        for game in similar_games
        if game.get("metadata", {}).get("text")
    )
    context = rag_context or team_context or "No specific game data available"

    async def stream_response():
        full_response = ""
        try:
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
            yield _sse({"error": str(exc)})

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
