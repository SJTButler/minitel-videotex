"""TCP transport and paced writes."""

import asyncio
import time

CHUNK = 32


class PacedWriter:
    """Write bytes at a characters-per-second budget for one connection.

    The token bucket is connection-scoped: consecutive small writes share the
    budget instead of each starting with a fresh burst.
    """

    def __init__(self, writer, cps, *, burst=CHUNK, clock=None, sleep=None):
        self.writer = writer
        self.cps = cps
        self.burst = max(1, int(burst))
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._tokens = float(self.burst)
        self._updated = self._clock()

    async def write(self, data):
        if not data:
            return
        if self.cps <= 0:
            self.writer.write(data)
            await self.writer.drain()
            return
        for start in range(0, len(data), CHUNK):
            chunk = data[start:start + CHUNK]
            await self._spend(len(chunk))
            self.writer.write(chunk)
            await self.writer.drain()

    async def _spend(self, amount):
        while amount > 0:
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
            self._tokens = 0.0
            await self._sleep(missing / self.cps)


async def paced_write(writer, data, cps):
    """Compatibility helper for callers that do not own a PacedWriter.

    New connection code should create one PacedWriter and reuse it.
    """
    await PacedWriter(writer, cps).write(data)


async def serve(handler, host, port):
    return await asyncio.start_server(handler, host, port)
