"""Application layer: wire a registry, profile, session, and TCP transport."""

import asyncio
import inspect
import socket
import time

from . import transport
from .profiles import M1
from .render import render
from .screensaver import Screensaver
from .session import Session


class MinitelApp:
    def __init__(self, registry, *, profile=M1, initial="100", fallback=None,
                 guide=None, cps=None, echo=False, log=None, services=None,
                 screensaver=None, screensaver_after=120.0,
                 screensaver_hold=20.0, clock=None):
        self.registry = registry
        self.profile = profile
        self.initial = initial
        self.fallback = fallback
        self.guide = guide
        self.cps = cps if cps is not None else profile.max_speed / 9
        self.echo = echo
        self.log = log or self._default_log
        self.services = dict(services or {})
        self.clock = clock or time.monotonic
        self.screensaver = (
            Screensaver.from_spec(
                registry,
                screensaver,
                after=screensaver_after,
                hold=screensaver_hold,
            )
            if screensaver is not None
            else None
        )

    def _default_log(self, peer, message):
        stamp = time.strftime("%H:%M:%S")
        print(f"[{stamp}] {peer} {message}", flush=True)

    def new_session(self):
        return Session(
            self.registry,
            self.profile,
            initial=self.initial,
            fallback=self.fallback,
            guide=self.guide,
            echo=self.echo,
            services=self.services,
            screensaver=self.screensaver,
            clock=self.clock,
        )

    async def send(self, writer, screen, log):
        data = render(screen)
        await transport.paced_write(writer, data, self.cps)
        log(f"SENT page ({len(data)} bytes)")

    async def _apply_action(self, writer, action, log):
        if action.raw:
            await transport.paced_write(writer, action.raw, self.cps)
            if len(action.raw) > 4:
                log(f"RAW {len(action.raw)} bytes")
        if action.page is not None:
            log(f"PAGE {action.page.number}")
        if action.screen is not None:
            await self.send(writer, action.screen, log)

    async def handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        sock = writer.get_extra_info("socket")
        if sock is not None:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        def log(message):
            self.log(peer, message)

        self.log(peer, "connect")
        log(f"profile {self.profile.name}, cps={self.cps}, echo={self.echo}")

        session = self.new_session()
        try:
            await self.send(writer, session.start(), log)
            while True:
                interval = session.next_timeout()
                if interval is None:
                    data = await reader.read(64)
                else:
                    try:
                        data = await asyncio.wait_for(reader.read(64), timeout=interval)
                    except asyncio.TimeoutError:
                        await self._apply_action(writer, session.on_timeout(), log)
                        continue
                if not data:
                    break
                log("RX " + " ".join(f"{b:02X}" for b in data))
                for action in session.feed(data):
                    await self._apply_action(writer, action, log)
        except (ConnectionResetError, BrokenPipeError):
            pass

        self.log(peer, "disconnect")
        writer.close()
        await writer.wait_closed()

    async def _start_services(self):
        for service in self.services.values():
            hook = getattr(service, "start", None)
            if hook is None:
                continue
            result = hook()
            if inspect.isawaitable(result):
                await result

    async def _stop_services(self):
        for service in self.services.values():
            hook = getattr(service, "stop", None)
            if hook is None:
                continue
            result = hook()
            if inspect.isawaitable(result):
                await result

    async def serve(self, host="0.0.0.0", port=3615):
        try:
            await self._start_services()
            server = await transport.serve(self.handle, host, port)
            print(f"listening on {host}:{port}", flush=True)
            print(
                f"cps={self.cps} echo={self.echo} profile={self.profile.name}",
                flush=True,
            )
            async with server:
                await server.serve_forever()
        finally:
            await self._stop_services()
