import unittest

from minitel import Carousel, M1, Page, Screen, Screensaver, page
from minitel.pages import Registry
from minitel.session import Session

ENVOI = bytes([0x13, 0x41])


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def build_registry(calls=None):
    calls = calls if calls is not None else {}
    registry = Registry()

    @page("700", tick_interval=1.0, on_tick=lambda ctx: b"")
    def main(ctx):
        s = Screen()
        s.text(0, 0, "MAIN")
        ctx.set_input(1, 0, 5)
        return s

    @page("701", tick_interval=2.0, on_tick=lambda ctx: b"")
    def other(ctx):
        s = Screen()
        s.text(0, 0, "OTHER")
        return s

    def saver_tick(ctx):
        calls["saver"] = calls.get("saver", 0) + 1
        return None

    @page("800", tick_interval=2.0, on_tick=saver_tick)
    def saver_a(ctx):
        s = Screen()
        s.text(0, 0, "SAVER A")
        return s

    @page("801", tick_interval=3.0, on_tick=lambda ctx: b"")
    def saver_b(ctx):
        s = Screen()
        s.text(0, 0, "SAVER B")
        return s

    for value in (main, other, saver_a, saver_b):
        registry.add(value)
    return registry, main, other, saver_a, saver_b


class ScreensaverMechanismTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.registry, self.main, self.other, self.saver_a, self.saver_b = (
            build_registry()
        )
        self.session = Session(
            self.registry,
            M1,
            initial="700",
            fallback=self.main,
            screensaver=Screensaver.from_spec(
                self.registry, (self.saver_a,), after=10.0, hold=5.0
            ),
            clock=self.clock,
        )
        self.session.start()

    def test_next_timeout_uses_the_earliest_deadline(self):
        self.assertEqual(self.session.next_timeout(), 1.0)
        self.clock.advance(9.0)
        self.assertEqual(self.session.next_timeout(), 1.0)
        self.clock.advance(1.0)
        self.assertEqual(self.session.next_timeout(), 0.0)

    def test_activates_after_idle(self):
        self.clock.advance(9.9)
        self.assertFalse(self.session.screensaver_active)
        self.clock.advance(0.1)
        action = self.session.on_timeout()
        self.assertTrue(self.session.screensaver_active)
        self.assertIsNotNone(action.screen)
        self.assertIn("SAVER A", action.screen.to_text())
        self.assertIs(self.session.current, self.main)

    def test_ticks_do_not_reset_idle(self):
        self.clock.advance(5.0)
        self.session.tick()
        self.clock.advance(5.0)
        self.session.on_timeout()
        self.assertTrue(self.session.screensaver_active)

    def test_input_resets_idle(self):
        self.clock.advance(9.0)
        self.session.feed(b"1")
        self.clock.advance(9.0)
        self.assertFalse(self.session.screensaver_active)
        self.clock.advance(1.0)
        self.session.on_timeout()
        self.assertTrue(self.session.screensaver_active)

    def test_navigation_resets_idle(self):
        self.clock.advance(9.0)
        self.session.navigate("701")
        self.clock.advance(9.0)
        self.assertFalse(self.session.screensaver_active)
        self.clock.advance(1.0)
        self.session.on_timeout()
        self.assertTrue(self.session.screensaver_active)
        self.assertEqual(self.session.current.number, "701")

    def test_activation_preserves_page_state(self):
        self.session.navigate("701")
        self.session.navigate("700")
        self.session.feed(b"AB")
        history = list(self.session.history)
        self.clock.advance(10.0)
        self.session.on_timeout()
        self.assertIs(self.session.current, self.main)
        self.assertEqual(self.session.history, history)
        self.assertEqual(self.session.values["input"], "AB")
        self.assertEqual(len(self.session.fields), 1)

    def test_wake_consumes_the_first_chunk_and_restores_the_page(self):
        self.session.feed(b"AB")
        self.session.activate_screensaver()
        actions = self.session.feed(b"XY" + ENVOI)
        self.assertEqual(len(actions), 1)
        self.assertFalse(self.session.screensaver_active)
        self.assertIsNotNone(actions[0].screen)
        self.assertIn("MAIN", actions[0].screen.to_text())
        self.assertEqual(self.session.values["input"], "AB")
        self.session.feed(b"C")
        self.assertEqual(self.session.values["input"], "ABC")

    def test_wake_restores_the_input_cursor(self):
        self.session.feed(b"AB")
        self.session.activate_screensaver()
        self.session.feed(b"Z")
        self.assertEqual(
            (
                self.session.screen.cursor_row,
                self.session.screen.cursor_col,
                self.session.screen.cursor_visible,
            ),
            (1, 2, True),
        )

    def test_rotation_wraps_between_pages_without_a_busy_loop(self):
        self.session.set_screensaver(
            (self.saver_a, self.saver_b), after=10.0, hold=5.0
        )
        self.session.activate_screensaver()
        self.clock.advance(5.0)
        action = self.session.on_timeout()
        self.assertIn("SAVER B", action.screen.to_text())
        self.clock.advance(5.0)
        action = self.session.on_timeout()
        self.assertIn("SAVER A", action.screen.to_text())
        self.assertGreater(self.session.next_timeout(), 0.0)

    def test_long_stall_advances_to_the_current_rotation(self):
        self.session.set_screensaver(
            (self.saver_a, self.saver_b), after=10.0, hold=5.0
        )
        self.session.activate_screensaver()
        self.clock.advance(27.0)
        action = self.session.on_timeout()
        self.assertIn("SAVER B", action.screen.to_text())
        self.assertGreater(self.session.next_timeout(), 0.0)

    def test_wake_discards_a_split_key_sequence(self):
        self.session.navigate("701")
        self.session.activate_screensaver()
        self.session.feed(b"\x13")
        self.session.feed(b"B")
        self.assertEqual(self.session.current.number, "701")

    def test_screensaver_pages_use_the_pager(self):
        self.session.set_screensaver(
            (self.saver_a, self.saver_b), after=10.0, hold=5.0
        )
        self.assertIs(self.session.screensaver.page(0), self.saver_a)
        self.assertIs(self.session.screensaver.page(1), self.saver_b)
        self.assertEqual(self.session.screensaver.hold, 5.0)
        self.assertTrue(self.session.screensaver.wrap)

    def test_carousel_validates_and_disables(self):
        self.assertTrue(Carousel(hold=5.0).active)
        self.assertFalse(Carousel(hold=0).active)
        with self.assertRaises(ValueError):
            Carousel(hold=-1)

    def test_active_screen_saver_tick_runs_instead_of_current_page(self):
        calls = {}
        registry, main, _other, saver_a, _saver_b = build_registry(calls)
        session = Session(
            registry,
            M1,
            initial="700",
            fallback=main,
            screensaver=Screensaver.from_spec(
                registry, (saver_a,), after=10.0, hold=5.0
            ),
            clock=self.clock,
        )
        session.start()
        session.activate_screensaver()
        self.assertEqual(session.next_timeout(), 2.0)
        session.tick()
        self.assertEqual(calls.get("saver"), 1)

    def test_screen_saver_tick_hides_the_cursor(self):
        @page("810", tick_interval=1.0, on_tick=lambda ctx: Screen())
        def saver(ctx):
            return Screen()

        self.registry.add(saver)
        self.session.set_screensaver((saver,), after=10.0, hold=5.0)
        self.session.activate_screensaver()
        self.session.tick()
        self.assertFalse(self.session.screen.cursor_visible)

    def test_auto_can_be_disabled_while_manual_activation_works(self):
        self.session.set_screensaver((self.saver_a,), after=None)
        self.clock.advance(60.0)
        self.assertFalse(self.session.screensaver_active)
        self.session.on_timeout()
        self.assertFalse(self.session.screensaver_active)
        action = self.session.activate_screensaver()
        self.assertIsNotNone(action.screen)
        self.assertTrue(self.session.screensaver_active)

    def test_idle_is_suppressed_on_a_screen_saver_page(self):
        self.session.set_screensaver((self.saver_a,), after=10.0)
        self.session.navigate("800")
        self.clock.advance(60.0)
        self.assertFalse(self.session.screensaver_active)
        self.assertEqual(self.session.next_timeout(), 2.0)

    def test_set_screensaver_does_not_reset_idle(self):
        self.clock.advance(4.0)
        self.session.set_screensaver((self.saver_b,), after=5.0)
        self.clock.advance(1.0)
        self.session.on_timeout()
        self.assertTrue(self.session.screensaver_active)

    def test_manual_request_from_a_page(self):
        def submit(ctx, line):
            ctx.start_screensaver()
            return "710"

        @page("710", on_submit=submit)
        def picker(ctx):
            s = Screen()
            ctx.set_input(1, 0, 5)
            return s

        self.registry.add(picker)
        self.session.navigate("710")
        action = self.session.feed(b"0" + ENVOI)[-1]
        self.assertIsNotNone(action.screen)
        self.assertTrue(self.session.screensaver_active)
        self.assertEqual(self.session.current.number, "710")

    def test_idle_elapsed(self):
        self.clock.advance(3.5)
        self.assertEqual(self.session.idle_elapsed, 3.5)

    def test_unknown_or_empty_spec_raises(self):
        with self.assertRaises(KeyError):
            Screensaver.from_spec(self.registry, ("999",))
        with self.assertRaises(ValueError):
            Screensaver.from_spec(self.registry, ())
        self.assertIsInstance(self.saver_a, Page)


if __name__ == "__main__":
    unittest.main()
