import unittest

from minitel import codec
from minitel.screen import Screen


class ScreenTests(unittest.TestCase):
    def test_clear(self):
        s = Screen()
        s.text(1, 0, "HELLO")
        s.clear()
        self.assertEqual(s.to_text(), "\n".join([" " * codec.COLS] * codec.ROWS))

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
