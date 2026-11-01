import importlib.util
import unittest
from pathlib import Path

from minitel import codec


def load_client():
    path = Path(__file__).resolve().parents[1] / "tools" / "minitel_client.py"
    spec = importlib.util.spec_from_file_location("minitel_client", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


client = load_client()


class KeyEncodingTests(unittest.TestCase):
    def test_function_keys_round_trip(self):
        names = (
            "ENVOI",
            "RETOUR",
            "REPETITION",
            "GUIDE",
            "ANNULATION",
            "SOMMAIRE",
            "CORRECTION",
            "SUITE",
        )
        for name in names:
            parser = codec.InputParser()
            events = parser.feed(client.FUNCTION_BYTES[name])
            self.assertEqual(events, [codec.Function(name)])

    def test_arrow_keys_round_trip(self):
        for name, data in client.ARROW_BYTES.items():
            parser = codec.InputParser()
            events = parser.feed(data)
            self.assertEqual(events, [codec.Key(name)])

    def test_enter_and_editing_keys(self):
        self.assertEqual(client.key_to_bytes("\n"), bytes([codec.CR]))
        self.assertEqual(
            client.key_to_bytes(client.curses.KEY_BACKSPACE),
            client.FUNCTION_BYTES["CORRECTION"],
        )
        self.assertEqual(
            client.key_to_bytes("\t"), client.FUNCTION_BYTES["SUITE"]
        )
        self.assertEqual(
            client.key_to_bytes(client.curses.KEY_F1),
            client.FUNCTION_BYTES["GUIDE"],
        )

    def test_printable_text_is_uppercased_by_default(self):
        self.assertEqual(client.key_to_bytes("a"), b"A")
        self.assertEqual(client.key_to_bytes("a", uppercase=False), b"a")
        self.assertEqual(client.key_to_bytes(" "), b" ")

    def test_supported_accent_uses_codec(self):
        self.assertEqual(client.key_to_bytes("é"), codec.text("é"))

    def test_unsupported_character_is_ignored(self):
        self.assertEqual(client.key_to_bytes("\u2603"), b"")
        self.assertEqual(client.key_to_bytes(999999), b"")


class LocalEchoTests(unittest.TestCase):
    class FakeSocket:
        def __init__(self):
            self.sent = []

        def sendall(self, data):
            self.sent.append(data)

    def test_writes_at_cursor_and_advances(self):
        decoder = client.Decoder()
        decoder.feed(b"\x1f\x4a\x46")
        client.echo_to_screen(decoder.screen, "A")
        self.assertEqual(decoder.screen.rows[10][5].ch, "A")
        self.assertEqual((decoder.screen.row, decoder.screen.col), (10, 6))

    def test_uses_current_pen_attributes(self):
        decoder = client.Decoder()
        decoder.feed(b"\x1f\x45\x41\x1bA")
        client.echo_to_screen(decoder.screen, "A")
        self.assertEqual(decoder.screen.rows[5][0].fg, codec.RED)

    def test_send_key_echoes_locally_by_default(self):
        session = client.Client("example.test", 3615)
        session.decoder = client.Decoder()
        session.sock = self.FakeSocket()
        session.connected = True

        self.assertTrue(session.send_key("a"))
        self.assertEqual(session.sock.sent, [b"A"])
        self.assertEqual(session.decoder.screen.rows[1][0].ch, "A")
        self.assertEqual(session.decoder.screen.col, 1)

    def test_send_key_does_not_echo_when_disabled(self):
        session = client.Client("example.test", 3615, local_echo=False)
        session.decoder = client.Decoder()
        session.sock = self.FakeSocket()
        session.connected = True

        self.assertFalse(session.send_key("a"))
        self.assertEqual(session.sock.sent, [b"A"])
        self.assertEqual(session.decoder.screen.rows[1][0].ch, " ")


class AddressTests(unittest.TestCase):
    def test_default_port(self):
        self.assertEqual(client.parse_address("example.test"), ("example.test", 3615))

    def test_explicit_port(self):
        self.assertEqual(client.parse_address("127.0.0.1:43620"), ("127.0.0.1", 43620))


if __name__ == "__main__":
    unittest.main()
