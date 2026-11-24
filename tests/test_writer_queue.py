import asyncio
import importlib.util
import unittest
from pathlib import Path

import pages

from minitel.app import MinitelApp
from minitel.pagemodel import page
from minitel.render import Screen, render_screen
from minitel.session import Action, Session
from minitel.terminal.profiles import M1

SUITE = bytes([0x13, 0x48])


def load_virtual_minitel():
    path = Path(__file__).resolve().parents[1] / "tools" / "virtual_minitel.py"
    spec = importlib.util.spec_from_file_location("virtual_minitel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VM = load_virtual_minitel()


class FakeSession:
    def __init__(self):
        self.feed_called = asyncio.Event()
        self.closed = asyncio.Event()
        self.fed = []

    def start(self):
        screen = Screen()
        for row in range(1, 20):
            screen.text(row, 0, "X" * 40)
        return screen

    def echo_override(self):
        return b""

    def next_timeout(self):
        return None

    def feed(self, data):
        self.fed.append(data)
        self.feed_called.set()
        return [Action(raw=b"ECHO")]

    def close(self):
        self.closed.set()


class PaintWriter:
    def __init__(self):
        self.writes = []
        self.started = asyncio.Event()
        self.gate = asyncio.Event()
        self.echo_written = asyncio.Event()
        self.closed = False

    def get_extra_info(self, name):
        return None

    def write(self, data):
        self.writes.append(bytes(data))
        if b"ECHO" in data:
            self.echo_written.set()

    async def drain(self):
        if not self.started.is_set():
            self.started.set()
            await self.gate.wait()

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


class InputDuringPaintReader:
    def __init__(self, writer):
        self.writer = writer
        self.reads = 0

    async def read(self, size):
        self.reads += 1
        if self.reads == 1:
            await self.writer.started.wait()
            return b"x"
        await self.writer.echo_written.wait()
        return b""


class BrokenWriter:
    def __init__(self):
        self.closed = False

    def get_extra_info(self, name):
        return None

    def write(self, data):
        pass

    async def drain(self):
        raise BrokenPipeError("gone")

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


class NeverReader:
    async def read(self, size):
        await asyncio.Event().wait()


@page("650", title="PAGES")
def paged(ctx):
    ctx.set_pager(10, 1)
    screen = Screen()
    screen.text(1, 0, f"PAGE {ctx.pager.page_index}")
    return screen


class PagerWriter:
    def __init__(self):
        self.writes = []
        self.settled = asyncio.Event()

    def get_extra_info(self, name):
        return None

    def write(self, data):
        self.writes.append(bytes(data))
        if len(self.writes) >= 3:
            self.settled.set()

    async def drain(self):
        pass

    def close(self):
        pass

    async def wait_closed(self):
        pass


class PagerReader:
    def __init__(self, writer):
        self.writer = writer
        self.reads = 0

    async def read(self, size):
        self.reads += 1
        if self.reads == 1:
            return SUITE * 5
        await self.writer.settled.wait()
        return b""


class LazyRepaintTests(unittest.IsolatedAsyncioTestCase):
    async def test_rapid_suite_moves_collapse_into_one_diff(self):
        registry = pages.build_registry()
        registry.add(paged)
        writer = PagerWriter()
        app = MinitelApp(
            registry,
            initial="650",
            cps=0,
            log=lambda peer, message: None,
        )
        await asyncio.wait_for(
            app.handle(PagerReader(writer), writer), timeout=1
        )

        self.assertEqual(len(writer.writes), 3)
        decoder = VM.Decoder()
        for data in writer.writes:
            decoder.feed(data)
        self.assertIn("PAGE 5", decoder.screen.text())

    async def test_lazy_diff_chain_reconstructs_the_final_screen(self):
        registry = pages.build_registry()
        registry.add(paged)
        session = Session(registry, M1, initial="650")
        decoder = VM.Decoder()
        decoder.feed(render_screen(session.start()))
        session.defer_repaints = True

        for _ in range(5):
            session.feed(SUITE)
            action = session.render_lazy()
            if action.screen is not None:
                decoder.feed(render_screen(action.screen))
            else:
                decoder.feed(action.raw)

        self.assertEqual(decoder.screen.text(), session.screen.to_text())
        self.assertIn("PAGE 5", decoder.screen.text())

    async def test_deferred_refresh_returns_a_lazy_action(self):
        registry = pages.build_registry()
        registry.add(paged)
        session = Session(registry, M1, initial="650")
        session.start()
        session.defer_repaints = True

        action = session.refresh()

        self.assertTrue(action.lazy)
        self.assertIsNone(action.screen)
        self.assertEqual(action.raw, b"")


class WriterQueueAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_input_is_parsed_and_echoed_while_a_paint_is_in_flight(self):
        session = FakeSession()
        writer = PaintWriter()
        app = MinitelApp(
            pages.build_registry(),
            cps=0,
            log=lambda peer, message: None,
        )
        app.new_session = lambda: session
        task = asyncio.create_task(
            app.handle(InputDuringPaintReader(writer), writer)
        )

        await asyncio.wait_for(session.feed_called.wait(), timeout=1)
        self.assertFalse(writer.echo_written.is_set())

        writer.gate.set()
        await asyncio.wait_for(task, timeout=1)

        joined = b"".join(writer.writes)
        self.assertIn(b"ECHO", joined)
        self.assertTrue(writer.closed)

    async def test_broken_pipe_mid_drain_closes_the_session(self):
        session = FakeSession()
        writer = BrokenWriter()
        app = MinitelApp(
            pages.build_registry(),
            cps=0,
            log=lambda peer, message: None,
        )
        app.new_session = lambda: session

        await asyncio.wait_for(
            app.handle(NeverReader(), writer), timeout=1
        )

        self.assertTrue(session.closed.is_set())
        self.assertTrue(writer.closed)


if __name__ == "__main__":
    unittest.main()
