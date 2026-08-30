"""Database access object: owns the engine and hands out sessions.

Runs on SQLite (local development, the default) and on PostgreSQL (the
database the design document specifies for a real deployment, and the only
safe choice once more than one pod writes). The dialect differences are
confined to this module.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings


class Database:
    """Encapsulates the engine + session lifecycle.

    ``expire_on_commit=False`` keeps column attributes accessible after a
    session closes, so repositories can return detached ORM objects.
    """

    def __init__(self, url: str) -> None:
        self._ensure_sqlite_dir(url)
        options: dict = {"echo": False}
        if url.startswith("sqlite"):
            # check_same_thread=False so the engine can be shared by FastAPI
            # workers and the separate FastMCP tool process (both hit the same
            # SQLite file).
            options["connect_args"] = {"check_same_thread": False}
        else:
            # A server database sits behind a pooler or a load balancer that
            # will drop idle connections; verify one before handing it out
            # rather than failing the request that happens to get it.
            options["pool_pre_ping"] = True
            options["pool_recycle"] = 300
        self.engine = create_engine(url, **options)

    @property
    def is_sqlite(self) -> bool:
        return self.engine.dialect.name == "sqlite"

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
        """Create all tables, then apply additive column migrations."""
        import app.models  # noqa: F401  (registers tables on metadata)

        SQLModel.metadata.create_all(self.engine)
        if self.is_sqlite:
            self.migrate()

    def migrate(self) -> None:
        """Add columns that exist on the models but not yet in the database.

        **SQLite only.** It reads ``sqlite_master`` and ``PRAGMA table_info``,
        so ``init()`` skips it on any other dialect. On PostgreSQL,
        ``create_all`` covers a fresh database and anything beyond that wants a
        real migration tool (Alembic) — see docs/deployment.md.

        ``create_all`` only creates missing *tables* — it never alters an
        existing one, so a database created before the realtime renovation is
        missing e.g. ``chatmessage.message_id``. SQLite supports additive
        ``ALTER TABLE ... ADD COLUMN`` cheaply, which covers every schema change
        this renovation makes. Anything destructive (drops, type changes) is out
        of scope here and would want a real migration tool.
        """
        import app.models  # noqa: F401

        with self.engine.begin() as conn:
            for table in SQLModel.metadata.sorted_tables:
                if not self._table_exists(conn, table.name):
                    continue
                existing = self._column_names(conn, table.name)
                for column in table.columns:
                    if column.name in existing or column.primary_key:
                        continue
                    ddl = self._add_column_ddl(table.name, column)
                    if ddl:
                        conn.exec_driver_sql(ddl)

    @staticmethod
    def _table_exists(conn, table_name: str) -> bool:
        rows = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchall()
        return bool(rows)

    @staticmethod
    def _column_names(conn, table_name: str) -> set[str]:
        rows = conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
        return {row[1] for row in rows}

    @staticmethod
    def _add_column_ddl(table_name: str, column) -> str | None:
        """Build ``ALTER TABLE ADD COLUMN`` with a constant default.

        SQLite requires a *constant* default when adding a NOT NULL column, so
        columns whose default is computed in Python (e.g. ``created_at``) are
        added as nullable and filled by the ORM on write.
        """
        try:
            column_type = column.type.compile(dialect=None)
        except Exception:  # noqa: BLE001 — unknown type: leave it to a real migration
            return None
        parts = [f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {column_type}']
        default = getattr(column, "default", None)
        if default is not None and not getattr(default, "is_callable", False):
            value = default.arg
            if isinstance(value, str):
                escaped = value.replace("'", "''")
                parts.append(f"NOT NULL DEFAULT '{escaped}'")
            elif isinstance(value, bool):
                parts.append(f"NOT NULL DEFAULT {int(value)}")
            elif isinstance(value, (int, float)):
                parts.append(f"NOT NULL DEFAULT {value}")
        return " ".join(parts)

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


if __name__ == "__main__":
    # `python -m app.db.session` — create the schema and stop.
    #
    # Kept distinct from `python -m app.db.seed`, which DELETES every row
    # before inserting its sample data. Deployment tooling wants this one: it
    # is safe to run on every start, including against a database with real
    # data in it.
    init_db()
    print(f"Schema ready on {database.engine.url.render_as_string(hide_password=True)}")
