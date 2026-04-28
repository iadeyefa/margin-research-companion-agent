from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchSearch(Base):
    __tablename__ = "research_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("research_workspaces.id", ondelete="CASCADE"))
    query: Mapped[str] = mapped_column(String(512), nullable=False)
    sources: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    workspace = relationship("ResearchWorkspace", back_populates="searches")
