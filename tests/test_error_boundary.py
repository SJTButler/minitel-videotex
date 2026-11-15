import unittest

from minitel import Header, Registry, Screen, Session, page
from minitel.terminal.profiles import M1

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SOMMAIRE = bytes([0x13, 0x46])


class BrokenHeader(Header):
    def render(self, ctx):
        raise RuntimeError("header failed")


def make_registry(*pages):
    registry = Registry()
    for page_object in pages:
        registry.add(page_object)
    return registry


def make_session(registry, *, initial="100", log=None):
    session = Session(
        registry,
        M1,
        initial=initial,
        fallback=registry.get("100"),
        log=log,
    )
    session.start()
    return session


@page("100", title="HOME")
def home(ctx):
    screen = Screen()
    screen.text(0, 0, "HOME")
    return screen


@page("200", title="BROKEN")
def broken_render(ctx):
    raise RuntimeError("render failed")


def _broken_tick(ctx):
    raise RuntimeError("tick failed")


@page("201", title="BROKEN TICK", tick_interval=1.0, on_tick=_broken_tick)
def broken_tick(ctx):
    screen = Screen()
    screen.text(0, 0, "TICK")
    return screen


def _bad_tick_fields(ctx):
    ctx.set_input(2, 0, 5)
    return None


@page(
    "202", title="BAD TICK FIELDS", tick_interval=1.0,
    on_tick=_bad_tick_fields,
)
def bad_tick_fields(ctx):
    screen = Screen()
    ctx.set_input(1, 0, 5)
    return screen


def _broken_submit(ctx, line):
    raise RuntimeError("submit failed")


@page("203", title="BROKEN SUBMIT", on_submit=_broken_submit)
def broken_submit(ctx):
    screen = Screen()
    screen.text(0, 0, "SUBMIT")
    return screen


@page("204", title="BROKEN HEADER", header=BrokenHeader())
def broken_header(ctx):
    screen = Screen()
    screen.text(0, 0, "BODY")
    return screen


def _focus_tick(ctx):
    ctx.focus("name")
    return None


@page(
    "205", title="BAD TICK FOCUS", form=True, tick_interval=1.0,
    on_tick=_focus_tick,
)
def bad_tick_focus(ctx):
    screen = Screen()
    ctx.add_field("name", 1, 0, 5)
    return screen


def _same_tick(ctx):
    ctx.set_input(1, 0, 5)
    return None


@page(
    "206", title="SAME TICK FIELD", tick_interval=1.0,
    on_tick=_same_tick,
)
def same_tick_field(ctx):
    screen = Screen()
    ctx.set_input(1, 0, 5)
    return screen


class ErrorBoundaryTests(unittest.TestCase):
    def test_render_failure_keeps_the_session_alive(self):
        logs = []
        registry = make_registry(home, broken_render)
        session = make_session(registry, log=logs.append)

        action = session.navigate("200")

        self.assertIsNotNone(action.screen)
        self.assertIn("PAGE ERROR", action.screen.to_text())
        self.assertEqual(session.current.number, "200")
        self.assertEqual(session.page_error, "render")
        self.assertIsNone(session.next_timeout())
        self.assertTrue(any("page error (render)" in line for line in logs))

        session.feed(SOMMAIRE)
        self.assertEqual(session.current.number, "100")
        self.assertIsNone(session.page_error)
        self.assertIn("HOME", session.screen.to_text())

    def test_retour_from_the_error_screen_uses_history(self):
        registry = make_registry(home, broken_render)
        session = make_session(registry)
        session.navigate("200")

        session.feed(RETOUR)

        self.assertEqual(session.current.number, "100")
        self.assertIsNone(session.page_error)

    def test_tick_failure_disables_that_page_tick(self):
        logs = []
        registry = make_registry(home, broken_tick)
        session = make_session(registry, log=logs.append)
        session.navigate("201")

        action = session.tick()

        self.assertIn("PAGE ERROR", action.screen.to_text())
        self.assertEqual(session.page_error, "tick")
        self.assertIn("201", session._ticks_disabled)
        self.assertIsNone(session._page_tick_interval(registry.get("201")))
        self.assertTrue(any("page error (tick)" in line for line in logs))

    def test_tick_cannot_change_a_field(self):
        registry = make_registry(home, bad_tick_fields)
        session = make_session(registry)
        session.navigate("202")

        action = session.tick()

        self.assertIn("PAGE ERROR", action.screen.to_text())
        self.assertEqual(session.page_error, "tick")
        self.assertIn("202", session._ticks_disabled)

    def test_submit_failure_enters_the_error_screen(self):
        logs = []
        registry = make_registry(home, broken_submit)
        session = make_session(registry, log=logs.append)
        session.navigate("203")

        action = session.feed(ENVOI)[0]

        self.assertIn("PAGE ERROR", action.screen.to_text())
        self.assertEqual(session.page_error, "submit")
        self.assertTrue(any("page error (submit)" in line for line in logs))

    def test_header_failure_enters_the_error_screen(self):
        logs = []
        registry = make_registry(home, broken_header)
        session = make_session(registry, log=logs.append)

        action = session.navigate("204")

        self.assertIn("PAGE ERROR", action.screen.to_text())
        self.assertEqual(session.page_error, "header")
        self.assertTrue(any("page error (header)" in line for line in logs))

    def test_tick_cannot_change_focus(self):
        registry = make_registry(home, bad_tick_focus)
        session = make_session(registry)
        session.navigate("205")

        action = session.tick()

        self.assertIn("PAGE ERROR", action.screen.to_text())
        self.assertEqual(session.page_error, "tick")

    def test_tick_may_redeclare_an_identical_field(self):
        registry = make_registry(home, same_tick_field)
        session = make_session(registry)
        session.navigate("206")

        action = session.tick()

        self.assertEqual(action.screen, None)
        self.assertIsNone(session.page_error)
        self.assertNotIn("206", session._ticks_disabled)

    def test_start_failure_returns_the_error_screen(self):
        registry = make_registry(broken_render)
        session = Session(
            registry,
            M1,
            initial="200",
            fallback=registry.get("200"),
        )

        screen = session.start()

        self.assertIn("PAGE ERROR", screen.to_text())
        self.assertEqual(session.page_error, "render")


if __name__ == "__main__":
    unittest.main()
