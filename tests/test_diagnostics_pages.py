import unittest

import pages
from diagnostics_pages import flood as flood_page
from diagnostics_pages import latency as latency_page

from minitel import M1, Session
from minitel.protocol import codec
from minitel.render import render_screen

ENVOI = bytes([0x13, 0x41])


def make_session(page, *, extra=("diagnostics_pages",)):
    registry = pages.build_registry(*extra)
    session = Session(
        registry,
        M1,
        initial=page,
        fallback=registry.get(pages.NOT_FOUND),
    )
    session.start()
    return session


class DiagnosticsPageTests(unittest.TestCase):
    def test_pages_are_optional(self):
        registry = pages.build_registry()
        for number in ("980", "981", "982", "983", "984"):
            self.assertIsNone(registry.get(number))

    def test_pages_register_when_requested(self):
        registry = pages.build_registry("diagnostics_pages")
        for number in ("980", "981", "982", "983", "984"):
            self.assertIsNotNone(registry.get(number))

    def test_latency_page_logs_input_and_ticks(self):
        session = make_session("980")
        self.assertIn("INPUT / LATENCY", session.screen.to_text())
        self.assertEqual(session.next_timeout(), 1.0)

        session.feed(b"ABC" + ENVOI)
        self.assertEqual(session.state[latency_page.LAST_LINE], "ABC")
        self.assertEqual(session.state[latency_page.EVENTS], 1)

        session.tick()
        self.assertEqual(session.state[latency_page.TICKS], 1)

    def test_flood_page_forces_a_full_paint(self):
        session = make_session("981")
        self.assertFalse(session.state.get(flood_page.FLOOD, False))
        self.assertIsNone(session.tick().screen)

        session.feed(b"ON" + ENVOI)
        self.assertTrue(session.state[flood_page.FLOOD])
        action = session.tick()
        self.assertIsNotNone(action.screen)
        self.assertTrue(action.screen.force_full)
        self.assertEqual(session.state[flood_page.PASSES], 1)

    def test_idle_page_has_no_deadline(self):
        session = make_session("983")
        self.assertIsNone(session.current.tick_interval)
        self.assertTrue(session.current.no_screensaver)
        self.assertIsNone(session.next_timeout())

    def test_signals_page_sends_rep(self):
        session = make_session("982")
        self.assertIn(codec.REP, render_screen(session.screen))

    def test_fault_page_raises_on_confirmation(self):
        session = make_session("984")
        with self.assertRaises(RuntimeError):
            session.feed(b"CRASH" + ENVOI)


if __name__ == "__main__":
    unittest.main()
