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


def find_line(lines, prefix):
    for line in lines:
        if line.startswith(prefix):
            return line
    raise AssertionError(f"no line starts with {prefix!r}")


def page_numbers(lines, start=5, count=12):
    numbers = []
    for line in lines[start:start + count]:
        if not line.strip():
            continue
        numbers.append(line.split()[0].rstrip("*#"))
    return numbers


class PageDirectoryTests(unittest.TestCase):
    def test_lists_numeric_pages_in_order(self):
        session = make_session()
        text = session.screen.to_text().splitlines()
        self.assertEqual(text[1].strip(), "PAGES")
        self.assertEqual(text[2].strip(), "REGISTERED PAGES 1/2")
        self.assertIn("PAGE", text[4])
        self.assertEqual(
            page_numbers(text),
            [
                "100", "110", "111", "112", "120", "130",
                "140", "150", "151", "153", "154", "155",
            ],
        )
        self.assertIn("NUMBER:", text[17])

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertIn("REGISTERED PAGES 2/2", session.screen.to_text())
        self.assertEqual(
            page_numbers(text),
            [
                "160", "190", "199", "900", "901", "902",
                "903", "910", "911", "912",
            ],
        )

    def test_hides_internal_pages(self):
        session = make_session()
        self.assertNotIn("__not_found__", session.screen.to_text())

    def test_marks_extension_aware_pages(self):
        session = make_session()
        text = session.screen.to_text().splitlines()
        self.assertTrue(find_line(text, "120").startswith("120#"))
        self.assertTrue(find_line(text, "150").startswith("150#"))
        self.assertTrue(find_line(text, "151").startswith("151#"))
        self.assertTrue(find_line(text, "153").startswith("153#"))
        self.assertFalse(find_line(text, "100").startswith("100#"))

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        line = find_line(text, "900")
        self.assertTrue(line.startswith("900*"))
        self.assertNotIn("#", line)

    def test_number_markers_can_combine(self):
        registry = pages.build_registry()

        @page("156", title="BOTH", screensaver="test", extensions=True)
        def both(ctx):
            return Screen()

        registry.add(both)
        session = make_session(registry)
        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertTrue(find_line(text, "156").startswith("156*#"))

    def test_shows_aliases_and_flags(self):
        session = make_session()
        text = session.screen.to_text().splitlines()
        self.assertIn(" 0", find_line(text, "100"))
        self.assertIn(" 1", find_line(text, "110"))
        self.assertIn(" 2", find_line(text, "120"))
        self.assertIn(" 3", find_line(text, "130"))
        self.assertIn(" 4", find_line(text, "140"))
        self.assertIn(" 5", find_line(text, "150"))
        self.assertIn(" 6", find_line(text, "155"))
        self.assertIn("DN", find_line(text, "111"))
        self.assertIn("F", find_line(text, "140"))

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertIn(" 7", find_line(text, "190"))
        line = find_line(text, "900")
        self.assertTrue(line.startswith("900*"))
        self.assertIn("D", line)

    def test_marks_scrolling_pages(self):
        session = make_session()
        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        line = find_line(text, "902")
        self.assertTrue(line.startswith("902*"))
        self.assertEqual(line[34:].strip(), "DS")

    def test_screensaver_group_is_a_prefix_when_it_differs(self):
        session = make_session()
        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        line = find_line(text, "900")
        self.assertTrue(line.startswith("900*"))
        self.assertIn("CLOCK", line)
        self.assertNotIn("CLOCK:", line)

        line = find_line(text, "902")
        self.assertTrue(line.startswith("902*"))
        self.assertIn("SCROLL: SHAKESPEARE", line)
        line = find_line(text, "903")
        self.assertTrue(line.startswith("903*"))
        self.assertIn("BOUNCING BALL", line)
        line = find_line(text, "910")
        self.assertTrue(line.startswith("910*"))
        self.assertIn("CAROUSEL: KILO", line)
        line = find_line(text, "911")
        self.assertTrue(line.startswith("911*"))
        self.assertIn("CAROUSEL: NEWS", line)
        line = find_line(text, "912")
        self.assertTrue(line.startswith("912*"))
        self.assertIn("CAROUSEL: WEATHER", line)

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
        self.assertEqual(
            page_numbers(lines),
            [
                "160", "190", "199", "250", "900", "901",
                "902", "903", "910", "911", "912",
            ],
        )


if __name__ == "__main__":
    unittest.main()
