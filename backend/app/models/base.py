"""Shared helpers for the SQLModel tables.

The domain stores timestamps as ISO-8601 strings rather than native datetimes:
they round-trip identically through SQLite and JSON, and every comparison in
the schedule logic is a lexicographic string compare that sorts correctly.
"""

from datetime import UTC, date, datetime


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


# Kept as public aliases: callers across the app import these by name.
def utcnow() -> str:
    return now_iso()


def today_iso() -> str:
    return date.today().isoformat()
