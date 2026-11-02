import unittest

import pages

from minitel.app import MinitelApp
from minitel.render import Screen
from minitel.session import Action
from minitel.transport import PacedWriter


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeWriter:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(bytes(data))

    async def drain(self):
        pass


class PacedWriterTests(unittest.IsolatedAsyncioTestCase):
    async def test_consecutive_small_writes_share_the_budget(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=10, burst=4, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"ABCD")
        self.assertEqual(writer.writes, [b"ABCD"])
        self.assertEqual(clock.sleeps, [])

        await pacer.write(b"E")
        self.assertAlmostEqual(clock.sleeps[0], 0.1)
        self.assertEqual(writer.writes, [b"ABCD", b"E"])

    async def test_partial_budget_only_waits_for_the_missing_tokens(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=10, burst=4, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"ABC")
        await pacer.write(b"DEFG")

        self.assertAlmostEqual(clock.sleeps[0], 0.3)
        self.assertEqual(writer.writes, [b"ABC", b"DEFG"])

    async def test_page_after_echo_does_not_stall(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=100, burst=32, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"ABCDE")
        await pacer.write(b"X" * 32)

        self.assertAlmostEqual(clock.sleeps[0], 0.05)
        self.assertEqual(writer.writes[-1], b"X" * 32)

    async def test_idle_time_refills_but_is_capped(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=10, burst=4, clock=clock, sleep=clock.sleep
        )

        clock.advance(100.0)
        await pacer.write(b"ABCD")
        self.assertEqual(clock.sleeps, [])

        await pacer.write(b"EFGH")
        self.assertAlmostEqual(clock.sleeps[0], 0.4)

    async def test_large_write_is_chunked_and_paced(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=64, burst=32, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"X" * 64)
        self.assertEqual(writer.writes, [b"X" * 32, b"X" * 32])
        self.assertAlmostEqual(clock.sleeps[0], 0.5)

    async def test_zero_cps_is_immediate(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=0, burst=4, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"X" * 100)
        self.assertEqual(writer.writes, [b"X" * 100])
        self.assertEqual(clock.sleeps, [])

    async def test_empty_write_is_a_noop(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=10, burst=4, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"")
        self.assertEqual(writer.writes, [])
        self.assertEqual(clock.sleeps, [])


class AppPacingTests(unittest.IsolatedAsyncioTestCase):
    async def test_consecutive_raw_actions_are_coalesced(self):
        writes = []

        class Reader:
            def __init__(self):
                self.reads = 0

            async def read(self, size):
                self.reads += 1
                return b"x" if self.reads == 1 else b""

        class Writer:
            def get_extra_info(self, name):
                return None

            def write(self, data):
                writes.append(bytes(data))

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        class FakeSession:
            def start(self):
                return Screen()

            def echo_override(self):
                return b""

            def next_timeout(self):
                return None

            def feed(self, data):
                return [
                    Action(raw=b"A"),
                    Action(raw=b"B"),
                    Action(raw=b"C"),
                ]

            def close(self):
                pass

        app = MinitelApp(
            pages.build_registry(),
            cps=0,
            log=lambda peer, message: None,
        )
        app.new_session = lambda: FakeSession()
        await app.handle(Reader(), Writer())

        self.assertEqual(writes[-1], b"ABC")
        self.assertEqual(len(writes), 2)


if __name__ == "__main__":
    unittest.main()
