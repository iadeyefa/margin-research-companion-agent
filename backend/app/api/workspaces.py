from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.research_saved_paper import ResearchSavedPaper
from app.models.research_workspace import ResearchWorkspace
from app.models.research_workspace_brief import ResearchWorkspaceBrief
from app.models.research_workspace_state import ResearchPaperNote, ResearchWorkspaceState
from app.schemas.research import ResearchPaper
from app.schemas.workspace import (
    LibraryPaper,
    PaperNoteRead,
    PaperNoteUpdate,
    SavedPaperUpdate,
    WorkspaceBriefCreate,
    WorkspaceBriefRead,
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceSummary,
    WorkspaceStateRead,
    WorkspaceStateUpdate,
    WorkspaceUpdate,
)


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


library_router = APIRouter(prefix="/library", tags=["library"])


@library_router.get("/papers", response_model=list[LibraryPaper])
def list_library_papers(db: Session = Depends(get_db)):
    records = db.scalars(
        select(ResearchSavedPaper)
        .options(selectinload(ResearchSavedPaper.workspace))
        .order_by(ResearchSavedPaper.created_at.desc())
    ).all()

    return [
        LibraryPaper(
            source=record.source,
            external_id=record.external_id,
            title=record.title,
            abstract=record.abstract,
            abstract_override=record.abstract_override,
            authors=record.authors or [],
            venue=record.venue,
            year=record.year,
            publication_date=record.publication_date,
            doi=record.doi,
            url=record.url,
            pdf_url=record.pdf_url,
            citation_count=record.citation_count,
            open_access=record.open_access,
            workspace_id=record.workspace_id,
            workspace_title=record.workspace.title if record.workspace else "",
            saved_at=record.created_at,
        )
        for record in records
    ]


def _brief_schema(record: ResearchWorkspaceBrief) -> WorkspaceBriefRead:
    return WorkspaceBriefRead(
        id=record.id,
        mode=record.mode,
        style=record.style,
        title=record.title,
        body=record.body,
        source_papers=record.source_papers or [],
        created_at=record.created_at,
    )


def _state_schema(record: ResearchWorkspaceState) -> WorkspaceStateRead:
    return WorkspaceStateRead(
        state_key=record.state_key,
        value=record.value or {},
        updated_at=record.updated_at,
    )


def _paper_note_schema(record: ResearchPaperNote) -> PaperNoteRead:
    return PaperNoteRead(
        source=record.source,
        external_id=record.external_id,
        note=record.note,
        updated_at=record.updated_at,
    )


def _paper_schema(record: ResearchSavedPaper) -> ResearchPaper:
    return ResearchPaper(
        source=record.source,
        external_id=record.external_id,
        title=record.title,
        abstract=record.abstract,
        abstract_override=record.abstract_override,
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
        briefs=[],
        state=[],
        paper_notes=[],
    )


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(workspace_id: int, db: Session = Depends(get_db)):
    workspace = db.scalar(
        select(ResearchWorkspace)
        .where(ResearchWorkspace.id == workspace_id)
        .options(
            selectinload(ResearchWorkspace.saved_papers),
            selectinload(ResearchWorkspace.searches),
            selectinload(ResearchWorkspace.briefs),
            selectinload(ResearchWorkspace.state_entries),
            selectinload(ResearchWorkspace.paper_notes),
        )
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
        briefs=[_brief_schema(b) for b in workspace.briefs],
        state=[_state_schema(s) for s in workspace.state_entries],
        paper_notes=[_paper_note_schema(n) for n in workspace.paper_notes],
    )


