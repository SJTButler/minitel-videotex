import unittest

from minitel import Screen
from minitel_kit import Bars, Sparkline


class BarsTests(unittest.TestCase):
    def test_zero_and_missing_values_leave_gaps(self):
        screen = Screen()
        Bars(2, 1, minimum=0, maximum=1).draw(
            screen, 1, 0, (0, 1)
        )
        self.assertIsNone(screen.rows[1][0].mosaic)
        self.assertEqual(screen.rows[1][1].mosaic, 63)

        screen = Screen()
        Bars(2, 1, minimum=0, maximum=1).draw(
            screen, 1, 0, (1, None)
        )
        self.assertEqual(screen.rows[1][0].mosaic, 63)
        self.assertIsNone(screen.rows[1][1].mosaic)

    def test_scaling_and_gap(self):
        screen = Screen()
        Bars(2, 1, minimum=0, maximum=10).draw(
            screen, 1, 0, (5, 10)
        )
        self.assertEqual(screen.rows[1][0].mosaic, 15)
        self.assertEqual(screen.rows[1][1].mosaic, 63)

        screen = Screen()
        Bars(5, 1, minimum=0, maximum=1, gap=1).draw(
            screen, 1, 0, (1, 1)
        )
        self.assertEqual(screen.rows[1][0].mosaic, 63)
        self.assertEqual(screen.rows[1][1].mosaic, 63)
        self.assertIsNone(screen.rows[1][2].mosaic)
        self.assertEqual(screen.rows[1][3].mosaic, 63)
        self.assertEqual(screen.rows[1][4].mosaic, 63)

    def test_bar_attrs(self):
        screen = Screen()
        Bars(1, 1, minimum=0, maximum=1, fg=3).draw(
            screen, 1, 0, (1,), inverse=True
        )
        cell = screen.rows[1][0]
        self.assertEqual(cell.mosaic, 63)
        self.assertEqual(cell.fg, 3)
        self.assertTrue(cell.inverse)

    def test_validation(self):
        with self.assertRaises(ValueError):
            Bars(0, 1)
        with self.assertRaises(ValueError):
            Bars(1, 1, gap=-1)
        with self.assertRaises(ValueError):
            Bars(1, 1, minimum=1, maximum=1)
        with self.assertRaises(TypeError):
            Bars(1, 1, fg="x")
        with self.assertRaises(TypeError):
            Bars(1, 1, minimum="x")


class SparklineTests(unittest.TestCase):
    def test_line_connects_values(self):
        screen = Screen()
        Sparkline(4, 1, minimum=0, maximum=3).draw(
            screen, 1, 0, (0, 3)
        )
        self.assertEqual(screen.rows[1][0].mosaic & 0x02, 0x02)
        self.assertEqual(screen.rows[1][3].mosaic & 0x10, 0x10)

    def test_none_breaks_the_line(self):
        screen = Screen()
        Sparkline(4, 1, minimum=0, maximum=3).draw(
            screen, 1, 0, (0, None, 3)
        )
        self.assertIsNone(screen.rows[1][1].mosaic)
        self.assertEqual(screen.rows[1][0].mosaic & 0x02, 0x02)
        self.assertEqual(screen.rows[1][3].mosaic & 0x10, 0x10)

    def test_single_point(self):
        screen = Screen()
        Sparkline(4, 1).draw(screen, 1, 0, (1,))
        self.assertEqual(screen.rows[1][1].mosaic & 0x01, 0x01)

    def test_validation(self):
        with self.assertRaises(ValueError):
            Sparkline(0, 1)
        with self.assertRaises(ValueError):
            Sparkline(1, 1, minimum=2, maximum=1)
        with self.assertRaises(TypeError):
            Sparkline(1, 1, maximum="x")


if __name__ == "__main__":
    unittest.main()
