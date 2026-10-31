import unittest

from minitel import codec
from minitel.codec import (
    Control,
    Enter,
    Function,
    Ident,
    InputParser,
    Key,
    Protocol,
    Text,
)


class PosTests(unittest.TestCase):
    def test_status_row_first_cell(self):
        self.assertEqual(codec.pos(0, 0), b"\x1f\x40\x41")

    def test_page_home_uses_rs(self):
        self.assertEqual(codec.pos(1, 0), b"\x1e")

    def test_row_five_column_ten(self):
        self.assertEqual(codec.pos(5, 9), b"\x1f\x45\x4a")

    def test_bottom_right(self):
        self.assertEqual(codec.pos(24, 39), b"\x1f\x58\x68")

    def test_out_of_range(self):
        with self.assertRaises(ValueError):
            codec.pos(-1, 0)
        with self.assertRaises(ValueError):
            codec.pos(25, 0)
        with self.assertRaises(ValueError):
            codec.pos(0, 40)


class AttributeTests(unittest.TestCase):
    def test_colours(self):
        self.assertEqual(codec.fg(0), b"\x1b\x40")
        self.assertEqual(codec.fg(7), b"\x1b\x47")
        self.assertEqual(codec.bg(0), b"\x1b\x50")
        self.assertEqual(codec.bg(7), b"\x1b\x57")

    def test_inverse(self):
        self.assertEqual(codec.inverse(), b"\x1b\x5d")
        self.assertEqual(codec.inverse(False), b"\x1b\x5c")

    def test_flash(self):
        self.assertEqual(codec.flash(), b"\x1b\x48")
        self.assertEqual(codec.flash(False), b"\x1b\x49")

    def test_underline(self):
        self.assertEqual(codec.underline(), b"\x1b\x5a")
        self.assertEqual(codec.underline(False), b"\x1b\x59")

    def test_size(self):
        self.assertEqual(codec.size(codec.NORMAL), b"\x1b\x4c")
        self.assertEqual(codec.size(codec.DOUBLE_HEIGHT), b"\x1b\x4d")
        self.assertEqual(codec.size(codec.DOUBLE_WIDTH), b"\x1b\x4e")
        self.assertEqual(codec.size(codec.DOUBLE_SIZE), b"\x1b\x4f")


class TextTests(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(codec.text("HELLO"), b"HELLO")

    def test_accents(self):
        self.assertEqual(codec.text("é"), b"\x19\x42\x65")
        self.assertEqual(codec.text("ç"), b"\x19\x4b\x63")
        self.assertEqual(codec.text("ù"), b"\x19\x41\x75")
        self.assertEqual(codec.text("û"), b"\x19\x43\x75")

    def test_specials(self):
        self.assertEqual(codec.text("°"), b"\x19\x30")
        self.assertEqual(codec.text("£"), b"\x19\x23")
        self.assertEqual(codec.text("Œ"), b"\x19\x6a")

    def test_unsupported(self):
        with self.assertRaises(ValueError):
            codec.text("\u2603")

    def test_seven_bit(self):
        data = codec.text("HELLO é ç ° £")
        self.assertTrue(all(b <= 0x7F for b in data))


class RepeatTests(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(codec.repeat("=", 0), b"")

    def test_one(self):
        self.assertEqual(codec.repeat("=", 1), b"=")

    def test_forty(self):
        self.assertEqual(codec.repeat("=", 40), b"=\x12\x67")

    def test_sixty_four(self):
        self.assertEqual(codec.repeat("=", 64), b"=\x12\x7f")

    def test_sixty_five(self):
        self.assertEqual(codec.repeat("=", 65), b"=\x12\x7f\x12\x41")

    def test_accented_repeat(self):
        self.assertEqual(codec.repeat("é", 2), b"\x19\x42\x65\x12\x41")


class MiscEncoderTests(unittest.TestCase):
    def test_clear_and_cursor(self):
        self.assertEqual(codec.clear(), b"\x0c")
        self.assertEqual(codec.cursor(), b"\x11")
        self.assertEqual(codec.cursor(False), b"\x14")

    def test_mosaic(self):
        self.assertEqual(codec.mosaic(0x3F), b"\x0e\x3f\x0f")


class InputParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = InputParser()

    def test_text(self):
        self.assertEqual(
            self.parser.feed(b"HELLO"),
            [Text("H"), Text("E"), Text("L"), Text("L"), Text("O")],
        )

    def test_enter(self):
        self.assertEqual(self.parser.feed(b"\r"), [Enter()])

    def test_function_key(self):
        self.assertEqual(self.parser.feed(b"\x13A"), [Function("ENVOI")])
        self.assertEqual(self.parser.feed(b"\x13G"), [Function("CORRECTION")])

    def test_function_key_split(self):
        self.assertEqual(self.parser.feed(b"\x13"), [])
        self.assertEqual(self.parser.feed(b"A"), [Function("ENVOI")])

    def test_arrow(self):
        self.assertEqual(self.parser.feed(b"\x1b[A"), [Key("up")])
        self.assertEqual(self.parser.feed(b"\x1b[B"), [Key("down")])

    def test_arrow_split(self):
        self.assertEqual(self.parser.feed(b"\x1b["), [])
        self.assertEqual(self.parser.feed(b"A"), [Key("up")])

    def test_ctrl_enter(self):
        self.assertEqual(self.parser.feed(b"\x1b[2J"), [Key("ctrl_enter")])

    def test_shift_enter(self):
        self.assertEqual(self.parser.feed(b"\x1b[H"), [Key("shift_enter")])

    def test_protocol_frame(self):
        event = self.parser.feed(b"\x1b\x3a\x75\x64")[0]
        self.assertIsInstance(event, Protocol)
        self.assertEqual(event.kind, "PRO2")
        self.assertEqual(event.data, b"\x1b\x3a\x75\x64")

    def test_protocol_split(self):
        self.assertEqual(self.parser.feed(b"\x1b\x3a"), [])
        event = self.parser.feed(b"\x75\x64")[0]
        self.assertEqual(event.kind, "PRO2")

    def test_ident(self):
        event = self.parser.feed(b"\x01\x43\x76\x01\x04")[0]
        self.assertEqual(event, Ident(b"\x01\x43\x76\x01\x04"))

    def test_ss2_accent(self):
        self.assertEqual(self.parser.feed(b"\x19\x42\x65"), [Text("é")])

    def test_ss2_special(self):
        self.assertEqual(self.parser.feed(b"\x19\x30"), [Text("°")])

    def test_ss2_split(self):
        self.assertEqual(self.parser.feed(b"\x19\x42"), [])
        self.assertEqual(self.parser.feed(b"e"), [Text("é")])

    def test_control(self):
        self.assertEqual(self.parser.feed(b"\x12"), [Control(0x12)])


if __name__ == "__main__":
    unittest.main()
