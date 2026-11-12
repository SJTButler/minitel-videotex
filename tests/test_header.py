import unittest

from minitel import (
    FunctionPage,
    Header,
    M1,
    MinitelApp,
    Registry,
    Screen,
    Session,
    page,
)
from minitel.session import Screensaver


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FixedHeader(Header):
    def __init__(self, text, *, tick_interval=None, requires=()):
        self.text = text
        self.tick_interval = tick_interval
        self.requires = requires

    def render(self, ctx):
        screen = Screen()
        screen.fill(0, 0, 40, " ", inverse=True)
        screen.text(0, 0, self.text, inverse=True)
        return screen


class PassThroughHeader(Header):
    def render(self, ctx):
        return None


class WallClockHeader(Header):
    tick_interval = 1.0

    def render(self, ctx):
        screen = Screen()
        screen.fill(0, 0, 40, " ", inverse=True)
        screen.text(0, 0, f"H{int(ctx.now)}", inverse=True)
        return screen


class ServiceHeader(Header):
    requires = ("svc",)

    def render(self, ctx):
        screen = Screen()
        screen.text(0, 0, ctx.service("svc").value)
        return screen


class BadIntervalHeader(Header):
    tick_interval = 0

    def render(self, ctx):
        return Screen()


def body_screen(text="BODY"):
    screen = Screen()
    screen.fill(0, 0, 40, " ", inverse=True)
    screen.text(0, 0, "BODYSTATUS", inverse=True)
    screen.text(1, 0, text)
    return screen


@page("700")
def normal(ctx):
    screen = body_screen()
    ctx.set_input(5, 0, 4)
    return screen


@page("701", header=False)
def opt_out(ctx):
    return body_screen("NOHEADER")


@page("702", header=FixedHeader("PAGEHEADER"))
def page_header(ctx):
    return body_screen("PAGEHEADERBODY")


@page("703", extensions=True, header=FixedHeader("EXTHEADER"))
def extension_base(ctx):
    return body_screen("EXTBODY")


def _tick_render(ctx):
    return body_screen("TICKBODY")


def _tick_on_tick(ctx):
    ctx.state["ticks"] = ctx.state.get("ticks", 0) + 1
    return body_screen(f"T{ctx.state['ticks']}")


ticking = FunctionPage(
    "704", _tick_render, tick_interval=1.0, on_tick=_tick_on_tick
)
slow_ticking = FunctionPage(
    "705", _tick_render, tick_interval=5.0, on_tick=_tick_on_tick
)


def _full_tick(ctx):
    screen = body_screen("FULL")
    screen.force_full = True
    return screen


full_ticking = FunctionPage(
    "706", _tick_render, tick_interval=1.0, on_tick=_full_tick
)


@page("720", screensaver="test")
def saver(ctx):
    screen = Screen()
    screen.text(0, 0, "SAVER")
    return screen


def build_registry():
    registry = Registry()
    for value in (
        normal, opt_out, page_header, extension_base, ticking,
        slow_ticking, full_ticking, saver,
    ):
        registry.add(value)
    return registry


def make_session(registry, initial, *, header=None, clock=None,
                 wall_clock=None, screensaver=None, services=None):
    clock = clock or FakeClock()
    wall_clock = wall_clock or FakeClock()
    session = Session(
        registry,
        M1,
        initial=initial,
        fallback=registry.get("700"),
        header=header,
        clock=clock,
        wall_clock=wall_clock,
        screensaver=screensaver,
        services=services,
    )
    session.start()
    return session, clock, wall_clock


def row0(screen):
    return "".join(cell.ch for cell in screen.rows[0]).rstrip()


class HeaderCompositionTests(unittest.TestCase):
    def test_no_app_header_leaves_the_body_row_untouched(self):
        session, _, _ = make_session(build_registry(), "700")
        self.assertEqual(row0(session.screen), "BODYSTATUS")
        self.assertEqual(session.screen.to_text().splitlines()[1].strip(), "BODY")

    def test_app_header_replaces_row_zero_and_preserves_the_cursor(self):
        session, _, _ = make_session(
            build_registry(), "700", header=FixedHeader("APPHEADER")
        )
        self.assertEqual(row0(session.screen), "APPHEADER")
        self.assertEqual(session.screen.to_text().splitlines()[1].strip(), "BODY")
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col), (5, 0)
        )

    def test_header_returning_none_passes_through(self):
        session, _, _ = make_session(
            build_registry(), "700", header=PassThroughHeader()
        )
        self.assertEqual(row0(session.screen), "BODYSTATUS")

    def test_page_header_overrides_the_app_header(self):
        session, _, _ = make_session(
            build_registry(), "702", header=FixedHeader("APPHEADER")
        )
        self.assertEqual(row0(session.screen), "PAGEHEADER")

    def test_page_header_false_uses_the_body_row(self):
        session, _, _ = make_session(
            build_registry(), "701", header=FixedHeader("APPHEADER")
        )
        self.assertEqual(row0(session.screen), "BODYSTATUS")
        self.assertEqual(
            session.screen.to_text().splitlines()[1].strip(), "NOHEADER"
        )

    def test_navigation_restores_the_app_header(self):
        session, _, _ = make_session(
            build_registry(), "701", header=FixedHeader("APPHEADER")
        )
        self.assertEqual(row0(session.screen), "BODYSTATUS")
        session.navigate("700")
        self.assertEqual(row0(session.screen), "APPHEADER")

    def test_extension_inherits_the_base_header(self):
        registry = build_registry()
        session, _, _ = make_session(registry, "703#ABC")
        self.assertEqual(row0(session.screen), "EXTHEADER")
        self.assertIs(session.current.header, registry.get("703").header)


