import asyncio
import unittest

from minitel import Registry, Screen, page
from minitel.app import MinitelApp, _Wake


class FakeWakeService:
    def __init__(self):
        self.callback = None
        self.value = "VALUE-A"

    def on_change(self, callback):
        self.callback = callback

    def changed(self, value="VALUE-B"):
        self.value = value
        if self.callback is not None:
            self.callback()


@page("600", title="WAKE", requires=("demo",))
def wake_page(ctx):
    screen = Screen()
    screen.text(1, 0, ctx.service("demo").value)
    return screen


@page("601", title="PLAIN")
def plain_page(ctx):
    screen = Screen()
    screen.text(1, 0, "PLAIN")
    return screen


@page("602", title="BROKEN", requires=("demo",))
def broken_page(ctx):
    raise RuntimeError("boom")


@page("603", title="AUTO", requires=("demo",))
def auto_page(ctx):
    screen = Screen()
    screen.text(1, 0, "AUTO")
    ctx.set_input(20, 6, 10, cursor="auto")
    return screen


def make_registry():
    registry = Registry()
    for item in (wake_page, plain_page, broken_page, auto_page):
        registry.add(item)
    return registry


class QueueReader:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def read(self, size):
        return await self.queue.get()


class EventWriter:
    def __init__(self):
        self.writes = []
        self.saw_initial = asyncio.Event()
        self.saw_changed = asyncio.Event()

    def get_extra_info(self, name):
        return None

    def write(self, data):
        self.writes.append(data)
        if b"VALUE-A" in data:
            self.saw_initial.set()
        if b"VALUE-B" in data:
            self.saw_changed.set()

    async def drain(self):
        pass

    def close(self):
        pass

    async def wait_closed(self):
        pass


class WakeDecisionTests(unittest.IsolatedAsyncioTestCase):
    async def make_app(self, initial):
        service = FakeWakeService()
        app = MinitelApp(
            make_registry(),
            initial=initial,
            cps=0,
            services={"demo": service},
            log=lambda peer, message: None,
        )
        await app._start_services()
        session = app.new_session()
        session.start()
        return app, service, session

    async def test_installs_the_service_callback(self):
        app, service, _session = await self.make_app("600")

        self.assertTrue(app._wake_enabled)
        self.assertIsNotNone(service.callback)

    async def test_a_non_requiring_page_is_not_repainted(self):
        app, _service, session = await self.make_app("601")

        self.assertIsNone(app._wake_action(session, {"demo"}))

    async def test_paused_sessions_are_not_repainted(self):
        app, _service, session = await self.make_app("600")
        session.feed(b"\x00")

        self.assertTrue(session.paused)
        self.assertIsNone(app._wake_action(session, {"demo"}))

    async def test_page_error_suppresses_the_repaint(self):
        app, _service, session = await self.make_app("602")

        self.assertEqual(session.page_error, "render")
        self.assertIsNone(app._wake_action(session, {"demo"}))

    async def test_screensaver_suppresses_the_repaint(self):
        app, _service, session = await self.make_app("600")
        session.screensaver_active = True

        self.assertIsNone(app._wake_action(session, {"demo"}))

    async def test_auto_field_with_text_suppresses_the_repaint(self):
        app, _service, session = await self.make_app("603")
        session.feed(b"X")

        self.assertEqual(session.values["input"], "X")
        self.assertIsNone(app._wake_action(session, {"demo"}))

    async def test_auto_field_without_text_allows_the_repaint(self):
        app, _service, session = await self.make_app("603")

        self.assertIsNotNone(app._wake_action(session, {"demo"}))

    async def test_a_wake_does_not_reset_the_idle_deadline(self):
        app, _service, session = await self.make_app("600")
        before = session.last_activity

        action = app._wake_action(session, {"demo"})

        self.assertIsNotNone(action)
        self.assertEqual(session.last_activity, before)


class WakeLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_service_change_repaints_the_requiring_page(self):
        service = FakeWakeService()
        app = MinitelApp(
            make_registry(),
            initial="600",
            cps=0,
            services={"demo": service},
            log=lambda peer, message: None,
        )
        await app._start_services()
        reader = QueueReader()
        writer = EventWriter()
        task = asyncio.create_task(app.handle(reader, writer))
        try:
            await asyncio.wait_for(writer.saw_initial.wait(), timeout=1)
            service.changed()
            await asyncio.wait_for(writer.saw_changed.wait(), timeout=1)
        finally:
            await reader.queue.put(b"")
            await asyncio.wait_for(task, timeout=1)

    async def test_two_wakes_coalesce_into_one_repaint(self):
        service = FakeWakeService()
        app = MinitelApp(
            make_registry(),
            initial="600",
            cps=0,
            services={"demo": service},
            log=lambda peer, message: None,
        )
        await app._start_services()
        reader = QueueReader()
        writer = EventWriter()
        task = asyncio.create_task(app.handle(reader, writer))
        try:
            await asyncio.wait_for(writer.saw_initial.wait(), timeout=1)
            service.changed()
            service.changed()
            await asyncio.wait_for(writer.saw_changed.wait(), timeout=1)
            for _ in range(3):
                await asyncio.sleep(0)
            repaints = sum(
                1 for data in writer.writes if b"VALUE-B" in data
            )
            self.assertEqual(repaints, 1)
        finally:
            await reader.queue.put(b"")
            await asyncio.wait_for(task, timeout=1)

    async def test_change_fans_out_to_every_connection(self):
        app = MinitelApp(make_registry(), cps=0)
        first = _Wake()
        second = _Wake()
        app._wakes = {first, second}

        app._dispatch_change("demo")

        self.assertEqual(first.keys, {"demo"})
        self.assertEqual(second.keys, {"demo"})
        self.assertTrue(first.event.is_set())
        self.assertTrue(second.event.is_set())


if __name__ == "__main__":
    unittest.main()
