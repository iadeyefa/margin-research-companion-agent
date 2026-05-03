"""Lightweight SQLite column adds (create_all does not ALTER existing tables)."""

from sqlalchemy import inspect, text

from app.db.session import engine


def apply_sqlite_migrations() -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if not inspector.has_table("research_saved_papers"):
        return
    cols = {c["name"] for c in inspector.get_columns("research_saved_papers")}
    with engine.begin() as conn:
        if "abstract_override" not in cols:
            conn.execute(text("ALTER TABLE research_saved_papers ADD COLUMN abstract_override TEXT"))
