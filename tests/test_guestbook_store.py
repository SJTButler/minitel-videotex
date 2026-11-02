import unittest

from pages.guestbook._support.store import GuestbookStore


class GuestbookStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = GuestbookStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_add_and_recent(self):
        self.store.add("ALICE", "HELLO")
        entries = self.store.recent(1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].handle, "ALICE")
        self.assertEqual(entries[0].message, "HELLO")

    def test_empty_message(self):
        with self.assertRaises(ValueError):
            self.store.add("ALICE", "   ")

    def test_handle_is_truncated(self):
        self.store.add("A" * 20, "HELLO")
        self.assertEqual(self.store.recent(1)[0].handle, "A" * 16)

    def test_message_is_truncated(self):
        self.store.add("ALICE", "B" * 100)
        self.assertEqual(self.store.recent(1)[0].message, "B" * 80)

    def test_recent_limit_and_order(self):
        for i in range(4):
            self.store.add("USER", f"MESSAGE {i}")
        entries = self.store.recent(3)
        self.assertEqual(
            [entry.message for entry in entries],
            ["MESSAGE 3", "MESSAGE 2", "MESSAGE 1"],
        )


if __name__ == "__main__":
    unittest.main()
