import unittest

from minitel.design.stops import Stop, Stops, reveal_offset, reveal_viewport
from minitel.design.viewport import Viewport
from minitel.pagemodel import Registry, page
from minitel.render import Screen
from minitel.session import Session
from minitel.terminal.profiles import M1

SUITE = bytes([0x13, 0x48])
RETOUR = bytes([0x13, 0x42])

LINES = tuple(f"L{n:02d}" for n in range(20))
STOPS = (Stop(0, 0, 0), Stop(10, 10, 1), Stop(15, 15, 2))


class StopsValueTests(unittest.TestCase):
    def test_starts_and_wrap(self):
        stops = Stops(STOPS, start_next=1, start_prev=2)
        self.assertEqual(stops.next().selected, 1)
        self.assertEqual(stops.prev().selected, 2)
        self.assertEqual(stops.next().next().selected, 2)
        self.assertEqual(stops.next().next().next().selected, 0)
        self.assertEqual(stops.prev().prev().selected, 1)

    def test_clamp_and_identity(self):
        stops = Stops(STOPS, selected=9, start_next=9, start_prev=-2)
        clamped = stops.clamp()
        self.assertEqual(clamped.selected, 2)
        self.assertEqual(clamped.start_next, 2)
        self.assertEqual(clamped.start_prev, 0)
        self.assertEqual(clamped.identity, ((0, 0), (10, 1), (15, 2)))
        self.assertEqual(Stops(()).clamp().selected, None)
        self.assertEqual(Stops(()).next().selected, None)

    def test_reveal(self):
        view = Viewport(20, 5, 7)
        self.assertEqual(reveal_offset(view, 10), 7)
        self.assertEqual(reveal_offset(view, 2), 1)
        self.assertEqual(reveal_offset(view, 15), 12)
        revealed = reveal_viewport(view, 15)
        self.assertEqual(revealed.offset, 12)
        self.assertFalse(revealed.follow)


class SessionStopsTests(unittest.TestCase):
    def make_session(self):
        @page("988", scroll=True)
        def paged(ctx):
            view = ctx.set_viewport(20, 5)
            current = ctx.set_stops(STOPS)
            screen = Screen()
            for index, line in enumerate(view.window(LINES)):
                screen.text(1 + index, 0, line)
            selected = current.selected_stop
            screen.text(0, 0, f"SEL {selected.link if selected else 'NONE'}")
            return screen

        registry = Registry()
        registry.add(paged)
        session = Session(registry, M1, initial="988", fallback=paged)
        session.start()
        return session

    def test_first_press_selects_start_and_reveals(self):
        session = self.make_session()
        self.assertIsNone(session.stops.selected)
        session.feed(SUITE)
        self.assertEqual(session.stops.selected, 0)
        self.assertEqual(session.viewport.offset, 0)
        self.assertEqual(session.screen.rows[0][0].ch, "S")

        session.feed(SUITE)
        self.assertEqual(session.stops.selected, 1)
        self.assertEqual(session.viewport.offset, 7)
        self.assertEqual(session.screen.rows[1][0].ch, "L")
        self.assertEqual(session.screen.rows[1][1].ch, "0")
        self.assertEqual(session.screen.rows[1][2].ch, "7")

    def test_cycle_wraps_both_ends(self):
        session = self.make_session()
        for _ in range(3):
            session.feed(SUITE)
        self.assertEqual(session.stops.selected, 2)
        self.assertEqual(session.viewport.offset, 12)
        session.feed(SUITE)
        self.assertEqual(session.stops.selected, 0)
        self.assertEqual(session.viewport.offset, 0)
        session.feed(RETOUR)
        self.assertEqual(session.stops.selected, 2)
        self.assertEqual(session.viewport.offset, 12)

    def test_one_stop_uses_normal_viewport_step(self):
        @page("989", scroll=True)
        def paged(ctx):
            view = ctx.set_viewport(20, 5, step=2)
            ctx.set_stops((Stop(0, 0, 0),))
            screen = Screen()
            for index, line in enumerate(view.window(LINES)):
                screen.text(1 + index, 0, line)
            return screen

        registry = Registry()
        registry.add(paged)
        session = Session(registry, M1, initial="989", fallback=paged)
        session.start()
        session.feed(SUITE)
        self.assertEqual(session.viewport.offset, 2)


if __name__ == "__main__":
    unittest.main()
