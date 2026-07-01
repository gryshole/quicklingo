from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

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


def close_all() -> None:
    conn = getattr(_local, "connection", None)
    if conn is not None:
        conn.close()
        _local.connection = None
