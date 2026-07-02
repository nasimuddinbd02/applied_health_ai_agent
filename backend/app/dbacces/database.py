"""Database access object: owns the SQLite engine and hands out sessions."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from app.common.config import settings


class Database:
    """Encapsulates the engine + session lifecycle.

    ``expire_on_commit=False`` keeps column attributes accessible after a
    session closes, so repositories can return detached ORM objects.
    """

    def __init__(self, url: str) -> None:
        self._ensure_sqlite_dir(url)
        # check_same_thread=False so the engine can be shared by FastAPI workers
        # and the separate FastMCP tool process (both hit the same SQLite file).
        self.engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})

    @staticmethod
    def _ensure_sqlite_dir(url: str) -> None:
        """Create the parent folder for a file-based SQLite DB if missing."""
        prefix = "sqlite:///"
        if url.startswith(prefix):
            path = url[len(prefix):]
            if path and path != ":memory:":
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)

    def init(self) -> None:
        """Create all tables. Import models first so they register on metadata."""
        import app.models.entities  # noqa: F401  (registers tables on metadata)

        SQLModel.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as session:
            yield session


# Default application database instance (composition root wires repos onto it).
database = Database(settings.database_url)

# Back-compat module-level helpers used by scripts (seed) and tests.
engine = database.engine


def init_db() -> None:
    database.init()


@contextmanager
def session_scope() -> Iterator[Session]:
    with database.session() as session:
        yield session
