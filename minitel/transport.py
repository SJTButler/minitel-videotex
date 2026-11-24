"""TCP transport and paced writes."""

import asyncio
import time
from collections import deque
from contextlib import suppress
from dataclasses import dataclass

CHUNK = 32


@dataclass
class _Frame:
    data: bytes | None = None
    generation: int = 0
    label: str | None = None
    full: bool = False
    preserve: bool = False
    render: object | None = None


class PacedWriter:
    """Write frames from a per-connection queue at a cps budget.

    The token bucket is connection-scoped: consecutive small writes share the
    budget instead of each starting with a fresh burst. A full paint supersedes
    queued frames and abandons the frame currently on the wire. A lazy frame
    renders the current session state only when the drain reaches it, so rapid
    same-page updates collapse into one diff.
    """

    def __init__(self, writer, cps, *, burst=CHUNK, clock=None, sleep=None,
                 log=None):
        self.writer = writer
        self.cps = cps
        self.burst = max(1, int(burst))
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._log = log
        self._tokens = float(self.burst)
        self._updated = self._clock()
        self._chunk = min(CHUNK, self.burst)
        self._queue = deque()
        self._has_items = asyncio.Event()
        self._idle = asyncio.Event()
        self._idle.set()
        self._task = None
        self._pending = 0
        self._in_flight = False
        self._generation = 0
        self._closing = False
        self._error = None
        self.dead = asyncio.Event()

    async def write(self, data, *, supersedes=False, preserve=False,
                    label=None):
        if not data:
            return
        self._raise_if_dead()
        if self._closing:
            raise RuntimeError("writer is closed")
        if supersedes:
            self._generation += 1
            self._keep_preserved()
        self._enqueue(_Frame(
            data=bytes(data),
            generation=self._generation,
            label=label,
            full=supersedes,
            preserve=preserve,
        ))

    async def write_lazy(self, render):
        self._raise_if_dead()
        if self._closing:
            raise RuntimeError("writer is closed")
        self._drop_lazy()
        self._enqueue(_Frame(
            generation=self._generation,
            render=render,
        ))

    async def flush(self):
        while self._pending:
            self._raise_if_dead()
            await self._idle.wait()
        self._raise_if_dead()

    async def close(self):
        self._closing = True
        self._has_items.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._queue.clear()
        self._pending = 0
        self._in_flight = False
        self._idle.set()

    def raise_if_dead(self):
        self._raise_if_dead()

    def _raise_if_dead(self):
        if self._error is not None:
            raise self._error

    def _enqueue(self, frame):
        self._queue.append(frame)
        self._pending += 1
        self._idle.clear()
        self._has_items.set()
        if self._task is None or self._task.done():
            self._raise_if_dead()
            self._task = asyncio.create_task(self._drain())

    def _keep_preserved(self):
        kept = deque(frame for frame in self._queue if frame.preserve)
        self._pending -= len(self._queue) - len(kept)
        self._queue = kept

    def _drop_lazy(self):
        kept = deque(
            frame for frame in self._queue if frame.render is None
        )
        self._pending -= len(self._queue) - len(kept)
        self._queue = kept

    async def _drain(self):
        try:
            while True:
                frame = await self._next_item()
                if frame is None:
                    return
                self._in_flight = True
                try:
                    await self._write(frame)
                finally:
                    self._in_flight = False
                self._finish_frame()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._error = exc
            self._pending = 0
            self.dead.set()
        finally:
            self._idle.set()

    async def _next_item(self):
        while not self._queue:
            if self._closing:
                return None
            self._has_items.clear()
            await self._has_items.wait()
            if self._closing and not self._queue:
                return None
        return self._queue.popleft()

    def _finish_frame(self):
        self._pending = max(0, self._pending - 1)
        if self._pending == 0:
            self._idle.set()

    async def _write(self, frame):
        lazy = frame.render is not None
        if lazy:
            if self._stale(frame):
                return
            data, full = frame.render()
            if not data:
                return
            frame.data = bytes(data)
            if full:
                self._generation += 1
                frame.generation = self._generation
                frame.full = True
                frame.preserve = False
                self._keep_preserved()
        await self._write_frame(frame)

    async def _write_frame(self, frame):
        data = frame.data or b""
        if self.cps <= 0:
            if self._stale(frame):
                return
            self.writer.write(data)
            await self.writer.drain()
        else:
            for start in range(0, len(data), self._chunk):
                if self._stale(frame):
                    return
                chunk = data[start:start + self._chunk]
                await self._spend(len(chunk))
                if self._stale(frame):
                    return
                self.writer.write(chunk)
                await self.writer.drain()
        if frame.label is not None:
            self._log_message(frame.label)

    def _stale(self, frame):
        if frame.preserve:
            return False
        return frame.generation != self._generation

    async def _spend(self, amount):
        while True:
            now = self._clock()
            elapsed = now - self._updated
            if elapsed > 0:
                self._tokens = min(
                    self.burst, self._tokens + elapsed * self.cps
                )
                self._updated = now
            if self._tokens >= amount:
                self._tokens -= amount
                return
            missing = amount - self._tokens
            await self._sleep(missing / self.cps)

    def _log_message(self, message):
        if self._log is None:
            return
        try:
            self._log(message)
        except Exception:
            pass


async def paced_write(writer, data, cps):
    """Compatibility helper for callers that do not own a PacedWriter."""
    pacer = PacedWriter(writer, cps)
    try:
        await pacer.write(data)
        await pacer.flush()
    finally:
        await pacer.close()


async def serve(handler, host, port):
    return await asyncio.start_server(handler, host, port)
