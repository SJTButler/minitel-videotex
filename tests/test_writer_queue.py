import asyncio
import unittest

import pages

from minitel.app import MinitelApp
from minitel.render import Screen
from minitel.session import Action


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
