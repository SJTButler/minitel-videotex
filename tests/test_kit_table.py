import unittest

from minitel import Screen, codec
from minitel_kit import Column, Table


class ColumnTests(unittest.TestCase):
    def test_left_right_and_center(self):
        self.assertEqual(Column("A", 5).format("x"), "x    ")
        self.assertEqual(Column("A", 5, align="right").format("x"), "    x")
        self.assertEqual(
            Column("A", 5, align="center").format("x"), "  x  "
        )

    def test_truncation_keeps_the_documented_edge(self):
        self.assertEqual(Column("A", 3).format("ABCDE"), "ABC")
        self.assertEqual(
            Column("A", 3, align="right").format("ABCDE"), "CDE"
        )

    def test_invalid_width_and_alignment(self):
        with self.assertRaises(ValueError):
            Column("A", 0)
        with self.assertRaises(ValueError):
            Column("A", 2, align="middle")


class TableTests(unittest.TestCase):
    def setUp(self):
        self.table = Table(
            Column("TIME", 5),
            Column("DESTINATION", 21),
            Column("PLT", 3, align="right"),
            Column("STATUS", 8),
        )

    def test_width(self):
        self.assertEqual(self.table.width, 5 + 1 + 21 + 1 + 3 + 1 + 8)

    def test_format_aligns_columns(self):
        line = self.table.format(("12:00", "DEST 0", "1", "ON TIME"))

        self.assertEqual(line.index("DEST 0"), 6)
        self.assertEqual(line.index("1", 28), 30)
        self.assertEqual(line.index("ON TIME"), 32)
        self.assertFalse(line.endswith(" "))
        self.assertEqual(len(line), 39)

    def test_header_and_row_draw_into_a_screen(self):
        screen = Screen()
        self.table.header(screen, 5, attrs={"fg": codec.CYAN})
        self.table.row(screen, 6, ("12:00", "DEST 0", "1", "ON TIME"))

        lines = screen.to_text().splitlines()
        self.assertEqual(lines[5].index("DESTINATION"), 6)
        self.assertEqual(lines[5].index("PLT"), 28)
        self.assertEqual(lines[5].index("STATUS"), 32)
        self.assertEqual(lines[6].index("DEST 0"), 6)
        self.assertTrue(all(
            cell.fg == codec.CYAN for cell in screen.rows[5][:40]
            if cell.ch != " "
        ))

    def test_per_column_attrs_override_row_attrs(self):
        table = Table(Column("A", 2, fg=codec.RED), Column("B", 2))
        screen = Screen()
        table.row(screen, 1, ("A", "B"), attrs={"fg": codec.CYAN})

        self.assertEqual(screen.rows[1][0].fg, codec.RED)
        self.assertEqual(screen.rows[1][3].fg, codec.CYAN)

    def test_last_column_is_not_padded(self):
        screen = Screen()
        self.table.row(screen, 1, ("12:00", "DEST 0", "1", "ON TIME"))
        visible = [
            cell.ch for cell in screen.rows[1] if not cell.continuation
        ]
        expected = self.table.format(("12:00", "DEST 0", "1", "ON TIME"))
        self.assertEqual("".join(visible)[:len(expected)], expected)

    def test_wrong_value_count_and_oversized_table(self):
        with self.assertRaises(ValueError):
            self.table.row(Screen(), 1, ("only one",))
        with self.assertRaises(ValueError):
            Table(Column("A", 21), Column("B", 21))

    def test_table_can_start_at_an_offset_column(self):
        screen = Screen()
        table = Table(Column("A", 3), Column("B", 3))
        table.header(screen, 1, col=5)
        table.row(screen, 2, ("a", "b"), col=5)

        self.assertEqual(screen.to_text().splitlines()[1][5:10], "A   B")
        self.assertEqual(screen.to_text().splitlines()[2][5:10], "a   b")


if __name__ == "__main__":
    unittest.main()
