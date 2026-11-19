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

    def test_double_width_marks_continuation_cells(self):
        s = Screen()
        s.text(1, 0, "AB", size=codec.DOUBLE_WIDTH)

        self.assertEqual(s.rows[1][0].ch, "A")
        self.assertFalse(s.rows[1][0].continuation)
        self.assertTrue(s.rows[1][1].continuation)
        self.assertEqual(s.rows[1][2].ch, "B")
        self.assertTrue(s.rows[1][3].continuation)
        self.assertTrue(s.to_text().splitlines()[1].startswith("AB"))

        with self.assertRaises(ValueError):
            s.put(1, 1, "X")

    def test_double_height_needs_a_continuation_row(self):
        s = Screen()
        s.text(23, 0, "OK", size=codec.DOUBLE_HEIGHT)
        with self.assertRaises(ValueError):
            s.text(24, 0, "NO", size=codec.DOUBLE_HEIGHT)

    def test_double_height_reserves_the_row_below(self):
        s = Screen()
        s.text(5, 0, "BIG", size=codec.DOUBLE_HEIGHT)

        self.assertFalse(s.rows[5][0].continuation)
        self.assertTrue(s.rows[6][0].continuation)
        self.assertTrue(s.rows[6][1].continuation)
        self.assertTrue(s.rows[6][2].continuation)

        with self.assertRaises(ValueError):
            s.put(6, 0, "X")
        with self.assertRaises(ValueError):
            s.text(6, 20, "SIDE")

    def test_put_and_fill_require_one_character(self):
        s = Screen()
        with self.assertRaises(ValueError):
            s.put(0, 0, "AB")
        with self.assertRaises(ValueError):
            s.fill(0, 0, 2, "AB")

    def test_put_mosaic(self):
        s = Screen()
        s.put_mosaic(2, 3, 48, fg=codec.RED, inverse=True)
        cell = s.rows[2][3]
        self.assertEqual(cell.mosaic, 48)
        self.assertEqual(cell.ch, " ")
        self.assertEqual(cell.fg, codec.RED)
        self.assertTrue(cell.inverse)
        self.assertEqual(s.to_text().splitlines()[2][3], "\U0001FB02")

    def test_mosaic_clone_and_clear(self):
        s = Screen()
        s.put_mosaic(1, 1, 63)
        clone = s.clone()
        self.assertEqual(clone.rows[1][1].mosaic, 63)
        self.assertIsNot(clone.rows[1][1], s.rows[1][1])
        s.clear()
        self.assertIsNone(s.rows[1][1].mosaic)

    def test_mosaic_can_overwrite_text_and_vice_versa(self):
        s = Screen()
        s.text(1, 0, "A")
        s.put_mosaic(1, 0, 1)
        self.assertEqual(s.rows[1][0].mosaic, 1)
        s.text(1, 0, "B")
        self.assertIsNone(s.rows[1][0].mosaic)
        self.assertEqual(s.rows[1][0].ch, "B")

    def test_mosaic_validation(self):
        s = Screen()
        with self.assertRaises(ValueError):
            s.put_mosaic(0, 0, 64)
        with self.assertRaises(ValueError):
            s.put_mosaic(0, 0, -1)
        with self.assertRaises(TypeError):
            s.put_mosaic(0, 0, "x")
        with self.assertRaises(ValueError):
            s.put_mosaic(0, 0, 1, size=codec.DOUBLE_WIDTH)
        with self.assertRaises(ValueError):
            s.put_mosaic(0, 0, 1, underline=True)
        with self.assertRaises(TypeError):
            s.put_mosaic(0, 0, 1, mosaic=1)
        with self.assertRaises(TypeError):
            s.put_mosaic(0, 0, 1, ch="A")
        with self.assertRaises(TypeError):
            s.put_mosaic(0, 0, 1, continuation=True)

    def test_text_rejects_mosaic_attribute(self):
        s = Screen()
        with self.assertRaises(TypeError):
            s.text(0, 0, "A", mosaic=1)
        with self.assertRaises(TypeError):
            s.put(0, 0, "A", mosaic=1)
        with self.assertRaises(TypeError):
            s.fill(0, 0, 1, "A", mosaic=1)

    def test_mosaic_respects_reserved_rows(self):
        s = Screen()
        s.text(5, 0, "BIG", size=codec.DOUBLE_HEIGHT)
        with self.assertRaises(ValueError):
            s.put_mosaic(6, 0, 1)

    def test_unknown_size_is_rejected(self):
        s = Screen()
        with self.assertRaises(ValueError):
            s.text(0, 0, "X", size=99)


if __name__ == "__main__":
    unittest.main()
