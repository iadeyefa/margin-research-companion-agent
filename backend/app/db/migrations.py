"""Lightweight SQLite column adds (create_all does not ALTER existing tables)."""

from sqlalchemy import inspect, text

from app.db.session import engine


def apply_sqlite_migrations() -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    with engine.begin() as conn:
        if inspector.has_table("research_saved_papers"):
            cols = {c["name"] for c in inspector.get_columns("research_saved_papers")}
            if "abstract_override" not in cols:
                conn.execute(text("ALTER TABLE research_saved_papers ADD COLUMN abstract_override TEXT"))
        if not inspector.has_table("research_workspace_briefs"):
            conn.execute(
                text(
                    """
                    CREATE TABLE research_workspace_briefs (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        workspace_id INTEGER NOT NULL,
                        mode VARCHAR(32) NOT NULL,
                        style VARCHAR(32) NOT NULL DEFAULT 'balanced',
                        title VARCHAR(512) NOT NULL,
                        body TEXT NOT NULL,
                        source_papers JSON NOT NULL DEFAULT '[]',
                        created_at DATETIME NOT NULL,
                        FOREIGN KEY(workspace_id) REFERENCES research_workspaces (id) ON DELETE CASCADE
                    )
                    """
                )
            )
        else:
            brief_cols = {c["name"] for c in inspector.get_columns("research_workspace_briefs")}
            if "style" not in brief_cols:
                conn.execute(
                    text("ALTER TABLE research_workspace_briefs ADD COLUMN style VARCHAR(32) NOT NULL DEFAULT 'balanced'")
                )
            if "source_papers" not in brief_cols:
                conn.execute(
                    text("ALTER TABLE research_workspace_briefs ADD COLUMN source_papers JSON NOT NULL DEFAULT '[]'")
                )
        if not inspector.has_table("research_workspace_state"):
            conn.execute(
                text(
                    """
                    CREATE TABLE research_workspace_state (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        workspace_id INTEGER NOT NULL,
                        state_key VARCHAR(64) NOT NULL,
                        value JSON NOT NULL,
                        updated_at DATETIME NOT NULL,
                        FOREIGN KEY(workspace_id) REFERENCES research_workspaces (id) ON DELETE CASCADE,
                        CONSTRAINT uq_workspace_state_key UNIQUE (workspace_id, state_key)
                    )
                    """
                )
            )
        if not inspector.has_table("research_paper_notes"):
            conn.execute(
                text(
                    """
                    CREATE TABLE research_paper_notes (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        workspace_id INTEGER NOT NULL,
                        source VARCHAR(64) NOT NULL,
                        external_id VARCHAR(512) NOT NULL,
                        note TEXT NOT NULL DEFAULT '',
                        updated_at DATETIME NOT NULL,
                        FOREIGN KEY(workspace_id) REFERENCES research_workspaces (id) ON DELETE CASCADE,
                        CONSTRAINT uq_paper_note_workspace_paper UNIQUE (workspace_id, source, external_id)
                    )
                    """
                )
            )
