from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchSavedPaper(Base):
    __tablename__ = "research_saved_papers"
    __table_args__ = (UniqueConstraint("workspace_id", "source", "external_id", name="uq_saved_paper_workspace_source_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("research_workspaces.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    abstract_override: Mapped[Optional[str]] = mapped_column(Text)
    authors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    venue: Mapped[Optional[str]] = mapped_column(String(512))
    year: Mapped[Optional[int]] = mapped_column(Integer)
    publication_date: Mapped[Optional[str]] = mapped_column(String(32))
    doi: Mapped[Optional[str]] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(Text)
    pdf_url: Mapped[Optional[str]] = mapped_column(Text)
    citation_count: Mapped[Optional[int]] = mapped_column(Integer)
    open_access: Mapped[Optional[bool]] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    workspace = relationship("ResearchWorkspace", back_populates="saved_papers")
