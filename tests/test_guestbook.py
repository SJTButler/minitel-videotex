import unittest

import pages

from minitel import profiles
from minitel.session import Session
from pages.guestbook_store import GuestbookStore

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])


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

    def test_sign_flow(self):
        self.session.feed(b"ALICE" + ENVOI)
        self.assertEqual(self.session.current.number, "141")
        self.assertEqual(self.session.state["guestbook_handle"], "ALICE")

        actions = self.session.feed(b"HELLO" + ENVOI)
        self.assertEqual(self.session.current.number, "140")
        entries = self.store.recent(1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].handle, "ALICE")
        self.assertEqual(entries[0].message, "HELLO")

        screen = actions[-1].screen
        self.assertIn("ALICE", screen.to_text())
        self.assertIn("HELLO", screen.to_text())

        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "100")

    def test_retour_from_message_step(self):
        self.session.feed(b"ALICE" + ENVOI)
        self.assertEqual(self.session.current.number, "141")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "140")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "100")

    def test_empty_handle(self):
        actions = self.session.feed(ENVOI)
        self.assertEqual(self.session.current.number, "140")
        self.assertIn("HANDLE REQUIRED", actions[-1].screen.to_text())

    def test_empty_message(self):
        self.session.feed(b"ALICE" + ENVOI)
        actions = self.session.feed(ENVOI)
        self.assertEqual(self.session.current.number, "141")
        self.assertIn("MESSAGE REQUIRED", actions[-1].screen.to_text())
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "140")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "100")

    def test_existing_entries_render(self):
        self.store.add("BOB", "FIRST")
        screen = self.session.render()
        self.assertIn("BOB", screen.to_text())
        self.assertIn("FIRST", screen.to_text())


if __name__ == "__main__":
    unittest.main()
