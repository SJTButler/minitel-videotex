import unittest

from minitel.pagemodel import LINE_FIELD, Registry, page
from minitel.protocol import codec
from minitel.render import Screen, reset
from minitel.session import Session
from minitel.terminal.profiles import M1

SUITE = bytes([0x13, 0x48])


def make_session(page_object):
    registry = Registry()
    registry.add(page_object)
    session = Session(
        registry, M1, initial=page_object.number, fallback=page_object
    )
    session.start()
    return session


class LiveFieldTests(unittest.TestCase):
    def test_visible_live_field_rerenders_the_page_on_text(self):
        renders = []

        @page("980")
        def paged(ctx):
            renders.append(ctx.input_value)
            screen = Screen()
            screen.text(0, 0, ctx.input_value)
            ctx.set_input(1, 0, 10, live=True)
            return screen

        session = make_session(paged)
        self.assertEqual(renders, [""])
        session.feed(b"A")
        self.assertEqual(session.values[LINE_FIELD], "A")
        self.assertEqual(renders, ["", "A"])
        self.assertEqual(session.screen.rows[0][0].ch, "A")
        self.assertTrue(session.screen.cursor_visible)
        self.assertEqual(session.screen.cursor_row, 1)
        self.assertEqual(session.screen.cursor_col, 1)

    def test_hidden_live_field_captures_text_without_echo_or_cursor(self):
        renders = []

        @page("981")
        def paged(ctx):
            renders.append(ctx.input_value)
            ctx.set_input(0, 0, 10, live=True, visible=False)
            return Screen()

        session = make_session(paged)
        actions = session.feed(b"B")
        self.assertEqual(session.values[LINE_FIELD], "B")
        self.assertEqual(renders, ["", "B"])
        self.assertEqual(actions[0].raw, b"")
        self.assertEqual(session.screen.rows[0][0].ch, " ")
        self.assertFalse(session.screen.cursor_visible)
        self.assertEqual(session.screen.cursor_row, codec.ROWS - 1)

    def test_live_field_correction_and_annulation_rerender(self):
        renders = []

        @page("982")
        def paged(ctx):
            renders.append(ctx.input_value)
            screen = Screen()
            screen.text(0, 0, ctx.input_value)
            ctx.set_input(1, 0, 10, live=True)
            return screen

        session = make_session(paged)
        session.feed(b"AB")
        session.function("CORRECTION")
        self.assertEqual(session.values[LINE_FIELD], "A")
        self.assertEqual(session.screen.rows[0][0].ch, "A")
        session.function("ANNULATION")
        self.assertEqual(session.values[LINE_FIELD], "")
        self.assertEqual(session.screen.rows[0][0].ch, " ")
        self.assertEqual(renders, ["", "A", "AB", "A", ""])

    def test_live_field_survives_viewport_movement(self):
        @page("983", scroll=True)
        def paged(ctx):
            screen = Screen()
            screen.text(0, 0, ctx.input_value)
            ctx.set_input(0, 0, 10, live=True, visible=False)
            ctx.set_viewport(20, 5)
            return screen

        session = make_session(paged)
        session.feed(b"A")
        session.feed(SUITE)
        self.assertEqual(session.values[LINE_FIELD], "A")
        self.assertEqual(session.screen.rows[0][0].ch, "A")

    def test_normal_field_still_clears_on_viewport_movement(self):
        @page("984", scroll=True)
        def paged(ctx):
            screen = Screen()
            screen.text(0, 0, ctx.input_value)
            ctx.set_input(0, 0, 10)
            ctx.set_viewport(20, 5)
            return screen

        session = make_session(paged)
        session.feed(b"A")
        session.feed(SUITE)
        self.assertEqual(session.values[LINE_FIELD], "")

    def test_hidden_live_field_tick_frame_hides_cursor(self):
        @page("985", tick_interval=1.0, on_tick=lambda ctx: b"X")
        def paged(ctx):
            ctx.set_input(0, 0, 10, live=True, visible=False)
            return Screen()

        session = make_session(paged)
        action = session.tick()
        self.assertEqual(
            action.raw,
            reset() + b"X" + codec.cursor(False),
        )


if __name__ == "__main__":
    unittest.main()
