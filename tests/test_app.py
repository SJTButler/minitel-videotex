import unittest

import pages
import services

from minitel import Registry, page
from minitel.protocol import codec
from minitel.app import MinitelApp
from minitel.terminal.power import PowerSignals
from minitel.terminal.profiles import M1
from minitel.render import Screen


class FakeService:
    def __init__(self, name, events, *, sync=False):
        self.name = name
        self.events = events
        self.sync = sync

    def start(self):
        self.events.append(f"{self.name}:start")
        if not self.sync:
            async def done():
                self.events.append(f"{self.name}:started")
            return done()
        return None

    def stop(self):
        self.events.append(f"{self.name}:stop")
        if not self.sync:
            async def done():
                self.events.append(f"{self.name}:stopped")
            return done()
        return None


class AppTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = pages.build_registry()

    def test_services_propagate_to_sessions(self):
        service = object()
        app = MinitelApp(self.registry, services={"demo": service})
        session = app.new_session()
        self.assertIs(session.services["demo"], service)

    def test_session_services_default_to_empty(self):
        app = MinitelApp(self.registry)
        self.assertEqual(app.new_session().services, {})

    def test_discovered_services_include_weather(self):
        service_registry = services.build_registry()
        self.assertIn("hackernews", service_registry)
        self.assertIn("weather", service_registry)
        self.assertIn("sports", service_registry)

    def test_screensaver_config_propagates_to_sessions(self):
        app = MinitelApp(
            self.registry,
            screensaver=("900",),
            screensaver_after=5.0,
            screensaver_hold=3.0,
        )
        session = app.new_session()
        self.assertEqual([page.number for page in session.screensaver.pages], ["900"])
        self.assertEqual(session.screensaver.after, 5.0)
        self.assertEqual(session.screensaver.hold, 3.0)

    def test_screensaver_is_optional(self):
        app = MinitelApp(self.registry)
        self.assertIsNone(app.new_session().screensaver)

    def test_server_echo_is_the_default(self):
        app = MinitelApp(self.registry)
        self.assertTrue(app.echo)
        session = app.new_session()
        self.assertTrue(session.echo)
        self.assertEqual(session.echo_override(), codec.echo_mode(False))

    def test_local_echo_can_be_selected(self):
        app = MinitelApp(self.registry, echo=False)
        session = app.new_session()
        self.assertFalse(session.echo)
        self.assertEqual(session.echo_override(), codec.echo_mode(True))

    def test_power_signals_propagate_to_sessions(self):
        signals = PowerSignals(off=b"\x01", on=b"\x02")
        app = MinitelApp(self.registry, power=signals)
        self.assertIs(app.new_session().power_signals, signals)

    async def test_async_start_and_stop_order(self):
        events = []
        app = MinitelApp(
            self.registry,
            services={
                "one": FakeService("one", events),
                "two": FakeService("two", events),
            },
        )
        await app._start_services()
        await app._stop_services()
        self.assertEqual(
            events,
            [
                "one:start", "one:started",
                "two:start", "two:started",
                "two:stop", "two:stopped",
                "one:stop", "one:stopped",
            ],
        )

    async def test_handle_closes_the_session_on_disconnect(self):
        closed = []

        class FakeSession:
            def start(self):
                return Screen()

            def echo_override(self):
                return b""

            def next_timeout(self):
                return None

            def close(self):
                closed.append(True)

        class Reader:
            async def read(self, size):
                return b""

        class Writer:
            def get_extra_info(self, name):
                return None

            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        app = MinitelApp(
            self.registry,
            cps=0,
            log=lambda peer, message: None,
        )
        app.new_session = lambda: FakeSession()
        await app.handle(Reader(), Writer())

        self.assertEqual(closed, [True])

    async def test_handle_asserts_the_local_echo_mode_before_the_first_page(self):
        writes = []

        class Reader:
            async def read(self, size):
                return b""

        class Writer:
            def get_extra_info(self, name):
                return None

            def write(self, data):
                writes.append(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        app = MinitelApp(
            self.registry,
            echo=True,
            cps=0,
            log=lambda peer, message: None,
        )
        await app.handle(Reader(), Writer())

        self.assertEqual(writes[0], codec.echo_mode(False))
        self.assertGreater(len(writes[1]), 0)

    async def test_handle_asserts_scroll_mode_for_a_scroll_page(self):
        registry = Registry()

        @page("600", title="SCROLL", scroll=True)
        def scrolling(ctx):
            screen = Screen()
            screen.text(0, 0, "STATUS")
            return screen

        registry.add(scrolling)
        writes = []

        class Reader:
            async def read(self, size):
                return b""

        class Writer:
            def get_extra_info(self, name):
                return None

            def write(self, data):
                writes.append(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        app = MinitelApp(
            registry,
            initial="600",
            cps=0,
            echo=True,
            log=lambda peer, message: None,
        )
        await app.handle(Reader(), Writer())

        self.assertEqual(writes[0], codec.echo_mode(False))
        self.assertIn(codec.SCROLL_ON, writes[1])

    async def test_sync_hooks_are_supported(self):
        events = []
        app = MinitelApp(
            self.registry,
            services={"sync": FakeService("sync", events, sync=True)},
        )
        await app._start_services()
        await app._stop_services()
        self.assertEqual(events, ["sync:start", "sync:stop"])


if __name__ == "__main__":
    unittest.main()
