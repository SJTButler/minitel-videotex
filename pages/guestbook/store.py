"""SQLite storage for the example guestbook."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "guestbook.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    handle TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Entry:
    handle: str
    message: str
    created_at: str


class GuestbookStore:
    def __init__(self, path=DEFAULT_PATH):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def add(self, handle, message):
        handle = (handle or "").strip()[:16] or "ANON"
        message = (message or "").strip()[:80]
        if not message:
            raise ValueError("message required")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.conn.execute(
            "INSERT INTO entries (handle, message, created_at) VALUES (?, ?, ?)",
            (handle, message, created_at),
        )
        self.conn.commit()

    def recent(self, limit=3):
        rows = self.conn.execute(
            "SELECT handle, message, created_at FROM entries "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            Entry(row["handle"], row["message"], row["created_at"])
            for row in rows
        ]

    def close(self):
        self.conn.close()
