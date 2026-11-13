import importlib.util
import unittest
from pathlib import Path

from minitel import (
    FunctionPage,
    Header,
    M1,
    Page,
    Registry,
    Screen,
    Session,
    page,
)
from minitel.protocol import codec
from minitel.render.render import render


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


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def body(text="HELLO"):
    screen = Screen()
    screen.text(1, 0, text)
    return screen


def render_body(ctx):
    return body()


def tick_hello(ctx):
    return body("HELLX")


def tick_hello_paint_cell(ctx):
    screen = body("HELLX")
    screen.paint = "cell"
    return screen


def tick_hello_paint_row(ctx):
    screen = body("HELLX")
    screen.paint = "row"
    return screen


def make_session(page_obj, *, header=None, clock=None):
    registry = Registry()
    registry.add(page_obj)
    clock = clock or FakeClock()
    session = Session(
        registry,
        M1,
        initial=page_obj.number,
        fallback=page_obj,
        header=header,
        clock=clock,
        wall_clock=clock,
    )
    return session


class CellHeader(Header):
    paint = "cell"
    tick_interval = 1.0

    def render(self, ctx):
        screen = Screen()
        screen.fill(0, 0, 40, " ", inverse=True)
        screen.text(0, 0, f"H{int(ctx.now)}", inverse=True)
        return screen


class RowHeader(Header):
    tick_interval = 1.0

    def render(self, ctx):
        screen = Screen()
        screen.fill(0, 0, 40, " ", inverse=True)
        screen.text(0, 0, f"H{int(ctx.now)}", inverse=True)
        return screen


class ResultCellHeader(RowHeader):
    def render(self, ctx):
        screen = super().render(ctx)
        screen.paint = "cell"
        return screen


class ResultRowHeader(CellHeader):
    def render(self, ctx):
        screen = super().render(ctx)
        screen.paint = "row"
        return screen


class FullResultHeader(Header):
    def render(self, ctx):
        screen = Screen()
        screen.paint = "full"
        return screen


class ForceFullHeader(RowHeader):
    def render(self, ctx):
        screen = super().render(ctx)
        screen.force_full = True
        return screen


class FullHeader(Header):
    paint = "full"


