import unittest

import pages

from minitel import M1, Session

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
            ["clock", "test_card", "bouncing_ball", "carousel"],
        )
        self.assertEqual(
            [page.number for page in groups["carousel"]],
            ["910", "911", "912"],
        )
        self.assertEqual(
            [page.number for page in self.registry.screensaver_pages("all")],
            ["900", "901", "903", "910", "911", "912"],
        )
        self.assertIsNone(self.registry.screensaver_pages("missing"))
        self.assertEqual(self.registry.get("900").screensaver, "clock")

    def test_selector_layout(self):
        text = self.session.screen.to_text().splitlines()
        self.assertEqual(text[1].strip(), "SCREENSAVER")
        self.assertEqual(text[3].strip(), "SCREENSAVER SETTINGS")
        self.assertEqual(text[5].strip(), "> 1  CLOCK")
        self.assertEqual(text[12].strip(), "CHOICE: CLOCK")
        self.assertEqual(text[13].strip(), "AUTO: 2 MIN")
        self.assertEqual((self.session.screen.cursor_row,
                          self.session.screen.cursor_col), (20, 6))

    def test_selector_selects_each_option(self):
        self.feed(b"3" + ENVOI)
        self.assertEqual(
            [page.number for page in self.session.screensaver.pages],
            ["903"],
        )
        self.assertIn("BOUNCING BALL", self.session.screen.to_text())

        self.feed(b"4" + ENVOI)
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
        self.assertEqual(opted_out, {"111", "150"})

    def test_home_links_to_veille(self):
        session = Session(
            self.registry,
            M1,
            initial=pages.INITIAL,
            fallback=self.registry.get(pages.NOT_FOUND),
        )
        text = session.start().to_text().splitlines()
        self.assertEqual(text[9].strip(), "5  LIVE SCORES")
        self.assertEqual(text[10].strip(), "7  SCREENSAVER")
        self.assertIn("TYPE A NUMBER", text[11])

    def test_clock_page(self):
        session = Session(
            self.registry, M1, initial="900",
            fallback=self.registry.get(pages.NOT_FOUND),
        )
        text = session.start().to_text()
        self.assertIn("3615 KILO", text)
        self.assertIn("LOCAL TIME", text)
        self.assertIn("PRESS ANY KEY", text)
        self.assertFalse(session.screen.cursor_visible)

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
        session = Session(
            self.registry, M1, initial="903",
            fallback=self.registry.get(pages.NOT_FOUND),
        )
        session.start()
        state = session.state["screensaver_ball"]
        start = (state["row"], state["col"])
        session.tick()
        self.assertNotEqual((state["row"], state["col"]), start)

        for _ in range(80):
            session.tick()
            self.assertTrue(4 <= state["row"] <= 17)
            self.assertTrue(5 <= state["col"] <= 34)
        self.assertIn("O", session.screen.to_text())
        self.assertIn("PRESS ANY KEY", session.screen.to_text())


if __name__ == "__main__":
    unittest.main()
