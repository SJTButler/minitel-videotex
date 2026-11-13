import unittest

from minitel.protocol import codec
from minitel.render import Cell, Screen, compose_row


class ScreenTests(unittest.TestCase):
    def test_clear(self):
        s = Screen()
        s.text(1, 0, "HELLO")
        s.clear()
        self.assertEqual(s.to_text(), "\n".join([" " * codec.COLS] * codec.ROWS))

    def test_clone_is_independent(self):
        s = Screen()
        s.text(1, 0, "BODY")
        s.set_cursor(2, 3, False)
        s.paint_order = "up"
        s.force_full = True
        s.paint = "cell"
        clone = s.clone()
        self.assertEqual(clone.to_text(), s.to_text())
        self.assertEqual((clone.cursor_row, clone.cursor_col), (2, 3))
        self.assertFalse(clone.cursor_visible)
        self.assertEqual(clone.paint_order, "up")
        self.assertTrue(clone.force_full)
        self.assertEqual(clone.paint, "cell")
        clone.text(1, 0, "CLONE")
        self.assertTrue(s.to_text().splitlines()[1].startswith("BODY"))

    def test_compose_row_replaces_only_that_row(self):
        s = Screen()
        s.text(1, 0, "BODY")
        s.set_cursor(2, 3, False)
        row = [Cell() for _ in range(codec.COLS)]
        row[0] = Cell(ch="H")
        s.paint = "cell"
        composed = compose_row(s, 0, row)
        self.assertEqual(
            "".join(cell.ch for cell in composed.rows[0]).strip(), "H"
        )
        self.assertEqual(composed.paint, "cell")
        self.assertTrue(
            composed.to_text().splitlines()[1].startswith("BODY")
        )
        self.assertEqual(
            (composed.cursor_row, composed.cursor_col), (2, 3)
        )
        self.assertEqual(
            "".join(cell.ch for cell in s.rows[0]).strip(), ""
        )

    def test_compose_row_rejects_the_wrong_width(self):
        s = Screen()
        with self.assertRaises(ValueError):
            compose_row(s, 0, [Cell()])

    def test_text(self):
        s = Screen()
        s.text(1, 2, "HELLO")
        self.assertEqual(s.rows[1][2].ch, "H")
        self.assertEqual(s.rows[1][6].ch, "O")

    def test_overflow(self):
        s = Screen()
        with self.assertRaises(ValueError):
            s.text(1, 0, "A" * 41)
        with self.assertRaises(ValueError):
            s.text(1, 39, "AB")

    def test_fill(self):
        s = Screen()
        s.fill(4, 3, 5, "x")
        self.assertEqual("".join(c.ch for c in s.rows[4][3:8]), "xxxxx")

    def test_rule(self):
        s = Screen()
        s.rule(5, 0, 40, "=")
        self.assertEqual("".join(c.ch for c in s.rows[5]), "=" * 40)

    def test_field(self):
        s = Screen()
        s.field(10, 5, 20)
        self.assertEqual(s.cursor_row, 10)
        self.assertEqual(s.cursor_col, 5)
        self.assertTrue(all(c.inverse for c in s.rows[10][5:25]))

    def test_bad_row(self):
        s = Screen()
        with self.assertRaises(ValueError):
            s.put(25, 0, "x")
        with self.assertRaises(ValueError):
            s.put(0, 40, "x")

    def test_double_width_uses_two_columns(self):
        s = Screen()
        s.text(1, 0, "X" * 20, size=codec.DOUBLE_WIDTH)
        with self.assertRaises(ValueError):
            s.text(1, 0, "X" * 21, size=codec.DOUBLE_WIDTH)

    def test_double_height_needs_a_continuation_row(self):
        s = Screen()
        s.text(23, 0, "OK", size=codec.DOUBLE_HEIGHT)
        with self.assertRaises(ValueError):
            s.text(24, 0, "NO", size=codec.DOUBLE_HEIGHT)

    def test_put_and_fill_require_one_character(self):
        s = Screen()
        with self.assertRaises(ValueError):
            s.put(0, 0, "AB")
        with self.assertRaises(ValueError):
            s.fill(0, 0, 2, "AB")

    def test_unknown_size_is_rejected(self):
        s = Screen()
        with self.assertRaises(ValueError):
            s.text(0, 0, "X", size=99)


if __name__ == "__main__":
    unittest.main()