@router.post(
    "/{workspace_id}/briefs",
    response_model=WorkspaceBriefRead,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace_brief(workspace_id: int, payload: WorkspaceBriefCreate, db: Session = Depends(get_db)):
    workspace = db.get(ResearchWorkspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    mode = payload.mode.strip()[:32] or "unknown"
    style = payload.style.strip()[:32] or "balanced"
    title = (payload.title.strip() or "Untitled")[:512]
    body = payload.body.strip() if payload.body else ""
    if len(body) > 500_000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Brief body too large")

    row = ResearchWorkspaceBrief(
        workspace_id=workspace_id,
        mode=mode,
        style=style,
        title=title,
        body=body,
        source_papers=[p.model_dump() for p in payload.source_papers],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _brief_schema(row)


@router.delete("/{workspace_id}/briefs/{brief_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_brief(workspace_id: int, brief_id: int, db: Session = Depends(get_db)):
    row = db.scalar(
        select(ResearchWorkspaceBrief).where(
            ResearchWorkspaceBrief.id == brief_id,
            ResearchWorkspaceBrief.workspace_id == workspace_id,
        )
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{workspace_id}/state/{state_key}", response_model=WorkspaceStateRead)
def upsert_workspace_state(
    workspace_id: int,
    state_key: str,
    payload: WorkspaceStateUpdate,
    db: Session = Depends(get_db),
):
    workspace = db.get(ResearchWorkspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    key = state_key.strip()[:64]
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="State key is required")
    row = db.scalar(
        select(ResearchWorkspaceState).where(
            ResearchWorkspaceState.workspace_id == workspace_id,
            ResearchWorkspaceState.state_key == key,
        )
    )
    if not row:
        row = ResearchWorkspaceState(workspace_id=workspace_id, state_key=key, value=payload.value)
        db.add(row)
    else:
        row.value = payload.value
    db.commit()
    db.refresh(row)
    return _state_schema(row)


@router.put("/{workspace_id}/paper-notes/{source}/{external_id:path}", response_model=PaperNoteRead)
def upsert_paper_note(
    workspace_id: int,
    source: str,
    external_id: str,
    payload: PaperNoteUpdate,
    db: Session = Depends(get_db),
):
    workspace = db.get(ResearchWorkspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    note = payload.note.strip()
    row = db.scalar(
        select(ResearchPaperNote).where(
            ResearchPaperNote.workspace_id == workspace_id,
            ResearchPaperNote.source == source,
            ResearchPaperNote.external_id == external_id,
        )
    )
    if not row:
        row = ResearchPaperNote(workspace_id=workspace_id, source=source, external_id=external_id, note=note)
        db.add(row)
    else:
        row.note = note
    db.commit()
    db.refresh(row)
    return _paper_note_schema(row)


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

    duplicate_checks = [
        (
            ResearchSavedPaper.source == payload.source,
            ResearchSavedPaper.external_id == payload.external_id,
        )
    ]
    if payload.doi:
        duplicate_checks.append((ResearchSavedPaper.doi == payload.doi,))
    if payload.title:
        duplicate_checks.append((ResearchSavedPaper.title == payload.title, ResearchSavedPaper.year == payload.year))
    existing = db.scalar(
        select(ResearchSavedPaper).where(
            ResearchSavedPaper.workspace_id == workspace_id,
            or_(*[cond[0] if len(cond) == 1 else (cond[0] & cond[1]) for cond in duplicate_checks]),
        )
    )
    if existing:
        return _paper_schema(existing)

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
        abstract_override=payload.abstract_override,
    )
    db.add(paper)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Paper already saved in workspace") from exc

    return payload


@router.patch("/{workspace_id}/papers/{source}/{external_id:path}", response_model=ResearchPaper)
def patch_saved_paper(
    workspace_id: int,
    source: str,
    external_id: str,
    payload: SavedPaperUpdate,
    db: Session = Depends(get_db),
):
    paper = db.scalar(
        select(ResearchSavedPaper).where(
            ResearchSavedPaper.workspace_id == workspace_id,
            ResearchSavedPaper.source == source,
            ResearchSavedPaper.external_id == external_id,
        )
    )
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved paper not found")

    data = payload.model_dump(exclude_unset=True)
    if "abstract_override" in data:
        val = data["abstract_override"]
        if val is None:
            paper.abstract_override = None
        else:
            paper.abstract_override = val.strip() or None
    db.commit()
    db.refresh(paper)
    return _paper_schema(paper)


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
