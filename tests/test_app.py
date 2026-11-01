import unittest

import pages

from minitel.app import MinitelApp
from minitel.profiles import M1


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

    def test_build_services_includes_weather(self):
        services = pages.build_services()
        self.assertIn("hackernews", services)
        self.assertIn("weather", services)
        self.assertIn("sports", services)

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
                "one:stop", "one:stopped",
                "two:stop", "two:stopped",
            ],
        )

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
