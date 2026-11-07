"""Application layer: wire a registry, profile, session, and TCP transport."""

import asyncio
import socket
import time

from . import transport
from .data.services import ServiceRegistry
from .render import render_screen
from .session import Session
from .session.screensaver import Screensaver
from .terminal.power import PowerSignals
from .terminal.profiles import M1


class MinitelApp:
    def __init__(self, registry, *, profile=M1, initial="100", fallback=None,
                 guide=None, cps=None, echo=True, log=None, services=None,
                 screensaver=None, screensaver_after=120.0,
                 screensaver_hold=20.0, power=None, clock=None):
        self.registry = registry
        self.profile = profile
        self.initial = initial
        self.fallback = fallback
        self.guide = guide
        self.cps = cps if cps is not None else profile.max_speed / 9
        self.echo = echo
        self.log = log or self._default_log
        self.services = (
            services if isinstance(services, ServiceRegistry)
            else ServiceRegistry(services)
        )
        self.power_signals = (
            power if isinstance(power, PowerSignals) else PowerSignals()
        )
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
            power=self.power_signals,
            clock=self.clock,
        )

    async def send(self, pacer, screen, log, scroll=None):
        data = render_screen(screen, scroll=scroll)
        await pacer.write(data)
        log(f"SENT page ({len(data)} bytes)")

    async def _apply_action(self, pacer, action, log, scroll=None):
        if action.power is not None:
            log("POWER off" if not action.power else "POWER on")
        if action.raw:
            await pacer.write(action.raw)
            if len(action.raw) > 4:
                log(f"RAW {len(action.raw)} bytes")
        if action.page is not None:
            log(f"PAGE {action.page.number}")
        if action.screen is not None:
            await self.send(pacer, action.screen, log, scroll)

    async def _apply_actions(self, pacer, actions, log, scroll=None):
        pending = bytearray()
        for action in actions:
            if (
                action.raw
                and action.screen is None
                and action.page is None
                and action.power is None
            ):
                pending.extend(action.raw)
                continue
            if pending:
                await pacer.write(bytes(pending))
                if len(pending) > 4:
                    log(f"RAW {len(pending)} bytes")
                pending.clear()
            await self._apply_action(pacer, action, log, scroll)
        if pending:
            await pacer.write(bytes(pending))
            if len(pending) > 4:
                log(f"RAW {len(pending)} bytes")

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
        pacer = transport.PacedWriter(writer, self.cps)
        try:
            echo = session.echo_override()
            await pacer.write(echo)
            log(f"ECHO local {'off' if self.echo else 'on'}")
            await self.send(
                pacer,
                session.start(),
                log,
                getattr(session, "scroll_mode", None),
            )
            while True:
                interval = session.next_timeout()
                if interval is None:
                    data = await reader.read(64)
                else:
                    try:
                        data = await asyncio.wait_for(reader.read(64), timeout=interval)
                    except asyncio.TimeoutError:
                        await self._apply_action(
                            pacer,
                            session.on_timeout(),
                            log,
                            getattr(session, "scroll_mode", None),
                        )
                        continue
                if not data:
                    break
                log("RX " + " ".join(f"{b:02X}" for b in data))
                await self._apply_actions(
                    pacer,
                    session.feed(data),
                    log,
                    getattr(session, "scroll_mode", None),
                )
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            self.log(peer, "disconnect")
            try:
                session.close()
            except Exception as exc:
                self.log(peer, f"session close error: {exc!r}")
            writer.close()
            await writer.wait_closed()

    def _report_orphan_services(self):
        required = {
            key
            for page in self.registry.all()
            for key in getattr(page, "requires", ())
        }
        unrequired = sorted(set(self.services) - required)
        if unrequired:
            self.log(
                "startup",
                "WARNING: services not required by any composed page: "
                + ", ".join(unrequired),
            )

    async def _start_services(self):
        self._report_orphan_services()
        await self.services.start()

    async def _stop_services(self):
        await self.services.stop()

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
