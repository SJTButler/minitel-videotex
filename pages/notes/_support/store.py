"""SQLite storage for the desk to-do list."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "notes.sqlite3"
MAX_NOTES = 99
MAX_TEXT = 32

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0
)
"""


@dataclass(frozen=True)
class Note:
    id: int
    text: str
    done: bool


class NoteStore:
    def __init__(self, path=DEFAULT_PATH):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, timeout=5.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(notes)")
        }
        if "position" not in columns:
            self.conn.execute(
                "ALTER TABLE notes ADD COLUMN position INTEGER NOT NULL "
                "DEFAULT 0"
            )
            self.conn.execute("UPDATE notes SET position = id")

    def add(self, text):
        text = (text or "").strip()[:MAX_TEXT]
        if not text:
            raise ValueError("note required")
        count = self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        if count >= MAX_NOTES:
            raise ValueError("note limit reached")
        position = self.conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM notes"
        ).fetchone()[0]
        self.conn.execute(
            "INSERT INTO notes (text, done, position) VALUES (?, 0, ?)",
            (text, position),
        )
        self.conn.commit()

    def all(self):
        rows = self.conn.execute(
            "SELECT id, text, done FROM notes ORDER BY position, id"
        ).fetchall()
        return tuple(
            Note(row["id"], row["text"], bool(row["done"])) for row in rows
        )

    def toggle(self, note):
        self.conn.execute(
            "UPDATE notes SET done = 1 - done WHERE id = ?", (note.id,)
        )
        self.conn.commit()

    def update(self, note_id, text):
        text = (text or "").strip()[:MAX_TEXT]
        if not text:
            raise ValueError("note required")
        self.conn.execute(
            "UPDATE notes SET text = ? WHERE id = ?", (text, note_id)
        )
        self.conn.commit()

    def move(self, note, delta):
        rows = self.conn.execute(
            "SELECT id, position FROM notes ORDER BY position, id"
        ).fetchall()
        index = next(
            (i for i, row in enumerate(rows) if row["id"] == note.id), None
        )
        if index is None:
            return
        other = index + delta
        if not 0 <= other < len(rows):
            return
        current, target = rows[index], rows[other]
        self.conn.execute(
            "UPDATE notes SET position = ? WHERE id = ?",
            (target["position"], current["id"]),
        )
        self.conn.execute(
            "UPDATE notes SET position = ? WHERE id = ?",
            (current["position"], target["id"]),
        )
        self.conn.commit()

    def delete(self, note):
        self.conn.execute("DELETE FROM notes WHERE id = ?", (note.id,))
        self.conn.commit()

    def close(self):
        self.conn.close()
