import unittest
from pathlib import Path

from minitel.pages import LINE_FIELD, Registry, page
from minitel.profiles import M1
from minitel.screen import Screen
from minitel.session import Session

ENVOI = bytes([0x13, 0x41])


class InputHelperTests(unittest.TestCase):
    def test_set_input_uses_the_named_line_field(self):
        @page("960")
        def typed(ctx):
            ctx.set_input(1, 0, 5)
            return Screen()

        registry = Registry()
        registry.add(typed)
        session = Session(registry, M1, initial="960", fallback=typed)
        session.start()

        self.assertEqual([field.name for field in session.fields], [LINE_FIELD])

    def test_input_value_and_clear_input(self):
        def submit(ctx, line):
            self.assertEqual(ctx.input_value.strip(), "AB")
            ctx.clear_input()
            return "961"

        @page("961", on_submit=submit)
        def typed(ctx):
            s = Screen()
            s.text(0, 0, ctx.input_value)
            ctx.set_input(1, 0, 5)
            return s

        registry = Registry()
        registry.add(typed)
        session = Session(registry, M1, initial="961", fallback=typed)
        session.start()
        session.feed(b"AB")
        self.assertEqual(session.values[LINE_FIELD], "AB")

        session.feed(ENVOI)
        self.assertEqual(session.values[LINE_FIELD], "")
        self.assertEqual(session.screen.rows[0][0].ch, " ")

    def test_pages_do_not_use_the_magic_input_key(self):
        pages_root = Path(__file__).resolve().parents[1] / "pages"
        for path in pages_root.rglob("*.py"):
            self.assertNotIn('values["input"]', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
