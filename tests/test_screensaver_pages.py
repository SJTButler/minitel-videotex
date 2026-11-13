import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pages

from minitel import M1, Session
from minitel.protocol import codec
from pages.screensavers import clock as clock_page
from pages.screensavers import scroll as scroll_page
from pages.screensavers._support.text import LINES

ENVOI = bytes([0x13, 0x41])


class ScreensaverPageTests(unittest.TestCase):
    def setUp(self):
        self.registry = pages.build_registry()
        self.session = Session(
            self.registry,
            M1,
            initial="190",
            fallback=self.registry.get(pages.NOT_FOUND),
            screensaver=("900",),
        )
        self.session.start()

    def feed(self, data):
        return self.session.feed(data)

    def test_registry_declares_screensaver_groups(self):
        groups = self.registry.screensaver_groups()
        self.assertIn(pages.DEFAULT_SCREENSAVER, groups)
        self.assertEqual(
            list(groups),
            ["clock", "test_card", "scroll", "bouncing_ball", "carousel"],
        )
        self.assertEqual(
            [page.number for page in groups["carousel"]],
            ["910", "911", "912"],
        )
        self.assertEqual(
            [page.number for page in self.registry.screensaver_pages("all")],
            ["900", "901", "902", "903", "910", "911", "912"],
        )
        self.assertIsNone(self.registry.screensaver_pages("missing"))
        self.assertEqual(self.registry.get("900").screensaver, "clock")
        self.assertEqual(self.registry.get("902").screensaver, "scroll")

    def test_selector_layout(self):
        text = self.session.screen.to_text().splitlines()
        self.assertEqual(text[1].strip(), "SCREENSAVER")
        self.assertEqual(text[3].strip(), "SCREENSAVER SETTINGS")
        self.assertEqual(text[5][:20].strip(), "> 1  CLOCK")
        self.assertEqual(text[5][20:].strip(), "5  CAROUSEL")
        self.assertEqual(text[6][:20].strip(), "2  TEST CARD")
        self.assertEqual(text[7][:20].strip(), "3  SCROLL")
        self.assertEqual(text[8][:20].strip(), "4  BOUNCING BALL")
        self.assertEqual(text[12].strip(), "CHOICE: CLOCK")
        self.assertEqual(text[13].strip(), "AUTO: 2 MIN")
        self.assertEqual((self.session.screen.cursor_row,
                          self.session.screen.cursor_col), (20, 6))

    def test_selector_selects_each_option(self):
        self.feed(b"3" + ENVOI)
        self.assertEqual(
            [page.number for page in self.session.screensaver.pages],
            ["902"],
        )
        self.assertIn("SCROLL", self.session.screen.to_text())

        self.feed(b"4" + ENVOI)
        self.assertEqual(
            [page.number for page in self.session.screensaver.pages],
            ["903"],
        )
        self.assertIn("BOUNCING BALL", self.session.screen.to_text())

        self.feed(b"5" + ENVOI)
        self.assertEqual(
            [page.number for page in self.session.screensaver.pages],
            ["910", "911", "912"],
        )
        self.assertIn("CAROUSEL", self.session.screen.to_text())

    def test_selector_activates_the_current_choice(self):
        self.feed(b"0" + ENVOI)
        self.assertTrue(self.session.screensaver_active)
        self.assertEqual(self.session.current.number, "190")
        self.assertIn("LOCAL TIME", self.session.screen.to_text())

    def test_selector_preserves_carousel_policy(self):
        self.session.set_screensaver(
            ("900",), after=300.0, hold=7.0, wrap=False
        )
        self.feed(b"1" + ENVOI)
        self.assertEqual(self.session.screensaver.after, 300.0)
        self.assertEqual(self.session.screensaver.hold, 7.0)
        self.assertFalse(self.session.screensaver.wrap)

    def test_selector_cycles_the_delay(self):
        self.assertEqual(self.session.screensaver.after, 120.0)
        self.feed(b"6" + ENVOI)
        self.assertEqual(self.session.screensaver.after, 300.0)
        self.feed(b"6" + ENVOI)
        self.assertEqual(self.session.screensaver.after, 600.0)
        self.feed(b"6" + ENVOI)
        self.assertIsNone(self.session.screensaver.after)
        self.assertIn("AUTO: OFF", self.session.screen.to_text())
        self.feed(b"6" + ENVOI)
        self.assertEqual(self.session.screensaver.after, 120.0)

    def test_selector_works_without_a_configured_screensaver(self):
        session = Session(
            self.registry,
            M1,
            initial="190",
            fallback=self.registry.get(pages.NOT_FOUND),
        )
        session.start()
        self.assertIn("NONE", session.screen.to_text())
        session.feed(b"0" + ENVOI)
        self.assertIsNotNone(session.screensaver)
        self.assertTrue(session.screensaver_active)

    def test_only_substantial_repaint_pages_opt_out(self):
        opted_out = {
            page.number
            for page in self.registry.all()
            if page.no_screensaver
        }
        self.assertEqual(opted_out, {"111", "150", "155"})

    def test_home_links_to_veille(self):
        session = Session(
            self.registry,
            M1,
            initial=pages.INITIAL,
            fallback=self.registry.get(pages.NOT_FOUND),
        )
        text = session.start().to_text().splitlines()
        self.assertEqual(text[9].strip(), "5  LIVE SCORES")
        self.assertEqual(text[10].strip(), "6  VIDIPRINTER")
        self.assertEqual(text[11].strip(), "7  SCREENSAVER")
        self.assertIn("TYPE A NUMBER", text[12])

    def test_clock_page(self):
        self.assertEqual(self.registry.get("900").paint, "cell")
        first = time.localtime(0)
        second = time.localtime(1)
        with patch.object(
            clock_page, "local_now", side_effect=[first, second]
        ):
            session = Session(
                self.registry, M1, initial="900",
                fallback=self.registry.get(pages.NOT_FOUND),
            )
            text = session.start().to_text()
            action = session.tick()
        self.assertIn("3615 KILO", text)
        self.assertIn("LOCAL TIME", text)
        self.assertIn("PRESS ANY KEY", text)
        self.assertFalse(session.screen.cursor_visible)
        self.assertIsNone(action.screen)
        self.assertNotIn(bytes([codec.CAN]), action.raw)

    def test_scroll_text_is_wrapped_and_encodable(self):
        self.assertTrue(LINES)
        for line in LINES:
            self.assertLess(len(line), codec.COLS)
            codec.text(line)

    def test_scroll_page_loops_after_the_gap(self):
        ctx = SimpleNamespace(state={})
        total = len(LINES) + scroll_page.LOOP_GAP
        frame = None
        for _ in range(total):
            frame = scroll_page.scroll_tick(ctx)
        self.assertEqual(ctx.state[scroll_page.STATE_KEY], 0)
        self.assertEqual(
            frame.to_text().splitlines()[1].strip(), "SONNET 18"
        )
        self.assertEqual(
            frame.to_text().splitlines()[0].strip(),
            "3615 KILO / SHAKESPEARE",
        )

    def test_scroll_page_keeps_status_and_advances_one_line(self):
        session = Session(
            self.registry, M1, initial="902",
            fallback=self.registry.get(pages.NOT_FOUND),
        )
        session.start()
        self.assertTrue(session.scroll_mode)
        self.assertTrue(session.screen_scroll_mode)
        self.assertEqual(session.fields, [])
        self.assertEqual(session.current.back_page, "190")

        lines = session.screen.to_text().splitlines()
        self.assertEqual(lines[0].strip(), "3615 KILO / SHAKESPEARE")
        self.assertEqual(lines[1].strip(), "SONNET 18")

        first = session.tick()
        self.assertIsNone(first.screen)
        self.assertIn(bytes([0x0A]), first.raw)
        action = session.tick()
        self.assertIsNone(action.screen)
        self.assertIn(bytes([0x0A]), action.raw)
        self.assertEqual(
            session.screen.to_text().splitlines()[1].strip(),
            "SHALL I COMPARE THEE TO A SUMMER'S DAY?",
        )
        status_line = session.screen.to_text().splitlines()[0]
        self.assertEqual(status_line.strip(), "3615 KILO / SHAKESPEARE")

    def test_scroll_echo_does_not_wake_the_screensaver(self):
        session = Session(
            self.registry,
            M1,
            initial="100",
            fallback=self.registry.get(pages.NOT_FOUND),
            screensaver=("902",),
        )
        session.start()
        session.activate_screensaver()
        action = session.tick()
        self.assertIn(bytes([0x0A]), action.raw)
        self.assertTrue(session.screensaver_active)
        self.assertEqual(session.feed(b"\x0a"), [])
        self.assertTrue(session.screensaver_active)
        self.assertEqual(session.feed(b"\x0d\x0a"), [])
        self.assertTrue(session.screensaver_active)

    def test_mire_page(self):
        session = Session(
            self.registry, M1, initial="901",
            fallback=self.registry.get(pages.NOT_FOUND),
        )
        text = session.start().to_text()
        self.assertIn("TEST CARD 3615 KILO", text)
        self.assertIn("PROFILE: MINITEL 1", text)
        self.assertIn("MAX: 1200 BPS", text)

    def test_promo_pages(self):
        for number, marker in (
            ("910", "3615 KILO"),
            ("911", "THE NEWS"),
            ("912", "THE WEATHER"),
        ):
            session = Session(
                self.registry, M1, initial=number,
                fallback=self.registry.get(pages.NOT_FOUND),
            )
            text = session.start().to_text()
            self.assertIn(marker, text)
            self.assertIn("PRESS ANY KEY", text)

    def test_ball_moves_and_stays_inside_the_border(self):
        self.assertEqual(self.registry.get("903").paint, "cell")
        session = Session(
            self.registry, M1, initial="903",
            fallback=self.registry.get(pages.NOT_FOUND),
        )
        session.start()
        state = session.state["screensaver_ball"]
        start = (state["row"], state["col"])
        action = session.tick()
        self.assertNotEqual((state["row"], state["col"]), start)
        self.assertIsNone(action.screen)
        self.assertNotIn(bytes([codec.CAN]), action.raw)

        for _ in range(80):
            session.tick()
            self.assertTrue(4 <= state["row"] <= 17)
            self.assertTrue(5 <= state["col"] <= 34)
        self.assertIn("O", session.screen.to_text())
        self.assertIn("PRESS ANY KEY", session.screen.to_text())


if __name__ == "__main__":
    unittest.main()
