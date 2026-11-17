import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pages.notes._support import store as notes_store
from pages.notes._support.store import NoteStore


class NoteStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = NoteStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_add_and_all(self):
        self.store.add("BUY MILK")
        notes = self.store.all()
        self.assertEqual([(note.text, note.done) for note in notes],
                         [("BUY MILK", False)])

    def test_add_trims_and_truncates(self):
        self.store.add("  " + "A" * 50 + "  ")
        self.assertEqual(self.store.all()[0].text, "A" * 32)

    def test_empty_note_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.add("   ")
        self.assertEqual(self.store.all(), ())

    def test_toggle_and_back(self):
        self.store.add("ONE")
        note = self.store.all()[0]
        self.store.toggle(note)
        self.assertTrue(self.store.all()[0].done)
        self.store.toggle(note)
        self.assertFalse(self.store.all()[0].done)

    def test_delete_keeps_the_others(self):
        self.store.add("ONE")
        self.store.add("TWO")
        first = self.store.all()[0]
        self.store.delete(first)
        self.assertEqual([note.text for note in self.store.all()], ["TWO"])

    def test_creation_order_is_stable(self):
        for text in ("ONE", "TWO", "THREE"):
            self.store.add(text)
        self.assertEqual(
            [note.text for note in self.store.all()],
            ["ONE", "TWO", "THREE"],
        )

    def test_move_up_and_down(self):
        for text in ("ONE", "TWO", "THREE"):
            self.store.add(text)
        notes = self.store.all()
        self.store.move(notes[2], -1)
        self.assertEqual(
            [note.text for note in self.store.all()],
            ["ONE", "THREE", "TWO"],
        )
        moved = self.store.all()[1]
        self.store.move(moved, 1)
        self.assertEqual(
            [note.text for note in self.store.all()],
            ["ONE", "TWO", "THREE"],
        )

    def test_move_at_the_boundaries_is_a_no_op(self):
        self.store.add("ONE")
        self.store.add("TWO")
        notes = self.store.all()
        self.store.move(notes[0], -1)
        self.store.move(notes[1], 1)
        self.assertEqual(
            [note.text for note in self.store.all()],
            ["ONE", "TWO"],
        )

    def test_migrates_a_store_without_positions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "notes.sqlite3")
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE notes ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)"
            )
            conn.execute("INSERT INTO notes (text, done) VALUES ('OLD', 0)")
            conn.commit()
            conn.close()

            store = NoteStore(path)
            self.assertEqual([note.text for note in store.all()], ["OLD"])
            store.add("NEW")
            self.assertEqual(
                [note.text for note in store.all()], ["OLD", "NEW"]
            )
            store.close()

    def test_limit(self):
        with patch.object(notes_store, "MAX_NOTES", 1):
            self.store.add("ONE")
            with self.assertRaises(ValueError):
                self.store.add("TWO")
        self.assertEqual(len(self.store.all()), 1)


if __name__ == "__main__":
    unittest.main()
