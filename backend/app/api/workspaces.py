from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.research_saved_paper import ResearchSavedPaper
from app.models.research_workspace import ResearchWorkspace
from app.schemas.research import ResearchPaper
from app.schemas.workspace import WorkspaceCreate, WorkspaceDetail, WorkspaceSummary, WorkspaceUpdate


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _paper_schema(record: ResearchSavedPaper) -> ResearchPaper:
    return ResearchPaper(
        source=record.source,
        external_id=record.external_id,
        title=record.title,
        abstract=record.abstract,
        authors=record.authors or [],
        venue=record.venue,
        year=record.year,
        publication_date=record.publication_date,
        doi=record.doi,
        url=record.url,
        pdf_url=record.pdf_url,
        citation_count=record.citation_count,
        open_access=record.open_access,
    )


def _workspace_summary(workspace: ResearchWorkspace) -> WorkspaceSummary:
    return WorkspaceSummary(
        id=workspace.id,
        title=workspace.title,
        notes=workspace.notes,
        saved_paper_count=len(workspace.saved_papers),
        search_count=len(workspace.searches),
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


@router.get("/", response_model=list[WorkspaceSummary])
def list_workspaces(db: Session = Depends(get_db)):
    workspaces = db.scalars(
        select(ResearchWorkspace)
        .options(selectinload(ResearchWorkspace.saved_papers), selectinload(ResearchWorkspace.searches))
        .order_by(ResearchWorkspace.updated_at.desc())
    ).all()
    return [_workspace_summary(workspace) for workspace in workspaces]


@router.post("/", response_model=WorkspaceDetail, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)):
    workspace = ResearchWorkspace(title=payload.title.strip() or "New workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return WorkspaceDetail(
        **_workspace_summary(workspace).model_dump(),
        saved_papers=[],
        searches=[],
    )


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(workspace_id: int, db: Session = Depends(get_db)):
    workspace = db.scalar(
        select(ResearchWorkspace)
        .where(ResearchWorkspace.id == workspace_id)
        .options(selectinload(ResearchWorkspace.saved_papers), selectinload(ResearchWorkspace.searches))
    )
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    return WorkspaceDetail(
        **_workspace_summary(workspace).model_dump(),
        saved_papers=[_paper_schema(record) for record in workspace.saved_papers],
        searches=[
            {
                "id": search.id,
                "query": search.query,
                "sources": search.sources or [],
                "result_count": search.result_count,
                "created_at": search.created_at,
            }
            for search in sorted(workspace.searches, key=lambda item: item.created_at, reverse=True)
        ],
    )


@router.patch("/{workspace_id}", response_model=WorkspaceSummary)
def update_workspace(workspace_id: int, payload: WorkspaceUpdate, db: Session = Depends(get_db)):
    workspace = db.scalar(
        select(ResearchWorkspace)
        .where(ResearchWorkspace.id == workspace_id)
        .options(selectinload(ResearchWorkspace.saved_papers), selectinload(ResearchWorkspace.searches))
    )
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    if payload.title is not None:
        workspace.title = payload.title.strip() or "New workspace"
    if payload.notes is not None:
        workspace.notes = payload.notes

    db.commit()
    db.refresh(workspace)
    return _workspace_summary(workspace)


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: int, db: Session = Depends(get_db)):
    workspace = db.get(ResearchWorkspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    db.delete(workspace)
    db.commit()
    return {"message": "Workspace removed"}


@router.post("/{workspace_id}/papers", response_model=ResearchPaper, status_code=status.HTTP_201_CREATED)
def save_paper(workspace_id: int, payload: ResearchPaper, db: Session = Depends(get_db)):
    workspace = db.get(ResearchWorkspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    paper = ResearchSavedPaper(
        workspace_id=workspace_id,
        source=payload.source,
        external_id=payload.external_id,
        title=payload.title,
        abstract=payload.abstract,
        authors=payload.authors,
        venue=payload.venue,
        year=payload.year,
        publication_date=payload.publication_date,
        doi=payload.doi,
        url=payload.url,
        pdf_url=payload.pdf_url,
        citation_count=payload.citation_count,
        open_access=payload.open_access,
    )
    db.add(paper)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Paper already saved in workspace") from exc

    return payload


@router.delete("/{workspace_id}/papers/{source}/{external_id:path}")
def delete_paper(workspace_id: int, source: str, external_id: str, db: Session = Depends(get_db)):
    paper = db.scalar(
        select(ResearchSavedPaper).where(
            ResearchSavedPaper.workspace_id == workspace_id,
            ResearchSavedPaper.source == source,
            ResearchSavedPaper.external_id == external_id,
        )
    )
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved paper not found")

    db.delete(paper)
    db.commit()
    return {"message": "Saved paper removed"}
