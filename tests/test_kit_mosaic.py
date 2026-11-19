import unittest

from minitel import Screen
from minitel_kit import MosaicCanvas


class MosaicCanvasTests(unittest.TestCase):
    def test_size_validation(self):
        with self.assertRaises(ValueError):
            MosaicCanvas(0, 1)
        with self.assertRaises(ValueError):
            MosaicCanvas(1, 0)
        with self.assertRaises(TypeError):
            MosaicCanvas("1", 1)

    def test_set_get_and_clip(self):
        canvas = MosaicCanvas(2, 2)
        canvas.set(0, 0)
        self.assertTrue(canvas.get(0, 0))
        canvas.set(-1, 0)
        canvas.set(4, 0)
        canvas.set(0, 6)
        self.assertEqual(len(canvas.pixels), 1)
        canvas.set(0, 0, on=False)
        self.assertFalse(canvas.get(0, 0))

    def test_pattern_bits(self):
        canvas = MosaicCanvas(1, 1)
        canvas.set(0, 0)
        self.assertEqual(canvas.pattern(0, 0), 32)
        canvas.set(1, 0)
        self.assertEqual(canvas.pattern(0, 0), 48)
        canvas.set(0, 1)
        canvas.set(1, 1)
        canvas.set(0, 2)
        canvas.set(1, 2)
        self.assertEqual(canvas.pattern(0, 0), 63)

    def test_pattern_bounds(self):
        canvas = MosaicCanvas(1, 1)
        with self.assertRaises(ValueError):
            canvas.pattern(1, 0)
        with self.assertRaises(ValueError):
            canvas.pattern(0, 1)

    def test_line_and_fill(self):
        canvas = MosaicCanvas(2, 1)
        canvas.line(0, 0, 3, 0)
        self.assertEqual(len(canvas.pixels), 4)
        canvas.clear()
        canvas.fill(0, 0, 1, 1)
        self.assertEqual(len(canvas.pixels), 4)

    def test_rect_outline_and_filled(self):
        canvas = MosaicCanvas(3, 3)
        canvas.rect(0, 0, 5, 8)
        self.assertIn((0, 0), canvas.pixels)
        self.assertIn((5, 8), canvas.pixels)
        self.assertNotIn((2, 2), canvas.pixels)
        canvas.clear()
        canvas.rect(0, 0, 5, 8, filled=True)
        self.assertIn((2, 2), canvas.pixels)
        self.assertEqual(len(canvas.pixels), 54)

    def test_ellipse_outline_and_filled(self):
        canvas = MosaicCanvas(4, 4)
        canvas.ellipse(0, 0, 7, 11)
        self.assertTrue(canvas.get(0, 5) or canvas.get(1, 5))
        self.assertNotIn((3, 5), canvas.pixels)
        for y in range(12):
            self.assertTrue(
                any(py == y for _px, py in canvas.pixels),
                f"outline has no pixel on row {y}",
            )
        canvas.clear()
        canvas.ellipse(0, 0, 7, 11, filled=True)
        self.assertIn((3, 5), canvas.pixels)
        self.assertNotIn((0, 0), canvas.pixels)

    def test_draw_writes_mosaic_cells(self):
        canvas = MosaicCanvas(2, 1)
        canvas.set(0, 0)
        canvas.set(2, 2)
        screen = Screen()
        canvas.draw(screen, 1, 2)
        self.assertEqual(screen.rows[1][2].mosaic, 32)
        self.assertEqual(screen.rows[1][3].mosaic, 2)
        self.assertEqual(screen.rows[1][2].ch, " ")

    def test_draw_skips_blank_unless_asked(self):
        canvas = MosaicCanvas(1, 1)
        screen = Screen()
        screen.text(1, 1, "A")
        canvas.draw(screen, 1, 1)
        self.assertEqual(screen.rows[1][1].ch, "A")
        self.assertIsNone(screen.rows[1][1].mosaic)
        canvas.draw(screen, 1, 1, include_blank=True)
        self.assertEqual(screen.rows[1][1].mosaic, 0)

    def test_draw_attrs_and_screen_clip(self):
        canvas = MosaicCanvas(2, 2)
        canvas.set(0, 0)
        screen = Screen()
        canvas.draw(screen, 24, 39, inverse=True)
        self.assertTrue(screen.rows[24][39].inverse)
        self.assertEqual(screen.rows[24][39].mosaic, 32)

    def test_draw_clips_beyond_the_screen(self):
        canvas = MosaicCanvas(2, 2)
        canvas.set(0, 0)
        canvas.set(2, 3)
        screen = Screen()
        canvas.draw(screen, 24, 39)
        self.assertEqual(screen.rows[24][39].mosaic, 32)


if __name__ == "__main__":
    unittest.main()
