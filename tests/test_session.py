import unittest

import pages

from minitel import Registry, Screen, codec, page, profiles
from minitel.session import Session

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SOMMAIRE = bytes([0x13, 0x46])
CORRECTION = bytes([0x13, 0x47])
ANNULATION = bytes([0x13, 0x45])


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.registry = pages.build_registry()
        self.session = Session(
            self.registry,
            profiles.M1,
            initial=pages.INITIAL,
            fallback=self.registry.get(pages.NOT_FOUND),
            guide=pages.GUIDE,
        )
        self.session.start()

    def feed(self, data):
        return self.session.feed(data)

    def test_start(self):
        screen = self.session.start()
        self.assertEqual(self.session.current.number, "100")
        self.assertEqual((screen.cursor_row, screen.cursor_col), (20, 6))

    def test_text_and_submit(self):
        self.feed(b"1")
        self.assertEqual(self.session.line, "1")
        actions = self.feed(ENVOI)
        self.assertEqual(self.session.current.number, "110")
        self.assertIsNotNone(actions[0].screen)
        self.assertEqual(self.session.line, "")

    def test_history(self):
        self.feed(b"1" + ENVOI)
        self.feed(b"2" + ENVOI)
        self.assertEqual(self.session.current.number, "120")
        self.feed(RETOUR)
        self.assertEqual(self.session.current.number, "110")
        self.feed(RETOUR)
        self.assertEqual(self.session.current.number, "100")

    def test_sommaire_clears_history(self):
        self.feed(b"1" + ENVOI)
        self.feed(SOMMAIRE)
        self.assertEqual(self.session.current.number, "100")
        self.feed(RETOUR)
        self.assertEqual(self.session.current.number, "100")

    def test_not_found(self):
        self.feed(b"9" + ENVOI)
        self.assertEqual(self.session.current.number, pages.NOT_FOUND)
        self.assertEqual(self.session.last_key, "9")

    def test_correction(self):
        self.feed(b"12")
        actions = self.feed(CORRECTION)
        self.assertEqual(self.session.line, "1")
        self.assertEqual(actions[0].raw, bytes([codec.BS, 0x20, codec.BS]))

    def test_annulation(self):
        self.feed(b"12")
        actions = self.feed(ANNULATION)
        self.assertEqual(self.session.line, "")
        self.assertIsNotNone(actions[0].screen)

    def test_input_overflow(self):
        for ch in b"1234567890":
            self.feed(bytes([ch]))
        actions = self.feed(b"1")
        self.assertEqual(actions[0].raw, bytes([codec.BEL]))
        self.assertEqual(len(self.session.line), 10)

    def test_echo_flag(self):
        session = Session(
            self.registry,
            profiles.M1,
            initial=pages.INITIAL,
            fallback=self.registry.get(pages.NOT_FOUND),
            echo=True,
        )
        session.start()
        actions = session.feed(b"1")
        self.assertEqual(actions[0].raw, b"1")

    def test_guide(self):
        self.feed(bytes([0x13, 0x44]))
        self.assertEqual(self.session.current.number, "130")
        self.feed(RETOUR)
        self.assertEqual(self.session.current.number, "100")

    def test_on_submit_hook_and_state(self):
        registry = Registry()

        def submit(ctx, line):
            ctx.state["echo"] = line
            return "300"

        @page("300", title="ECHO", on_submit=submit)
        def echo(ctx):
            s = Screen()
            s.text(0, 0, ctx.state.get("echo", ""))
            ctx.set_input(1, 0, 10)
            return s

        registry.add(echo)
        session = Session(registry, profiles.M1, initial="300", fallback=echo)
        session.start()
        actions = session.feed(b"HI" + ENVOI)
        self.assertEqual(session.state["echo"], "HI")
        self.assertIs(session.current, echo)
        self.assertIsNotNone(actions[-1].screen)
        self.assertEqual(actions[-1].screen.rows[0][0].ch, "H")


if __name__ == "__main__":
    unittest.main()
