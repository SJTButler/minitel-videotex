import unittest
from unittest.mock import Mock

import pages

from minitel import profiles
from minitel.screen import Screen
from minitel.session import Session
from pages.layout import footer, page_input, status


class PageTests(unittest.TestCase):
    def setUp(self):
        self.registry = pages.build_registry()
        self.fallback = self.registry.get(pages.NOT_FOUND)
        self.session = Session(
            self.registry,
            profiles.M1,
            initial=pages.INITIAL,
            fallback=self.fallback,
            guide=pages.GUIDE,
        )
        self.session.start()

    def test_aliases(self):
        home = self.registry.get("100")
        self.assertIs(self.registry.get(""), home)
        self.assertIs(self.registry.get("0"), home)
        self.assertIs(self.registry.get("1"), self.registry.get("110"))
        self.assertIs(self.registry.get("2"), self.registry.get("120"))
        self.assertIs(self.registry.get("3"), self.registry.get("130"))
        self.assertIs(self.registry.get("7"), self.registry.get("190"))
        self.assertIsNone(self.registry.get("999"))

    def test_home_layout(self):
        screen = self.session.start()
        text = screen.to_text().splitlines()
        self.assertTrue(text[0].startswith("3615 KILO"))
        self.assertEqual(text[1].strip(), "3615 KILO")
        self.assertEqual((screen.cursor_row, screen.cursor_col), (20, 6))
        self.assertFalse(screen.cursor_visible)
        self.assertTrue(all(screen.rows[20][c].inverse for c in range(6, 16)))
        self.assertTrue(text[22].startswith("SOMMAIRE=HOME"))

    def test_status_paints_full_row_and_ends_at_fc_boundary(self):
        s = Screen()
        status(s, "PAGE 100")
        self.assertTrue(all(s.rows[0][c].inverse for c in range(40)))
        text = "".join(cell.ch for cell in s.rows[0])
        self.assertEqual(text[29:37], "PAGE 100")
        self.assertEqual(text[37:40], "   ")

    def test_footer_names_the_keys(self):
        s = Screen()
        footer(s)
        text = "".join(cell.ch for cell in s.rows[22])
        self.assertTrue(text.startswith("SOMMAIRE=HOME"))
        self.assertIn("RETOUR=BACK", text)

    def test_page_input_registers_the_field(self):
        s = Screen()
        ctx = Mock()
        page_input(s, ctx)
        ctx.set_input.assert_called_once_with(20, 6, 10, cursor="visible")
        self.assertTrue(all(s.rows[20][c].inverse for c in range(6, 16)))

    def test_page_input_can_hide_the_cursor(self):
        s = Screen()
        ctx = Mock()
        page_input(s, ctx, cursor="hidden")
        ctx.set_input.assert_called_once_with(20, 6, 10, cursor="hidden")

    def test_page_input_auto_cursor(self):
        s = Screen()
        ctx = Mock()
        page_input(s, ctx, cursor="auto")
        ctx.set_input.assert_called_once_with(20, 6, 10, cursor="auto")


if __name__ == "__main__":
    unittest.main()
