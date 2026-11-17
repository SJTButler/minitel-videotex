import unittest
from unittest.mock import patch

import pages

from minitel import M1, Session
from pages.notes._support import store as notes_store
from pages.notes._support.store import NoteStore

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SUITE = bytes([0x13, 0x48])
ANNULATION = bytes([0x13, 0x45])
CORRECTION = bytes([0x13, 0x47])


def make_session(store=None):
    registry = pages.build_registry()
    if store is None:
        store = NoteStore(":memory:")
    session = Session(
        registry,
        M1,
        initial="100",
        fallback=registry.get("100"),
    )
    session.state["notes_store"] = store
    session.start()
    session.navigate("180")
    return session, store


class NotesPageTests(unittest.TestCase):
    def test_page_is_registered_without_a_menu_alias(self):
        registry = pages.build_registry()
        page = registry.get("180")
        self.assertEqual(page.title, "NOTES")
        self.assertEqual(registry.aliases_for(page), ())
        self.assertTrue(page.form)
        self.assertEqual(
            tuple(region.name for region in page.regions),
            ("items", "entry"),
        )

    def test_empty_layout(self):
        session, _store = make_session()
        screen = session.render()
        text = screen.to_text().splitlines()
        self.assertIn("NOTES", text[2])
        self.assertIn("EMPTY", text[2])
        self.assertIn("NO NOTES YET", text[4])
        self.assertTrue(text[16].startswith("NEW NOTE"))
        self.assertTrue(text[17].startswith("> "))
        self.assertIn("ENVOI: ADD", text[19])
        self.assertIn("RETOUR=BACK", text[22])
        self.assertEqual(session.focused_region, "entry")
        self.assertEqual(session.active_field.name, "note")
        self.assertEqual((screen.cursor_row, screen.cursor_col), (17, 2))

    def test_add_note(self):
        session, store = make_session()
        session.feed(b"BUY MILK")
        self.assertEqual(session.line, "BUY MILK")
        session.feed(ENVOI)
        notes = store.all()
        self.assertEqual([(note.text, note.done) for note in notes],
                         [("BUY MILK", False)])
        self.assertEqual(session.line, "")
        self.assertEqual(session.focused_region, "entry")
        text = session.screen.to_text()
        self.assertIn("BUY MILK", text)
        self.assertIn("1-1/1", text.splitlines()[2])

    def test_empty_note_is_not_added(self):
        session, store = make_session()
        session.feed(ENVOI)
        self.assertEqual(store.all(), ())
        self.assertIn("TYPE A NOTE", session.screen.to_text())
        self.assertEqual(session.focused_region, "entry")

    def test_suite_moves_to_the_list(self):
        session, _store = make_session()
        session.feed(SUITE)
        self.assertEqual(session.focused_region, "items")
        self.assertFalse(session.screen.cursor_visible)
        text = session.screen.to_text().splitlines()
        self.assertIn("ENVOI: DONE", text[19])
        self.assertIn("CORRECTION: EDIT", text[19])
        self.assertIn("ANNULATION: DELETE", text[20])
        self.assertIn("*: UP", text[20])
        self.assertIn("#: DOWN", text[20])

    def test_star_is_text_in_the_entry_form(self):
        session, _store = make_session()
        session.feed(b"*")
        self.assertEqual(session.line, "*")

    def test_star_and_hash_move_the_selected_note(self):
        store = NoteStore(":memory:")
        for text in ("ONE", "TWO", "THREE"):
            store.add(text)
        session, _ = make_session(store)
        session.feed(SUITE)
        session.feed(b"#")
        self.assertEqual(
            [note.text for note in store.all()], ["TWO", "ONE", "THREE"]
        )
        self.assertEqual(session.regions["items"].cursor.selected, 1)
        self.assertIn("ONE", session.screen.to_text().splitlines()[4])

        session.feed(b"*")
        self.assertEqual(
            [note.text for note in store.all()], ["ONE", "TWO", "THREE"]
        )
        self.assertEqual(session.regions["items"].cursor.selected, 0)

    def test_move_at_a_boundary_keeps_the_selection(self):
        store = NoteStore(":memory:")
        store.add("ONE")
        store.add("TWO")
        session, _ = make_session(store)
        session.feed(SUITE)
        session.feed(b"*")
        self.assertEqual(
            [note.text for note in store.all()], ["ONE", "TWO"]
        )
        self.assertEqual(session.regions["items"].cursor.selected, 0)

    def test_correction_loads_the_selected_note_for_editing(self):
        store = NoteStore(":memory:")
        store.add("BUY MILK")
        store.add("CALL PLUMBER")
        session, _ = make_session(store)
        session.feed(SUITE)
        session.feed(SUITE)
        session.feed(CORRECTION)
        self.assertEqual(session.focused_region, "entry")
        self.assertEqual(session.line, "CALL PLUMBER")
        self.assertTrue(
            session.screen.to_text().splitlines()[16].startswith("EDIT NOTE")
        )

        session.feed(b" NOW")
        session.feed(ENVOI)
        self.assertEqual(
            [note.text for note in store.all()],
            ["BUY MILK", "CALL PLUMBER NOW"],
        )
        self.assertEqual(session.focused_region, "items")
        self.assertIsNone(session.state.get("notes_edit"))
        self.assertEqual(session.line, "")

    def test_empty_field_cancels_the_edit(self):
        store = NoteStore(":memory:")
        store.add("ONE")
        session, _ = make_session(store)
        session.feed(SUITE)
        session.feed(CORRECTION)
        session.feed(ANNULATION)
        session.feed(ENVOI)
        self.assertEqual([note.text for note in store.all()], ["ONE"])
        self.assertEqual(session.focused_region, "items")
        self.assertIsNone(session.state.get("notes_edit"))

    def test_correction_on_an_empty_list_does_nothing(self):
        session, store = make_session()
        session.feed(SUITE)
        session.feed(CORRECTION)
        self.assertEqual(session.focused_region, "items")
        self.assertEqual(session.line, "")
        self.assertEqual(store.all(), ())

    def test_envoi_toggles_the_selected_note(self):
        store = NoteStore(":memory:")
        store.add("ONE")
        store.add("TWO")
        session, _ = make_session(store)
        session.feed(SUITE)
        session.feed(ENVOI)
        notes = store.all()
        self.assertTrue(notes[0].done)
        self.assertFalse(notes[1].done)
        self.assertEqual(session.focused_region, "items")
        text = session.screen.to_text().splitlines()
        self.assertIn("[X]", text[3])
        self.assertIn("[ ]", text[4])

    def test_annulation_deletes_the_selected_note(self):
        store = NoteStore(":memory:")
        store.add("ONE")
        store.add("TWO")
        session, _ = make_session(store)
        session.feed(SUITE)
        session.feed(ANNULATION)
        self.assertEqual([note.text for note in store.all()], ["TWO"])
        self.assertEqual(session.focused_region, "items")
        self.assertEqual(session.regions["items"].cursor.selected, 0)
        self.assertIn("TWO", session.screen.to_text())

    def test_envoi_on_an_empty_list_does_nothing(self):
        session, store = make_session()
        session.feed(SUITE)
        session.feed(ENVOI)
        self.assertEqual(store.all(), ())
        self.assertEqual(session.focused_region, "items")

    def test_a_long_list_pages_at_twelve(self):
        store = NoteStore(":memory:")
        for index in range(13):
            store.add(f"NOTE {index + 1}")
        session, _ = make_session(store)
        session.feed(SUITE)
        self.assertIn("1-12/13", session.screen.to_text().splitlines()[2])
        for _ in range(12):
            session.feed(SUITE)
        self.assertEqual(session.regions["items"].cursor.selected, 12)
        text = session.screen.to_text().splitlines()
        self.assertIn("13-13/13", text[2])
        self.assertIn("NOTE 13", text[3])
        session.feed(SUITE)
        self.assertEqual(session.focused_region, "entry")

    def test_full_list_reports_the_limit(self):
        store = NoteStore(":memory:")
        store.add("ONE")
        store.add("TWO")
        session, _ = make_session(store)
        with patch.object(notes_store, "MAX_NOTES", 2):
            session.feed(b"THREE")
            session.feed(ENVOI)
        self.assertEqual(len(store.all()), 2)
        self.assertIn(
            "LIST FULL - DELETE DONE ITEMS", session.screen.to_text()
        )
        self.assertEqual(session.line, "THREE")

    def test_retour_leaves_from_the_entry_region(self):
        session, _store = make_session()
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "100")

    def test_retour_leaves_from_the_top_of_the_list(self):
        session, _store = make_session()
        session.feed(SUITE)
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "100")


class NotesResourceTests(unittest.TestCase):
    def test_session_close_closes_the_created_store(self):
        created = []

        class FakeStore:
            def __init__(self, path=None):
                self.closed = False
                created.append(self)

            def all(self):
                return ()

            def add(self, text):
                pass

            def toggle(self, note):
                pass

            def delete(self, note):
                pass

            def close(self):
                self.closed = True

        registry = pages.build_registry()
        session = Session(
            registry,
            M1,
            initial="180",
            fallback=registry.get("100"),
        )
        with patch("pages.notes.page.notes_store.NoteStore", FakeStore):
            session.start()
            self.assertEqual(len(created), 1)
            self.assertIs(session.state["notes_store"], created[0])
            session.close()

        self.assertTrue(created[0].closed)


if __name__ == "__main__":
    unittest.main()
