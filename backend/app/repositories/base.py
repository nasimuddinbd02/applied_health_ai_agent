"""Base repository: holds the Database and exposes the session helper."""

from app.db.session import Database


class BaseRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def _session(self):
        return self._db.session()
