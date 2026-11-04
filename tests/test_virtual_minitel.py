import importlib.util
import unittest
from pathlib import Path


def load_virtual_minitel():
    path = Path(__file__).resolve().parents[1] / "tools" / "virtual_minitel.py"
    spec = importlib.util.spec_from_file_location("virtual_minitel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VM = load_virtual_minitel()


class DecoderTests(unittest.TestCase):
    def decode(self, data):
        decoder = VM.Decoder()
        decoder.feed(data)
        return decoder

    def test_backspace_overwrites_previous_cell(self):
        decoder = self.decode(b"AB\x08C")
        self.assertEqual(decoder.screen.text().splitlines()[1][:3], "AC ")
        self.assertEqual((decoder.screen.row, decoder.screen.col), (1, 2))

    def test_backspace_stops_at_column_zero(self):
        decoder = self.decode(b"\x08\x08A")
        self.assertEqual(decoder.screen.text().splitlines()[1][0], "A")
        self.assertEqual(decoder.screen.text().splitlines()[0][0], " ")

    def test_clear_to_end_of_row_keeps_text_before_cursor(self):
        decoder = self.decode(b"AB\x18")
        self.assertEqual(decoder.screen.text().splitlines()[1], "AB" + " " * 38)

    def test_split_escape_attribute(self):
        decoder = VM.Decoder()
        decoder.feed(b"\x1b")
        decoder.feed(b"A")
        decoder.feed(b"X")
        self.assertEqual(decoder.screen.rows[1][0].ch, "X")
        self.assertEqual(decoder.screen.rows[1][0].fg, 1)

    def test_us_position_resets_pen_attributes(self):
        decoder = self.decode(b"\x1bA\x1f\x45\x41X")
        self.assertEqual(decoder.screen.rows[5][0].ch, "X")
        self.assertEqual(decoder.screen.rows[5][0].fg, 7)

    def test_rs_home_resets_pen_attributes(self):
        decoder = self.decode(b"\x1bA\x1eX")
        self.assertEqual(decoder.screen.rows[1][0].ch, "X")
        self.assertEqual(decoder.screen.rows[1][0].fg, 7)

    def test_split_ss2_accent(self):
        decoder = VM.Decoder()
        decoder.feed(b"\x19\x42")
        decoder.feed(b"e")
        self.assertEqual(decoder.screen.rows[1][0].ch, "é")

    def test_split_repeat(self):
        decoder = VM.Decoder()
        decoder.feed(b"=")
        decoder.feed(b"\x12")
        decoder.feed(b"\x43")
        self.assertEqual(decoder.screen.text().splitlines()[1][:4], "====")

    def test_protocol_frame_is_not_displayed(self):
        decoder = self.decode(b"\x01ABC\x04HI")
        self.assertEqual(decoder.screen.text().splitlines()[1][:2], "HI")

    def test_every_byte_is_consumed_without_crashing(self):
        decoder = self.decode(bytes(range(256)))
        self.assertEqual(len(decoder.screen.rows), VM.ROWS)

    def pos(self, row, col=0):
        return bytes([0x1F, 0x40 + row, 0x41 + col])

    def numbered_rows(self):
        decoder = self.decode(self.pos(0) + b"STATUS")
        for row in range(1, VM.ROWS):
            decoder.feed(self.pos(row) + str(row).encode())
        return decoder

    def test_scroll_mode_command_sets_the_mode(self):
        decoder = VM.Decoder()
        decoder.feed(b"\x1b:\x69C")
        self.assertTrue(decoder.screen.scroll_mode)
        decoder.feed(b"\x1b:\x6aC")
        self.assertFalse(decoder.screen.scroll_mode)

    def test_line_feed_at_bottom_scrolls_rows_one_to_24(self):
        decoder = self.numbered_rows()
        decoder.feed(b"\x1b:\x69C")
        decoder.feed(self.pos(24) + b"\x0a")
        lines = decoder.screen.text().splitlines()
        self.assertTrue(lines[0].startswith("STATUS"))
        self.assertEqual(lines[1].strip(), "2")
        self.assertEqual(lines[23].strip(), "24")
        self.assertEqual(lines[24].strip(), "")

    def test_vertical_tab_at_top_scrolls_rows_one_to_24_down(self):
        decoder = self.numbered_rows()
        decoder.feed(b"\x1b:\x69C")
        decoder.feed(self.pos(1) + b"\x0b")
        lines = decoder.screen.text().splitlines()
        self.assertTrue(lines[0].startswith("STATUS"))
        self.assertEqual(lines[1].strip(), "")
        self.assertEqual(lines[2].strip(), "1")
        self.assertEqual(lines[24].strip(), "23")

    def test_page_mode_line_feed_wraps_to_row_one(self):
        decoder = self.numbered_rows()
        decoder.feed(self.pos(24) + b"\x0a")
        self.assertEqual(decoder.screen.row, 1)
        self.assertEqual(
            decoder.screen.text().splitlines()[24].strip(), "24"
        )

    def test_page_mode_vertical_tab_wraps_to_row_24(self):
        decoder = self.numbered_rows()
        decoder.feed(self.pos(1) + b"\x0b")
        self.assertEqual(decoder.screen.row, VM.ROWS - 1)


if __name__ == "__main__":
    unittest.main()
