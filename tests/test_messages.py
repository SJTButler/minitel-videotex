import unittest
from types import SimpleNamespace

from pages.common.messages import MessageLatch


class FakeContext:
    def __init__(self, number):
        self.state = {}
        self.page = SimpleNamespace(number=number)


class MessageLatchTests(unittest.TestCase):
    def test_set_get_and_clear(self):
        ctx = FakeContext("111")
        latch = MessageLatch(ctx)

        self.assertIsNone(latch.get())
        latch.set("NO STORY 5.", 10)
        self.assertEqual(latch.text(), "NO STORY 5.")
        self.assertEqual(latch.text(10), "NO STORY 5.")
        self.assertIsNone(latch.text(0))

        latch.clear()
        self.assertIsNone(latch.get())

    def test_clear_if_moved(self):
        ctx = FakeContext("111")
        latch = MessageLatch(ctx)

        latch.set("NO STORY 5.", 10)
        latch.clear_if_moved(10)
        self.assertEqual(latch.text(), "NO STORY 5.")

        latch.clear_if_moved(0)
        self.assertIsNone(latch.get())

    def test_offsetless_message_never_clears_on_move(self):
        ctx = FakeContext("140")
        latch = MessageLatch(ctx)

        latch.set("HANDLE REQUIRED")
        latch.clear_if_moved(99)
        self.assertEqual(latch.text(), "HANDLE REQUIRED")

    def test_pages_have_separate_latches(self):
        news = FakeContext("111")
        sports = FakeContext("150")
        MessageLatch(news).set("NO STORY 5.", 0)

        self.assertIsNone(MessageLatch(sports).get())


if __name__ == "__main__":
    unittest.main()
