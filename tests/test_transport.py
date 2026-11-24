import asyncio
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
        await pacer.flush()
        self.assertEqual(writer.writes, [b"ABCD"])
        self.assertEqual(clock.sleeps, [])

        await pacer.write(b"E")
        await pacer.flush()
        self.assertAlmostEqual(clock.sleeps[0], 0.1)
        self.assertEqual(writer.writes, [b"ABCD", b"E"])
        await pacer.close()

    async def test_partial_budget_only_waits_for_the_missing_tokens(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=10, burst=4, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"ABC")
        await pacer.write(b"DEFG")
        await pacer.flush()

        self.assertAlmostEqual(clock.sleeps[0], 0.3)
        self.assertEqual(writer.writes, [b"ABC", b"DEFG"])
        await pacer.close()

    async def test_page_after_echo_does_not_stall(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=100, burst=32, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"ABCDE")
        await pacer.write(b"X" * 32)
        await pacer.flush()

        self.assertAlmostEqual(clock.sleeps[0], 0.05)
        self.assertEqual(writer.writes[-1], b"X" * 32)
        await pacer.close()

    async def test_idle_time_refills_but_is_capped(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=10, burst=4, clock=clock, sleep=clock.sleep
        )

        clock.advance(100.0)
        await pacer.write(b"ABCD")
        await pacer.flush()
        self.assertEqual(clock.sleeps, [])

        await pacer.write(b"EFGH")
        await pacer.flush()
        self.assertAlmostEqual(clock.sleeps[0], 0.4)
        await pacer.close()

    async def test_large_write_is_chunked_and_paced(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=64, burst=32, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"X" * 64)
        await pacer.flush()
        self.assertEqual(writer.writes, [b"X" * 32, b"X" * 32])
        self.assertAlmostEqual(clock.sleeps[0], 0.5)
        await pacer.close()

    async def test_zero_cps_is_immediate(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=0, burst=4, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"X" * 100)
        await pacer.flush()
        self.assertEqual(writer.writes, [b"X" * 100])
        self.assertEqual(clock.sleeps, [])
        await pacer.close()

    async def test_empty_write_is_a_noop(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=10, burst=4, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"")
        await pacer.flush()
        self.assertEqual(writer.writes, [])
        self.assertEqual(clock.sleeps, [])
        await pacer.close()


class PacedWriterQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_supersedes_keeps_control_frames_and_drops_echo(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=0, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"CTRL", preserve=True)
        await pacer.write(b"F1", supersedes=True)
        await pacer.write(b"ECHO")
        await pacer.write(b"F2", supersedes=True)
        await pacer.flush()

        self.assertEqual(writer.writes, [b"CTRL", b"F2"])
        await pacer.close()

    async def test_supersedes_abandons_a_full_paint_between_chunks(self):
        clock = FakeClock()
        writer = GatedWriter()
        pacer = PacedWriter(
            writer, cps=64, burst=32, clock=clock, sleep=clock.sleep
        )

        await pacer.write(b"A" * 64, supersedes=True)
        await asyncio.wait_for(writer.started.wait(), timeout=1)
        await pacer.write(b"B" * 32, supersedes=True)
        writer.gate.set()
        await pacer.flush()

        self.assertEqual(writer.writes, [b"A" * 32, b"B" * 32])
        await pacer.close()

    async def test_drain_error_surfaces_to_flush(self):
        class FailWriter:
            def write(self, data):
                pass

            async def drain(self):
                raise BrokenPipeError("gone")

        pacer = PacedWriter(FailWriter(), cps=0)
        await pacer.write(b"X")

        with self.assertRaises(BrokenPipeError):
            await pacer.flush()

        await pacer.close()

    async def test_lazy_markers_collapse_before_rendering(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=0, clock=clock, sleep=clock.sleep
        )
        calls = []

        def render():
            calls.append(True)
            return b"LAZY", False

        await pacer.write_lazy(render)
        await pacer.write_lazy(render)
        await pacer.write_lazy(render)
        await pacer.flush()

        self.assertEqual(calls, [True])
        self.assertEqual(writer.writes, [b"LAZY"])
        await pacer.close()

    async def test_a_full_paint_drops_a_queued_lazy_marker(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=0, clock=clock, sleep=clock.sleep
        )
        calls = []

        def render():
            calls.append(True)
            return b"LAZY", False

        await pacer.write_lazy(render)
        await pacer.write(b"FULL", supersedes=True)
        await pacer.flush()

        self.assertEqual(calls, [])
        self.assertEqual(writer.writes, [b"FULL"])
        await pacer.close()

    async def test_ordered_echo_interleaves_with_a_lazy_marker(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=0, clock=clock, sleep=clock.sleep
        )

        def render():
            return b"LAZY", False

        await pacer.write(b"E1")
        await pacer.write_lazy(render)
        await pacer.write(b"E2")
        await pacer.flush()

        self.assertEqual(writer.writes, [b"E1", b"LAZY", b"E2"])
        await pacer.close()

    async def test_a_new_lazy_marker_waits_for_the_in_flight_diff(self):
        clock = FakeClock()
        writer = GatedWriter()
        pacer = PacedWriter(
            writer, cps=64, burst=32, clock=clock, sleep=clock.sleep
        )
        calls = []

        def first():
            calls.append("first")
            return b"A" * 64, False

        def second():
            calls.append("second")
            return b"B" * 32, False

        await pacer.write_lazy(first)
        await asyncio.wait_for(writer.started.wait(), timeout=1)
        await pacer.write_lazy(second)
        writer.gate.set()
        await pacer.flush()

        self.assertEqual(calls, ["first", "second"])
        self.assertEqual(
            writer.writes, [b"A" * 32, b"A" * 32, b"B" * 32]
        )
        await pacer.close()

    async def test_close_rejects_later_writes(self):
        clock = FakeClock()
        writer = FakeWriter()
        pacer = PacedWriter(
            writer, cps=0, clock=clock, sleep=clock.sleep
        )
        await pacer.write(b"X")
        await pacer.close()

        with self.assertRaises(RuntimeError):
            await pacer.write(b"Y")


class GatedWriter:
    def __init__(self):
        self.writes = []
        self.gate = asyncio.Event()
        self.started = asyncio.Event()

    def write(self, data):
        self.writes.append(bytes(data))

    async def drain(self):
        self.started.set()
        await self.gate.wait()


class AppPacingTests(unittest.IsolatedAsyncioTestCase):
    async def test_consecutive_raw_actions_are_coalesced(self):
        writes = []
        ready = asyncio.Event()

        class Reader:
            def __init__(self):
                self.reads = 0

            async def read(self, size):
                self.reads += 1
                if self.reads == 1:
                    return b"x"
                await ready.wait()
                return b""

        class Writer:
            def get_extra_info(self, name):
                return None

            def write(self, data):
                writes.append(bytes(data))
                if b"ABC" in data:
                    ready.set()

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
