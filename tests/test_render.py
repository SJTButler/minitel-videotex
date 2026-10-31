import importlib.util
import unittest
from pathlib import Path

from minitel import codec
from minitel.render import render
from minitel.screen import Screen


def load_virtual_minitel():
    path = Path(__file__).resolve().parents[1] / "tools" / "virtual_minitel.py"
    spec = importlib.util.spec_from_file_location("virtual_minitel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VM = load_virtual_minitel()


def decode(data):
    decoder = VM.Decoder()
    decoder.feed(data)
    return decoder.screen


class RenderTests(unittest.TestCase):
    def test_blank_page(self):
        data = render(Screen())
        self.assertTrue(all(b <= 0x7F for b in data))
        self.assertLess(len(data), 40)
        decoded = decode(data)
        self.assertEqual(decoded.text(), "\n".join([" " * codec.COLS] * codec.ROWS))
        self.assertEqual((decoded.row, decoded.col), (1, 0))

    def test_page_roundtrip(self):
        s = Screen()
        s.fill(0, 0, 40, " ", inverse=True)
        s.text(0, 0, "STATUS", inverse=True)
        s.text(1, 0, "HELLO", inverse=True, size=codec.DOUBLE_WIDTH)
        s.text(3, 0, "FIRST LIGHT")
        s.rule(5, 0, 40, "=")
        s.text(7, 0, "ACCENTS: é ç")
        s.field(10, 0, 20)

        data = render(s)
        self.assertTrue(all(b <= 0x7F for b in data))
        self.assertLess(len(data), 300)

        decoded = decode(data)
        grid = decoded.text().splitlines()
        self.assertTrue(grid[0].startswith("STATUS"))
        self.assertTrue(grid[1].startswith("HELLO"))
        self.assertTrue(grid[3].startswith("FIRST LIGHT"))
        self.assertEqual(grid[5], "=" * 40)
        self.assertTrue(grid[7].startswith("ACCENTS: é ç"))
        self.assertTrue(decoded.rows[10][0].inverse)
        self.assertTrue(decoded.cursor)
        self.assertEqual((decoded.row, decoded.col), (10, 0))

    def test_field_cursor(self):
        s = Screen()
        s.field(12, 5, 20)
        decoded = decode(render(s))
        self.assertEqual((decoded.row, decoded.col), (12, 5))
        self.assertTrue(all(decoded.rows[12][c].inverse for c in range(5, 25)))

    def test_attributes(self):
        s = Screen()
        s.text(2, 0, "COLOUR", fg=codec.RED, bg=codec.BLUE,
               underline=True, flash=True)
        decoded = decode(render(s))
        cell = decoded.rows[2][0]
        self.assertEqual(cell.fg, codec.RED)
        self.assertEqual(cell.bg, codec.BLUE)
        self.assertTrue(cell.underline)
        self.assertTrue(cell.flash)

    def test_double_width_marker(self):
        s = Screen()
        s.text(1, 0, "BIG", size=codec.DOUBLE_WIDTH)
        decoded = decode(render(s))
        self.assertTrue(all(decoded.rows[1][i].size == codec.DOUBLE_WIDTH for i in range(3)))

    def test_repeat_rule_is_compact(self):
        s = Screen()
        s.rule(5, 0, 40, "=")
        data = render(s)
        self.assertIn(b"\x12\x67", data)


if __name__ == "__main__":
    unittest.main()
