import unittest

import pages

from minitel import profiles
from minitel.session import Session
from pages.guestbook.store import GuestbookStore

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SUITE = bytes([0x13, 0x48])


class GuestbookFlowTests(unittest.TestCase):
    def setUp(self):
        self.registry = pages.build_registry()
        self.session = Session(
            self.registry,
            profiles.M1,
            initial="100",
            fallback=self.registry.get(pages.NOT_FOUND),
        )
        self.store = GuestbookStore(":memory:")
        self.session.state["guestbook_store"] = self.store
        self.session.start()
        self.session.navigate("4")

    def tearDown(self):
        self.store.close()

    def test_alias(self):
        self.assertIs(self.registry.get("4"), self.registry.get("140"))

    def test_form_layout(self):
        screen = self.session.render()
        self.assertEqual(self.session.active_field.name, "handle")
        self.assertEqual((screen.cursor_row, screen.cursor_col), (14, 9))
        self.assertEqual([field.col for field in self.session.fields], [9, 9])
        self.assertTrue(screen.cursor_visible)
        text = screen.to_text().splitlines()
        self.assertTrue(text[22].startswith("SUITE: MESSAGE"))
        self.assertIn("RETOUR: SORTIR", text[22])
        self.assertTrue(text[23].startswith("ENVOI: SUBMIT"))

    def test_dynamic_footer_follows_focus(self):
        actions = self.session.feed(SUITE)
        self.assertIn(b"(FIN)", actions[0].raw)
        self.assertIn(b"HANDLE", actions[0].raw)
        self.assertLess(len(actions[0].raw), 200)
        self.assertEqual(self.session.active_field.name, "message")
        text = self.session.screen.to_text().splitlines()
        self.assertIn("SUITE: (FIN)", text[22])
        self.assertIn("RETOUR: HANDLE", text[22])

        self.session.feed(RETOUR)
        self.assertEqual(self.session.active_field.name, "handle")
        text = self.session.screen.to_text().splitlines()
        self.assertIn("SUITE: MESSAGE", text[22])
        self.assertIn("RETOUR: SORTIR", text[22])

    def test_sign_flow(self):
        self.session.feed(b"ALICE")
        self.assertEqual(self.session.line, "ALICE")

        self.session.feed(SUITE)
        self.assertEqual(self.session.active_field.name, "message")
        self.session.feed(b"HELLO")

        actions = self.session.feed(ENVOI)
        self.assertEqual(self.session.current.number, "140")
        entries = self.store.recent(1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].handle, "ALICE")
        self.assertEqual(entries[0].message, "HELLO")

        screen = actions[-1].screen
        self.assertIn("ALICE", screen.to_text())
        self.assertIn("HELLO", screen.to_text())
        self.assertEqual(self.session.active_field.name, "handle")
        self.assertEqual(self.session.line, "")

    def test_focus_moves_between_fields(self):
        self.session.feed(b"ALICE")
        self.session.feed(SUITE)
        self.assertEqual(self.session.active_field.name, "message")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.active_field.name, "handle")
        self.assertEqual(self.session.line, "ALICE")

    def test_retour_from_first_field_goes_back(self):
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "100")

    def test_retour_from_message_does_not_leave_the_form(self):
        self.session.feed(SUITE)
        self.assertEqual(self.session.active_field.name, "message")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "140")
        self.assertEqual(self.session.active_field.name, "handle")

    def test_empty_handle(self):
        self.session.feed(SUITE)
        self.session.feed(b"MSG")
        actions = self.session.feed(ENVOI)
        self.assertEqual(self.session.current.number, "140")
        self.assertIn("HANDLE REQUIRED", actions[-1].screen.to_text())
        self.assertEqual(self.session.active_field.name, "handle")
        self.assertEqual(self.store.recent(1), [])

    def test_empty_message(self):
        self.session.feed(b"ALICE")
        self.session.feed(SUITE)
        actions = self.session.feed(ENVOI)
        self.assertEqual(self.session.current.number, "140")
        self.assertIn("MESSAGE REQUIRED", actions[-1].screen.to_text())
        self.assertEqual(self.session.active_field.name, "message")
        self.assertEqual(self.store.recent(1), [])

    def test_existing_entries_render(self):
        self.store.add("BOB", "FIRST")
        screen = self.session.render()
        self.assertIn("BOB", screen.to_text())
        self.assertIn("FIRST", screen.to_text())


if __name__ == "__main__":
    unittest.main()
