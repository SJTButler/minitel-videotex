import unittest

from minitel import Screen
from minitel_kit import Rect


class RectTests(unittest.TestCase):
    def test_text_is_clipped_to_the_pane(self):
        screen = Screen()
        rect = Rect(4, 19, 3, 5)

        rect.text(screen, 0, 0, "ABCDEFGH", inverse=True)

        self.assertEqual(
            "".join(cell.ch for cell in screen.rows[4][19:24]), "ABCDE"
        )
        self.assertTrue(all(cell.inverse for cell in screen.rows[4][19:24]))

    def test_relative_coordinates_and_bounds(self):
        screen = Screen()
        rect = Rect(2, 3, 3, 4)
        rect.text(screen, 2, 3, "X")

        self.assertEqual(screen.rows[4][6].ch, "X")
        with self.assertRaises(ValueError):
            rect.text(screen, 3, 0, "X")
        with self.assertRaises(ValueError):
            rect.text(screen, 0, 4, "X")

    def test_fill_rule_and_field_clip(self):
        screen = Screen()
        rect = Rect(5, 5, 2, 4)
        rect.fill(screen, 0, 1, 10, "x")
        rect.rule(screen, 1, 0, 10, "-")
        rect.field(screen, 1, 0, 10)

        self.assertEqual("".join(c.ch for c in screen.rows[5][5:9]), " xxx")
        self.assertTrue(all(cell.inverse for cell in screen.rows[6][5:9]))
        self.assertEqual((screen.cursor_row, screen.cursor_col), (6, 5))

    def test_sub_rectangles_are_relative_and_bounded(self):
        rect = Rect(2, 3, 10, 20)
        sub = rect.sub(1, 2, 3, 4)

        self.assertEqual((sub.top, sub.left), (3, 5))
        self.assertEqual((sub.height, sub.width), (3, 4))
        with self.assertRaises(ValueError):
            rect.sub(8, 0, 3, 1)

    def test_rect_must_fit_the_screen(self):
        with self.assertRaises(ValueError):
            Rect(24, 0, 2, 1)
        with self.assertRaises(ValueError):
            Rect(0, 39, 1, 2)
        with self.assertRaises(ValueError):
            Rect(0, 0, 0, 1)

    def test_contains(self):
        rect = Rect(1, 2, 3, 4)
        self.assertTrue(rect.contains(2, 3))
        self.assertFalse(rect.contains(3, 0))
        self.assertEqual(rect.bottom, 4)
        self.assertEqual(rect.right, 6)


if __name__ == "__main__":
    unittest.main()
