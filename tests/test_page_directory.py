import unittest

import pages

from minitel import Screen, page
from minitel.terminal import profiles
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
        self.assertTrue(text[16].startswith("155"))
        self.assertIn("NUMBER:", text[17])

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertIn("REGISTERED PAGES 2/2", session.screen.to_text())
        self.assertTrue(text[5].startswith("190"))
        self.assertTrue(text[6].startswith("199"))
        self.assertTrue(text[7].startswith("900"))
        self.assertTrue(text[8].startswith("901"))
        self.assertTrue(text[9].startswith("902"))
        self.assertTrue(text[10].startswith("903"))
        self.assertTrue(text[11].startswith("910"))
        self.assertTrue(text[12].startswith("911"))
        self.assertTrue(text[13].startswith("912"))

    def test_hides_internal_pages(self):
        session = make_session()
        self.assertNotIn("__not_found__", session.screen.to_text())

    def test_marks_extension_aware_pages(self):
        session = make_session()
        text = session.screen.to_text().splitlines()
        self.assertTrue(text[9].startswith("120#"))
        self.assertTrue(text[12].startswith("150#"))
        self.assertTrue(text[14].startswith("153#"))
        self.assertFalse(text[5].startswith("100#"))

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertTrue(text[7].startswith("900*"))
        self.assertNotIn("#", text[7])

    def test_number_markers_can_combine(self):
        registry = pages.build_registry()

        @page("156", title="BOTH", screensaver="test", extensions=True)
        def both(ctx):
            return Screen()

        registry.add(both)
        session = make_session(registry)
        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertTrue(text[5].startswith("156*#"))

    def test_shows_aliases_and_flags(self):
        session = make_session()
        text = session.screen.to_text().splitlines()
        self.assertIn(" 0", text[5])
        self.assertIn(" 1", text[6])
        self.assertIn(" 2", text[9])
        self.assertIn(" 3", text[10])
        self.assertIn(" 4", text[11])
        self.assertIn(" 5", text[12])
        self.assertIn(" 6", text[16])
        self.assertIn("DN", text[7])
        self.assertIn("F", text[11])

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertIn(" 7", text[5])
        self.assertTrue(text[7].startswith("900*"))
        self.assertIn("D", text[7])

    def test_marks_scrolling_pages(self):
        session = make_session()
        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertTrue(text[9].startswith("902*"))
        self.assertEqual(text[9][34:].strip(), "DS")

    def test_screensaver_group_is_a_prefix_when_it_differs(self):
        session = make_session()
        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertTrue(text[7].startswith("900*"))
        self.assertIn("CLOCK", text[7])
        self.assertNotIn("CLOCK:", text[7])

        self.assertTrue(text[9].startswith("902*"))
        self.assertIn("SCROLL: SHAKESPEARE", text[9])
        self.assertTrue(text[10].startswith("903*"))
        self.assertIn("BOUNCING BALL", text[10])
        self.assertTrue(text[11].startswith("910*"))
        self.assertIn("CAROUSEL: KILO", text[11])
        self.assertTrue(text[12].startswith("911*"))
        self.assertIn("CAROUSEL: NEWS", text[12])
        self.assertTrue(text[13].startswith("912*"))
        self.assertIn("CAROUSEL: WEATHER", text[13])

    def test_has_page_input_and_footer(self):
        session = make_session()
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col),
            (20, 6),
        )
        text = session.screen.to_text().splitlines()
        self.assertTrue(text[22].startswith("SOMMAIRE=HOME"))
        self.assertIn("NUMBER:", text[17])
        self.assertIn("* SAVER", text[17])
        self.assertIn("# EXT", text[17])
        self.assertIn("FLAGS:", text[18])
        self.assertIn("D DYN", text[18])
        self.assertIn("T TRANS", text[18])
        self.assertNotIn("FLAGS:", text[19])
        self.assertIn("N NO-SLEEP", text[19])
        self.assertIn("S SCROLL", text[19])

    def test_suite_pages_through_a_growing_registry(self):
        registry = pages.build_registry()

        @page("250", title="EXTRA")
        def extra(ctx):
            return Screen()

        registry.add(extra)
        session = make_session(registry)
        self.assertIn("REGISTERED PAGES 1/2", session.screen.to_text())
        lines = session.screen.to_text().splitlines()
        self.assertTrue(lines[16].startswith("155"))
        session.feed(SUITE)
        text = session.screen.to_text()
        self.assertIn("REGISTERED PAGES 2/2", text)
        lines = text.splitlines()
        self.assertTrue(lines[5].startswith("190"))
        self.assertTrue(lines[6].startswith("199"))
        self.assertTrue(lines[7].startswith("250"))
        self.assertTrue(lines[8].startswith("900"))
        self.assertTrue(lines[9].startswith("901"))
        self.assertTrue(lines[14].startswith("912"))


if __name__ == "__main__":
    unittest.main()
