from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

_local = threading.local()
_wal_initialized = False
_wal_lock = threading.Lock()


def db_path() -> Path:
    from quicklingo.paths import user_data_dir

    return user_data_dir() / "history.db"


def get_connection() -> sqlite3.Connection:
    global _wal_initialized
    conn = getattr(_local, "connection", None)
    if conn is None:
        conn = sqlite3.connect(db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Foreign keys are per-connection; always enable on a new handle.
        conn.execute("PRAGMA foreign_keys=ON")
        _local.connection = conn
    with _wal_lock:
        if not _wal_initialized:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            _wal_initialized = True
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Yield thread-local connection; commit on success, rollback on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def fetch_one(sql: str, params: Sequence[object] = ()) -> sqlite3.Row | None:
    """Run a read query on the thread-local connection and return the first row."""
    return get_connection().execute(sql, params).fetchone()


def fetch_all(sql: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
    """Run a read query on the thread-local connection and return all rows."""
    return get_connection().execute(sql, params).fetchall()


def scalar_int(sql: str, params: Sequence[object] = (), *, default: int = 0) -> int:
    """Return the first column of the first row as int (e.g. COUNT queries)."""
    row = get_connection().execute(sql, params).fetchone()
    if row is None:
        return default
    value = row[0]
    return int(value) if value is not None else default


def in_placeholders(count: int) -> str:
    """Build a comma-separated ``?`` placeholder list for an ``IN (...)`` clause."""
    return ",".join("?" * count)


def close_all() -> None:
    global _wal_initialized
    conn = getattr(_local, "connection", None)
    if conn is not None:
        conn.close()
        _local.connection = None
    with _wal_lock:
        _wal_initialized = False
