from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.team import Team
from app.schemas.team import TeamCreate, TeamRead

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{user_id}", response_model=list[TeamRead])
def get_teams(user_id: int, db: Session = Depends(get_db)):
    teams = db.scalars(
        select(Team)
        .where(Team.user_id == user_id)
        .options(selectinload(Team.games))
    ).all()

    for team in teams:
        team.games.sort(key=lambda game: game.date, reverse=True)
        team.games = team.games[:5]

    return teams


@router.post("/", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreate, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(Team).where(
            Team.user_id == payload.user_id,
            Team.team_name == payload.team_name,
            Team.sport == payload.sport,
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team already added")

    team = Team(user_id=payload.user_id, team_name=payload.team_name, sport=payload.sport)
    db.add(team)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add team") from exc
    db.refresh(team)
    return team


@router.delete("/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    db.delete(team)
    db.commit()
    return {"message": "Team removed"}
