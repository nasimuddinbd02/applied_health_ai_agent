"""Additive schema migration for databases created before the renovation.

``create_all`` only creates missing *tables* — an existing ``chatmessage``
would silently keep the old columns and every write would fail. These tests
run against a throwaway copy of the pre-renovation schema.
"""

import sqlite3

import pytest

from app.db.session import Database

PRE_RENOVATION_CHATMESSAGE = """
CREATE TABLE chatmessage (
    id INTEGER NOT NULL PRIMARY KEY,
    thread_id VARCHAR NOT NULL,
    patient_id INTEGER,
    role VARCHAR NOT NULL,
    content VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL
)
"""


@pytest.fixture
def legacy_db(tmp_path):
    """A database with the old chatmessage table and one row of real data."""
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    con.execute(PRE_RENOVATION_CHATMESSAGE)
    con.execute(
        "INSERT INTO chatmessage (thread_id, patient_id, role, content, created_at)"
        " VALUES ('thread-1', 3, 'patient', 'hello', '2026-01-01T00:00:00Z')"
    )
    con.commit()
    con.close()
    return path


def columns(path, table) -> list[str]:
    con = sqlite3.connect(path)
    try:
        return [row[1] for row in con.execute(f"PRAGMA table_info('{table}')")]
    finally:
        con.close()


def test_new_columns_are_added_to_an_existing_table(legacy_db):
    Database(f"sqlite:///{legacy_db}").init()

    added = columns(legacy_db, "chatmessage")
    assert "message_id" in added
    assert "correlation_id" in added


def test_existing_rows_survive_and_get_the_default(legacy_db):
    Database(f"sqlite:///{legacy_db}").init()

    con = sqlite3.connect(legacy_db)
    try:
        row = con.execute(
            "SELECT content, message_id, correlation_id FROM chatmessage"
        ).fetchone()
    finally:
        con.close()
    assert row == ("hello", "", "")


def test_the_new_conversation_table_is_created(legacy_db):
    Database(f"sqlite:///{legacy_db}").init()
    assert "conversation_id" in columns(legacy_db, "conversation")


def test_migrating_twice_is_a_no_op(legacy_db):
    db = Database(f"sqlite:///{legacy_db}")
    db.init()
    before = columns(legacy_db, "chatmessage")
    db.init()
    assert columns(legacy_db, "chatmessage") == before