class HeaderTickTests(unittest.TestCase):
    def test_body_tick_recomposes_the_header(self):
        session, clock, _ = make_session(
            build_registry(), "704", header=FixedHeader("APPHEADER")
        )
        self.assertEqual(session.state.get("ticks", 0), 0)
        clock.advance(1.0)
        action = session.on_timeout()
        self.assertTrue(action.raw)
        self.assertEqual(session.state["ticks"], 1)
        self.assertEqual(row0(session.screen), "APPHEADER")
        self.assertEqual(
            session.screen.to_text().splitlines()[1].strip(), "T1"
        )

    def test_header_tick_updates_row_zero_without_a_body_tick(self):
        session, clock, wall = make_session(
            build_registry(), "700", header=WallClockHeader()
        )
        self.assertEqual(row0(session.screen), "H0")
        self.assertEqual(session.next_timeout(), 1.0)
        clock.advance(1.0)
        wall.advance(1.0)
        action = session.on_timeout()
        self.assertTrue(action.raw)
        self.assertEqual(row0(session.screen), "H1")
        self.assertEqual(
            session.screen.to_text().splitlines()[1].strip(), "BODY"
        )

    def test_header_tick_does_not_advance_a_slower_body_tick(self):
        session, clock, wall = make_session(
            build_registry(), "705", header=WallClockHeader()
        )
        clock.advance(1.0)
        wall.advance(1.0)
        session.on_timeout()
        self.assertEqual(session.state.get("ticks", 0), 0)
        clock.advance(4.0)
        wall.advance(4.0)
        session.on_timeout()
        self.assertEqual(session.state["ticks"], 1)

    def test_header_ticks_do_not_reset_idle(self):
        registry = build_registry()
        screensaver = Screensaver.from_spec(
            registry, (saver,), after=10.0, hold=5.0
        )
        session, clock, wall = make_session(
            registry,
            "700",
            header=WallClockHeader(),
            screensaver=screensaver,
        )
        clock.advance(9.0)
        wall.advance(9.0)
        session.on_timeout()
        self.assertFalse(session.screensaver_active)
        clock.advance(1.0)
        wall.advance(1.0)
        session.on_timeout()
        self.assertTrue(session.screensaver_active)

    def test_force_full_body_tick_keeps_the_header(self):
        session, clock, _ = make_session(
            build_registry(), "706", header=FixedHeader("APPHEADER")
        )
        clock.advance(1.0)
        action = session.on_timeout()
        self.assertIsNotNone(action.screen)
        self.assertEqual(row0(action.screen), "APPHEADER")
        self.assertEqual(
            action.screen.to_text().splitlines()[1].strip(), "FULL"
        )


class HeaderValidationTests(unittest.TestCase):
    def test_invalid_header_declarations_are_rejected(self):
        with self.assertRaises(TypeError):
            FunctionPage("900", lambda ctx: Screen(), header=True)
        with self.assertRaises(TypeError):
            FunctionPage("900", lambda ctx: Screen(), header=object())
        with self.assertRaises(TypeError):
            FunctionPage(
                "900", lambda ctx: Screen(), header=BadIntervalHeader()
            )

    def test_page_header_requirements_are_reported(self):
        registry = Registry()
        page_object = FunctionPage(
            "901", lambda ctx: Screen(), header=ServiceHeader()
        )
        registry.add(page_object)
        self.assertEqual(
            registry.missing_requirements({}), {"svc": ("901",)}
        )

    def test_header_can_read_its_declared_service(self):
        session, _, _ = make_session(
            build_registry(),
            "700",
            header=ServiceHeader(),
            services={"svc": type("Service", (), {"value": "SERVICE"})()},
        )
        self.assertEqual(row0(session.screen), "SERVICE")

    def test_app_passes_the_header_and_requires_to_sessions(self):
        registry = build_registry()
        service = type("Service", (), {"value": "SERVICE"})()
        app = MinitelApp(
            registry,
            initial="700",
            fallback=registry.get("700"),
            header=ServiceHeader(),
            services={"svc": service},
        )
        session = app.new_session()
        self.assertIs(session.header, app.header)
        self.assertEqual(app.header_requires, ("svc",))
        session.start()
        self.assertEqual(row0(session.screen), "SERVICE")


if __name__ == "__main__":
    unittest.main()
