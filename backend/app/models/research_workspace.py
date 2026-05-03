from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchWorkspace(Base):
    __tablename__ = "research_workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    saved_papers = relationship(
        "ResearchSavedPaper",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="ResearchSavedPaper.id.desc()",
    )
    searches = relationship(
        "ResearchSearch",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="ResearchSearch.created_at.desc()",
    )
    briefs = relationship(
        "ResearchWorkspaceBrief",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="ResearchWorkspaceBrief.id.desc()",
    )
    state_entries = relationship(
        "ResearchWorkspaceState",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    paper_notes = relationship(
        "ResearchPaperNote",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="ResearchPaperNote.updated_at.desc()",
    )
