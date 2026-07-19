from __future__ import annotations

import sqlite3
from pathlib import Path

from quicklingo.db.connection import get_connection


def checkpoint_database() -> None:
    conn = get_connection()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def create_snapshot(dest: Path, *, source: Path | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    if source is None:
        checkpoint_database()
        source_conn = get_connection()
        dest_conn = sqlite3.connect(dest)
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
        return
    source_conn = sqlite3.connect(source)
    try:
        dest_conn = sqlite3.connect(dest)
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source_conn.close()
