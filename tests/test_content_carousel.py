import unittest

from minitel import Carousel, M1, Screen, Screensaver, page
from minitel.pages import Registry
from minitel.session import Session

ANNULATION = bytes([0x13, 0x45])
SUITE = bytes([0x13, 0x48])


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def build_registry():
    registry = Registry()

    def list_render(ctx, *, total=12, hold=10.0, wrap=True):
        s = Screen()
        s.text(0, 0, "LIST")
        pager = ctx.set_pager(
            total, 4, carousel=Carousel(hold=hold, wrap=wrap)
        )
        s.text(1, 0, pager.label)
        return s

    @page("600")
    def quiet(ctx):
        return list_render(ctx)

    @page("601", tick_interval=2.0, on_tick=list_render)
    def ticking(ctx):
        return list_render(ctx)

    @page("602")
    def field(ctx):
        s = list_render(ctx)
        ctx.set_input(2, 0, 4, cursor="auto")
        return s

    @page("603")
    def single(ctx):
        return list_render(ctx, total=4)

    @page("604")
    def no_wrap(ctx):
        return list_render(ctx, wrap=False)

    @page("605", no_screensaver=True)
    def no_saver(ctx):
        s = Screen()
        s.text(0, 0, "NO SAVER")
        return s

    @page("606")
    def detail(ctx):
        s = Screen()
        s.text(0, 0, "DETAIL")
        return s

    @page("607", no_screensaver=True)
    def no_saver_list(ctx):
        return list_render(ctx, hold=5.0)

    @page("609", tick_interval=2.0, on_tick=lambda ctx: list_render(
        ctx, total=ctx.state.get("total", 12)
    ))
    def changing(ctx):
        return list_render(ctx, total=ctx.state.get("total", 12))

    @page("610")
    def changing_quiet(ctx):
        return list_render(ctx, total=ctx.state.get("total", 12))

    @page("700")
    def saver(ctx):
        s = Screen()
        s.text(0, 0, "SAVER")
        return s

    @page("699")
    def home(ctx):
        s = Screen()
        s.text(0, 0, "HOME")
        return s

    pages = (
        quiet, ticking, field, single, no_wrap, no_saver, detail,
        no_saver_list, changing, changing_quiet, saver, home,
    )
    for value in pages:
        registry.add(value)
    return registry, pages


class ContentCarouselTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.registry, self.pages = build_registry()
        self.session = self.make_session()

    def make_session(self, initial="600", screensaver=None):
        session = Session(
            self.registry,
            M1,
            initial=initial,
            fallback=self.registry.get("699"),
            screensaver=screensaver,
            clock=self.clock,
        )
        session.start()
        return session

    def test_advances_on_idle(self):
        self.assertEqual(self.session.next_timeout(), 10.0)
        self.clock.advance(9.9)
        self.assertAlmostEqual(self.session.next_timeout(), 0.1)
        self.clock.advance(0.1)
        action = self.session.on_timeout()
        self.assertEqual(self.session.pager.offset, 4)
        self.assertEqual(self.session.pagers["600"].offset, 4)
        self.assertTrue(action.raw)

    def test_ticks_do_not_reset_the_carousel(self):
        session = self.make_session(initial="601")
        for _ in range(4):
            self.clock.advance(2.0)
            session.tick()
        self.clock.advance(1.0)
        self.assertEqual(session.next_timeout(), 1.0)
        self.clock.advance(1.0)
        session.on_timeout()
        self.assertEqual(session.pager.offset, 4)

    def test_total_change_does_not_reset_the_carousel(self):
        session = self.make_session(initial="609")
        self.clock.advance(5.0)
        session.state["total"] = 13
        session.tick()
        for _ in range(2):
            self.clock.advance(2.0)
            session.tick()
        self.assertEqual(session.next_timeout(), 1.0)
        self.clock.advance(1.0)
        session.on_timeout()
        self.assertEqual(session.pager.offset, 4)

    def test_empty_data_pauses_and_restarts_the_carousel(self):
        session = self.make_session(initial="610")
        self.clock.advance(5.0)
        session.state["total"] = 0
        session.refresh()
        self.assertIsNone(session.next_timeout())
        self.clock.advance(1.0)
        session.state["total"] = 13
        session.refresh()
        self.assertEqual(session.next_timeout(), 10.0)
        self.clock.advance(10.0)
        session.on_timeout()
        self.assertEqual(session.pager.offset, 4)

    def test_input_resets_the_carousel(self):
        self.clock.advance(9.0)
        self.session.feed(b"x")
        self.assertEqual(self.session.next_timeout(), 10.0)
        self.clock.advance(1.0)
        self.session.on_timeout()
        self.assertEqual(self.session.pager.offset, 0)
        self.clock.advance(9.0)
        self.session.on_timeout()
        self.assertEqual(self.session.pager.offset, 4)

    def test_field_text_pauses_the_carousel(self):
        session = self.make_session(initial="602")
        session.feed(b"1")
        self.assertEqual(session.values["input"], "1")
        self.clock.advance(10.0)
        self.assertIsNone(session.next_timeout())
        session.on_timeout()
        self.assertEqual(session.pager.offset, 0)

        session.feed(ANNULATION)
        self.assertEqual(session.values["input"], "")
        self.clock.advance(10.0)
        session.on_timeout()
        self.assertEqual(session.pager.offset, 4)

    def test_single_page_does_not_advance(self):
        session = self.make_session(initial="603")
        self.assertIsNone(session.next_timeout())
        self.clock.advance(20.0)
        session.on_timeout()
        self.assertEqual(session.pager.offset, 0)

    def test_wrap_disabled_stops_at_the_last_page(self):
        session = self.make_session(initial="604")
        for expected in (4, 8):
            self.clock.advance(10.0)
            session.on_timeout()
            self.assertEqual(session.pager.offset, expected)
        self.assertIsNone(session.next_timeout())
        self.clock.advance(10.0)
        session.on_timeout()
        self.assertEqual(session.pager.offset, 8)

    def test_manual_pager_move_restarts_the_interval(self):
        self.clock.advance(9.0)
        self.session.feed(SUITE)
        self.assertEqual(self.session.pager.offset, 4)
        self.assertEqual(self.session.next_timeout(), 10.0)
        self.clock.advance(10.0)
        self.session.on_timeout()
        self.assertEqual(self.session.pager.offset, 8)

    def test_pager_offset_is_remembered_across_navigation(self):
        self.clock.advance(10.0)
        self.session.on_timeout()
        self.session.navigate("606")
        self.assertIsNone(self.session.pager)
        self.session.navigate("600")
        self.assertEqual(self.session.pager.offset, 4)
        self.assertEqual(self.session.next_timeout(), 10.0)

    def test_screensaver_suspends_the_content_carousel(self):
        saver = self.registry.get("700")
        screensaver = Screensaver.from_spec(
            self.registry, (saver,), after=30.0, hold=5.0
        )
        session = self.make_session(screensaver=screensaver)
        for _ in range(2):
            self.clock.advance(10.0)
            session.on_timeout()
        self.assertEqual(session.pager.offset, 8)
        self.clock.advance(10.0)
        session.on_timeout()
        self.assertTrue(session.screensaver_active)
        self.assertEqual(session.pager.offset, 8)
        self.assertIsNone(session.next_timeout())

        session.feed(b"x")
        self.assertFalse(session.screensaver_active)
        self.assertEqual(session.pager.offset, 8)
        self.assertEqual(session.next_timeout(), 10.0)

    def test_no_screensaver_page_suppresses_automatic_takeover(self):
        saver = self.registry.get("700")
        screensaver = Screensaver.from_spec(
            self.registry, (saver,), after=10.0, hold=5.0
        )
        session = self.make_session(initial="605", screensaver=screensaver)
        self.clock.advance(10.0)
        self.assertIsNone(session.next_timeout())
        session.on_timeout()
        self.assertFalse(session.screensaver_active)
        session.activate_screensaver()
        self.assertTrue(session.screensaver_active)

    def test_no_screensaver_page_can_keep_advancing(self):
        saver = self.registry.get("700")
        screensaver = Screensaver.from_spec(
            self.registry, (saver,), after=10.0, hold=5.0
        )
        session = self.make_session(initial="607", screensaver=screensaver)
        self.clock.advance(5.0)
        session.on_timeout()
        self.assertEqual(session.pager.offset, 4)
        self.clock.advance(5.0)
        session.on_timeout()
        self.assertFalse(session.screensaver_active)
        self.assertEqual(session.pager.offset, 8)

    def test_set_pager_rejects_a_non_carousel_policy(self):
        @page("608")
        def bad(ctx):
            ctx.set_pager(12, 4, carousel="no")
            return Screen()

        self.registry.add(bad)
        session = Session(
            self.registry,
            M1,
            initial="608",
            fallback=self.registry.get("699"),
            clock=self.clock,
        )
        with self.assertRaises(TypeError):
            session.start()


if __name__ == "__main__":
    unittest.main()
