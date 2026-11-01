import unittest

import pages

from minitel import Screen, page, profiles
from minitel.session import Session

SUITE = bytes([0x13, 0x48])


def make_session(registry=None):
    registry = registry or pages.build_registry()
    session = Session(
        registry,
        profiles.M1,
        initial="199",
        fallback=registry.get(pages.NOT_FOUND),
        guide=pages.GUIDE,
    )
    session.start()
    return session


class PageDirectoryTests(unittest.TestCase):
    def test_lists_numeric_pages_in_order(self):
        session = make_session()
        text = session.screen.to_text().splitlines()
        self.assertEqual(text[1].strip(), "PAGES")
        self.assertEqual(text[2].strip(), "REGISTERED PAGES 1/2")
        self.assertIn("PAGE", text[4])
        self.assertTrue(text[5].startswith("100"))
        self.assertTrue(text[6].startswith("110"))
        self.assertTrue(text[7].startswith("111"))
        self.assertTrue(text[8].startswith("112"))
        self.assertTrue(text[9].startswith("120"))
        self.assertTrue(text[10].startswith("130"))
        self.assertTrue(text[11].startswith("140"))
        self.assertTrue(text[12].startswith("150"))
        self.assertTrue(text[13].startswith("151"))
        self.assertTrue(text[14].startswith("153"))
        self.assertTrue(text[15].startswith("154"))
        self.assertTrue(text[16].startswith("190"))
        self.assertTrue(text[17].startswith("199"))
        self.assertTrue(text[18].startswith("900"))
        self.assertTrue(text[19].startswith("901"))

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertIn("REGISTERED PAGES 2/2", session.screen.to_text())
        self.assertTrue(text[5].startswith("903"))
        self.assertTrue(text[6].startswith("910"))
        self.assertTrue(text[7].startswith("911"))
        self.assertTrue(text[8].startswith("912"))

    def test_hides_internal_pages(self):
        session = make_session()
        self.assertNotIn("__not_found__", session.screen.to_text())

    def test_shows_aliases_and_flags(self):
        session = make_session()
        text = session.screen.to_text().splitlines()
        self.assertIn(" 0", text[5])
        self.assertIn(" 1", text[6])
        self.assertIn(" 2", text[9])
        self.assertIn(" 3", text[10])
        self.assertIn(" 4", text[11])
        self.assertIn(" 5", text[12])
        self.assertIn(" 7", text[16])
        self.assertIn("D N", text[7])
        self.assertIn("F", text[11])
        self.assertTrue(text[18].startswith("900*"))
        self.assertIn("D", text[18])

    def test_screensaver_group_is_a_prefix_when_it_differs(self):
        session = make_session()
        text = session.screen.to_text().splitlines()
        self.assertTrue(text[18].startswith("900*"))
        self.assertIn("CLOCK", text[18])
        self.assertNotIn("CLOCK:", text[18])

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertTrue(text[5].startswith("903*"))
        self.assertIn("BOUNCING BALL", text[5])
        self.assertTrue(text[6].startswith("910*"))
        self.assertIn("CAROUSEL: KILO", text[6])
        self.assertTrue(text[7].startswith("911*"))
        self.assertIn("CAROUSEL: NEWS", text[7])
        self.assertTrue(text[8].startswith("912*"))
        self.assertIn("CAROUSEL: WEATHER", text[8])

    def test_has_page_input_and_footer(self):
        session = make_session()
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col),
            (20, 6),
        )
        text = session.screen.to_text().splitlines()
        self.assertTrue(text[22].startswith("SOMMAIRE=HOME"))
        self.assertIn("D DYN", text[23])
        self.assertIn("* SAVER", text[23])
        self.assertIn("N NO-SLEEP", text[23])

    def test_suite_pages_through_a_growing_registry(self):
        registry = pages.build_registry()

        @page("250", title="EXTRA")
        def extra(ctx):
            return Screen()

        registry.add(extra)
        session = make_session(registry)
        self.assertIn("REGISTERED PAGES 1/2", session.screen.to_text())
        lines = session.screen.to_text().splitlines()
        self.assertTrue(lines[18].startswith("250"))
        self.assertTrue(lines[19].startswith("900"))
        session.feed(SUITE)
        text = session.screen.to_text()
        self.assertIn("REGISTERED PAGES 2/2", text)
        lines = text.splitlines()
        self.assertTrue(lines[5].startswith("901"))
        self.assertTrue(lines[9].startswith("912"))


if __name__ == "__main__":
    unittest.main()
