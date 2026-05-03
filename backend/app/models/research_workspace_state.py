from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchWorkspaceState(Base):
    __tablename__ = "research_workspace_state"
    __table_args__ = (
        UniqueConstraint("workspace_id", "state_key", name="uq_workspace_state_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("research_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    state_key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    workspace = relationship("ResearchWorkspace", back_populates="state_entries")


class ResearchPaperNote(Base):
    __tablename__ = "research_paper_notes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "source", "external_id", name="uq_paper_note_workspace_paper"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("research_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(512), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    workspace = relationship("ResearchWorkspace", back_populates="paper_notes")
