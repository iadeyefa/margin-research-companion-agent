import pytest

from app import models  # noqa: F401
from app.db.base import Base
from app.db.migrations import apply_sqlite_migrations
from app.db.session import engine


@pytest.fixture(autouse=True)
def ensure_schema():
    Base.metadata.create_all(bind=engine)
    apply_sqlite_migrations()