class PaintModeTests(unittest.TestCase):
    def test_page_paint_validation(self):
        self.assertEqual(
            FunctionPage("810", render_body, paint="cell").paint,
            "cell",
        )
        with self.assertRaises(ValueError):
            FunctionPage("811", render_body, paint="bogus")
        with self.assertRaises(TypeError):
            FunctionPage("812", render_body, paint=1)

    def test_extension_page_copies_paint(self):
        @page("813", extensions=True, paint="cell")
        def base(ctx):
            return body()

        registry = Registry()
        registry.add(base)
        self.assertEqual(registry.get("813#ABC").paint, "cell")

    def test_page_subclass_paint_is_validated_at_render(self):
        class BadPage(Page):
            number = "814"
            paint = "bogus"

            def render(self, ctx):
                return body()

        session = make_session(BadPage())
        with self.assertRaises(ValueError):
            session.start()

    def test_header_paint_full_is_rejected(self):
        with self.assertRaises(ValueError):
            FunctionPage("815", render_body, header=FullHeader())

    def test_cell_tick_uses_cell_diff(self):
        session = make_session(
            FunctionPage(
                "820", render_body, tick_interval=1.0,
                on_tick=tick_hello, paint="cell",
            )
        )
        old = session.start()
        action = session.tick()
        self.assertIsNone(action.screen)
        self.assertNotIn(bytes([codec.CAN]), action.raw)
        self.assertEqual(
            decode(render(old) + action.raw).text(),
            session.screen.to_text(),
        )

    def test_row_tick_still_uses_row_diff(self):
        session = make_session(
            FunctionPage(
                "821", render_body, tick_interval=1.0,
                on_tick=tick_hello,
            )
        )
        old = session.start()
        action = session.tick()
        self.assertIn(bytes([codec.CAN]), action.raw)
        self.assertEqual(
            decode(render(old) + action.raw).text(),
            session.screen.to_text(),
        )

    def test_screen_paint_can_override_to_cell(self):
        session = make_session(
            FunctionPage(
                "822", render_body, tick_interval=1.0,
                on_tick=tick_hello_paint_cell,
            )
        )
        old = session.start()
        action = session.tick()
        self.assertNotIn(bytes([codec.CAN]), action.raw)
        self.assertEqual(
            decode(render(old) + action.raw).text(),
            session.screen.to_text(),
        )

    def test_screen_paint_can_override_to_row(self):
        session = make_session(
            FunctionPage(
                "823", render_body, tick_interval=1.0,
                on_tick=tick_hello_paint_row, paint="cell",
            )
        )
        old = session.start()
        action = session.tick()
        self.assertIn(bytes([codec.CAN]), action.raw)
        self.assertEqual(
            decode(render(old) + action.raw).text(),
            session.screen.to_text(),
        )

    def test_full_mode_returns_a_screen_on_tick_and_refresh(self):
        session = make_session(
            FunctionPage(
                "824", render_body, tick_interval=1.0,
                on_tick=tick_hello, paint="full",
            )
        )
        session.start()
        action = session.tick()
        self.assertIsNotNone(action.screen)
        self.assertEqual(action.raw, b"")
        action = session.refresh()
        self.assertIsNotNone(action.screen)
        self.assertEqual(action.raw, b"")

    def test_cell_header_tick_does_not_clear_row(self):
        clock = FakeClock()
        session = make_session(
            FunctionPage("830", render_body), header=CellHeader(), clock=clock
        )
        old = session.start()
        clock.advance(1.0)
        action = session.on_timeout()
        self.assertIsNone(action.screen)
        self.assertNotIn(bytes([codec.CAN]), action.raw)
        decoded = decode(render(old) + action.raw)
        self.assertEqual(decoded.text(), session.screen.to_text())
        self.assertTrue(decoded.rows[0][0].inverse)

    def test_row_header_tick_clears_row(self):
        clock = FakeClock()
        session = make_session(
            FunctionPage("831", render_body), header=RowHeader(), clock=clock
        )
        old = session.start()
        clock.advance(1.0)
        action = session.on_timeout()
        self.assertIn(bytes([codec.CAN]), action.raw)
        self.assertEqual(
            decode(render(old) + action.raw).text(),
            session.screen.to_text(),
        )

    def test_header_result_paint_overrides_class_declaration(self):
        clock = FakeClock()
        session = make_session(
            FunctionPage("832", render_body),
            header=ResultCellHeader(),
            clock=clock,
        )
        old = session.start()
        clock.advance(1.0)
        action = session.on_timeout()
        self.assertNotIn(bytes([codec.CAN]), action.raw)
        self.assertEqual(
            decode(render(old) + action.raw).text(),
            session.screen.to_text(),
        )

    def test_header_result_can_override_to_row(self):
        clock = FakeClock()
        session = make_session(
            FunctionPage("833", render_body),
            header=ResultRowHeader(),
            clock=clock,
        )
        old = session.start()
        clock.advance(1.0)
        action = session.on_timeout()
        self.assertIn(bytes([codec.CAN]), action.raw)
        self.assertEqual(
            decode(render(old) + action.raw).text(),
            session.screen.to_text(),
        )

    def test_header_result_full_is_rejected(self):
        session = make_session(
            FunctionPage("834", render_body), header=FullResultHeader()
        )
        with self.assertRaises(ValueError):
            session.start()

    def test_header_force_full_is_ignored(self):
        clock = FakeClock()
        session = make_session(
            FunctionPage("835", render_body),
            header=ForceFullHeader(),
            clock=clock,
        )
        session.start()
        clock.advance(1.0)
        action = session.on_timeout()
        self.assertIsNone(action.screen)

    def test_full_page_header_tick_full_paints(self):
        clock = FakeClock()
        session = make_session(
            FunctionPage("836", render_body, paint="full"),
            header=CellHeader(),
            clock=clock,
        )
        session.start()
        clock.advance(1.0)
        action = session.on_timeout()
        self.assertIsNotNone(action.screen)

    def test_raw_tick_forces_row_until_full_paint(self):
        def raw_then_screen(ctx):
            count = ctx.state.get("ticks", 0)
            ctx.state["ticks"] = count + 1
            if count == 0:
                return b"X"
            return body("HELLX" if count == 1 else "HELLY")

        session = make_session(
            FunctionPage(
                "840", render_body, tick_interval=1.0,
                on_tick=raw_then_screen, paint="cell",
            )
        )
        session.start()
        self.assertIsNone(session.tick().screen)
        row_diff = session.tick()
        self.assertIn(bytes([codec.CAN]), row_diff.raw)
        session.start()
        cell_diff = session.tick()
        self.assertNotIn(bytes([codec.CAN]), cell_diff.raw)


if __name__ == "__main__":
    unittest.main()
