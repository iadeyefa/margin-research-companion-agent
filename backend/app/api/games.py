from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.game import Game
from app.schemas.game import GameCreate, GameRead

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/{team_id}", response_model=list[GameRead])
def get_games(team_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(Game)
        .where(Game.team_id == team_id)
        .options(selectinload(Game.player_stats))
        .order_by(Game.date.desc())
    ).all()


@router.post("/", response_model=GameRead, status_code=status.HTTP_201_CREATED)
def create_game(payload: GameCreate, db: Session = Depends(get_db)):
    game = Game(
        team_id=payload.team_id,
        opponent=payload.opponent,
        score=payload.score,
        opponent_score=payload.opponent_score,
        date=payload.date,
        venue=payload.venue,
        game_status=payload.game_status,
    )
    db.add(game)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create game") from exc
    db.refresh(game)
    return game


@router.delete("/{game_id}")
def delete_game(game_id: int, db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    db.delete(game)
    db.commit()
    return {"message": "Game removed"}
