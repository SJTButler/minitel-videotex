import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

import minitel
from minitel.protocol import codec
from minitel.render.render import cell_diff_row_bytes, render, render_diff
from minitel.render import Cell, Screen
from minitel.render.screen import validate_paint


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


def apply_diff(old_screen, diff):
    return decode(render(old_screen) + diff)


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
        self.assertTrue(decoded.rows[1][0].inverse)
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

    def test_paint_order_defaults_down(self):
        with patch("minitel.render.render.paint_runs") as paint:
            render(Screen())
        rows = [call.args[1] for call in paint.call_args_list]
        self.assertEqual(rows, list(range(codec.ROWS)))

    def test_paint_order_up_paints_bottom_first(self):
        screen = Screen()
        screen.paint_order = "up"
        with patch("minitel.render.render.paint_runs") as paint:
            render(screen)
        rows = [call.args[1] for call in paint.call_args_list]
        self.assertEqual(rows, [0] + list(range(codec.ROWS - 1, 0, -1)))

    def test_double_width_marker(self):
        s = Screen()
        s.text(1, 0, "BIG", size=codec.DOUBLE_WIDTH)
        decoded = decode(render(s))
        self.assertTrue(all(decoded.rows[1][i].size == codec.DOUBLE_WIDTH for i in range(3)))

    def test_inverse_after_full_inverse_row_is_reasserted(self):
        s = Screen()
        s.fill(0, 0, 40, " ", inverse=True)
        s.text(0, 0, "STATUS", inverse=True)
        s.text(1, 0, "TITLE", inverse=True)

        decoded = decode(render(s))
        self.assertTrue(all(decoded.rows[1][i].inverse for i in range(5)))

    def test_repeat_rule_is_compact(self):
        s = Screen()
        s.rule(5, 0, 40, "=")
        data = render(s)
        self.assertIn(b"\x12\x67", data)


class DiffTests(unittest.TestCase):
    def test_identical_screens(self):
        s = Screen()
        s.text(3, 0, "HELLO")
        self.assertEqual(render_diff(s, s), b"")

    def test_changed_cell(self):
        old = Screen()
        old.text(3, 0, "HELLO")
        new = Screen()
        new.text(3, 0, "HELLX")

        diff = render_diff(old, new)
        self.assertTrue(diff)
        decoded = apply_diff(old, diff)
        self.assertEqual(decoded.text(), new.to_text())

    def test_changed_attributes(self):
        old = Screen()
        old.text(3, 0, "HELLO")
        new = Screen()
        new.text(3, 0, "HELLO", inverse=True)

        decoded = apply_diff(old, render_diff(old, new))
        self.assertTrue(all(decoded.rows[3][c].inverse for c in range(5)))

    def test_clears_removed_content(self):
        old = Screen()
        old.text(3, 0, "HELLO")
        new = Screen()

        decoded = apply_diff(old, render_diff(old, new))
        self.assertEqual(decoded.text(), new.to_text())

    def test_cursor_only_change(self):
        old = Screen()
        new = Screen()
        new.set_cursor(10, 5, True)

        diff = render_diff(old, new)
        self.assertTrue(diff)
        decoded = apply_diff(old, diff)
        self.assertEqual((decoded.row, decoded.col), (10, 5))

    def test_diff_resets_attributes_left_by_previous_paint(self):
        old = Screen()
        old.fill(9, 0, 40, " ", inverse=True)
        old.text(9, 0, "TOP COMMENT", inverse=True)
        old.field(20, 6, 10)

        new = Screen()
        new.fill(9, 0, 40, " ", inverse=True)
        new.text(9, 0, "TOP COMMENT", inverse=True)
        new.field(20, 6, 10)
        new.text(10, 0, "COMMENT BODY")

        decoded = apply_diff(old, render_diff(old, new))
        self.assertTrue(decoded.text().splitlines()[10].startswith("COMMENT BODY"))
        self.assertFalse(any(cell.inverse for cell in decoded.rows[10]))

    def test_diff_moves_underline_without_stale_cells(self):
        old = Screen()
        old.text(5, 0, "ONE LINK TWO")
        old.text(5, 4, "LINK", underline=True)

        new = Screen()
        new.text(5, 0, "ONE LINK TWO")
        new.text(5, 9, "TWO", underline=True)

        decoded = apply_diff(old, render_diff(old, new))
        self.assertFalse(
            any(decoded.rows[5][col].underline for col in range(4, 8))
        )
        self.assertTrue(
            all(decoded.rows[5][col].underline for col in range(9, 12))
        )
        self.assertFalse(
            any(
                cell.underline for cell in decoded.rows[5]
                if cell.ch == " "
            )
        )

    def test_full_paint_closes_underline_before_following_text(self):
        screen = Screen()
        screen.text(5, 0, "ONE LINK TWO")
        screen.text(5, 4, "LINK", underline=True)

        data = render(screen)
        on = data.find(codec.underline(True))
        off = data.find(codec.underline(False), on + 1)
        self.assertGreaterEqual(on, 0)
        self.assertGreater(off, on)
        self.assertGreater(data.find(b"TWO"), off)

    def test_diff_closes_underline_before_following_text(self):
        old = Screen()
        old.text(5, 0, "ONE LINK TWO")
        new = Screen()
        new.text(5, 0, "ONE LINK TWO")
        new.text(5, 4, "LINK", underline=True)

        data = render_diff(old, new)
        on = data.find(codec.underline(True))
        off = data.find(codec.underline(False), on + 1)
        self.assertGreaterEqual(on, 0)
        self.assertGreater(off, on)
        self.assertGreater(data.find(b"TWO"), off)

    def test_diff_is_smaller_than_full_page(self):
        old = Screen()
        old.fill(22, 0, 40, " ", inverse=True)
        old.text(22, 0, "OLD FOOTER", inverse=True)
        new = Screen()
        new.fill(22, 0, 40, " ", inverse=True)
        new.text(22, 0, "NEW FOOTER", inverse=True)

        diff = render_diff(old, new)
        self.assertLess(len(diff), len(render(new)))

    def test_status_row_diff(self):
        old = Screen()
        old.fill(0, 0, 40, " ", inverse=True)
        old.text(0, 0, "PAGE 100", inverse=True)
        new = Screen()
        new.fill(0, 0, 40, " ", inverse=True)
        new.text(0, 0, "PAGE 110", inverse=True)

        decoded = apply_diff(old, render_diff(old, new))
        self.assertTrue(decoded.text().splitlines()[0].startswith("PAGE 110"))


class CellDiffTests(unittest.TestCase):
    def test_one_changed_cell_emits_only_that_run(self):
        old = Screen()
        old.text(3, 0, "HELLO")
        new = Screen()
        new.text(3, 0, "HELLX")

        diff = render_diff(old, new, paint="cell")
        self.assertNotIn(bytes([codec.CAN]), diff)
        self.assertIn(codec.pos(3, 4) + b"X", diff)
        self.assertNotIn(b"HELL", diff)
        self.assertEqual(apply_diff(old, diff).text(), new.to_text())

    def test_status_digit_preserves_inverse_row(self):
        old = Screen()
        old.fill(0, 0, 40, " ", inverse=True)
        old.text(0, 0, "PAGE 100", inverse=True)
        new = Screen()
        new.fill(0, 0, 40, " ", inverse=True)
        new.text(0, 0, "PAGE 110", inverse=True)

        diff = render_diff(old, new, paint="cell")
        self.assertNotIn(bytes([codec.CAN]), diff)
        decoded = apply_diff(old, diff)
        self.assertTrue(decoded.text().splitlines()[0].startswith("PAGE 110"))
        self.assertTrue(all(cell.inverse for cell in decoded.rows[0]))

    def test_attribute_only_change_is_emitted(self):
        old = Screen()
        old.text(3, 0, "A")
        new = Screen()
        new.text(3, 0, "A", inverse=True)

        diff = render_diff(old, new, paint="cell")
        self.assertIn(codec.inverse(True), diff)
        self.assertIn(b"A", diff)
        decoded = apply_diff(old, diff)
        self.assertTrue(decoded.rows[3][0].inverse)
        self.assertEqual(decoded.rows[3][0].ch, "A")

    def test_trailing_clear_uses_can(self):
        old = Screen()
        old.text(3, 0, "HELLO")
        new = Screen()

        diff = render_diff(old, new, paint="cell")
        self.assertIn(bytes([codec.CAN]), diff)
        self.assertNotIn(b"HELLO", diff)
        self.assertEqual(apply_diff(old, diff).text(), new.to_text())

    def test_clear_after_inverse_run_uses_default_pen(self):
        old = Screen()
        old.fill(3, 0, 40, " ", inverse=True)
        old.text(3, 0, "PAGE 100", inverse=True)
        new = Screen()
        new.fill(3, 0, 6, " ", inverse=True)
        new.text(3, 0, "PAGE 1", inverse=True)

        diff = render_diff(old, new, paint="cell")
        self.assertIn(bytes([codec.CAN]), diff)
        decoded = apply_diff(old, diff)
        self.assertEqual(decoded.text().splitlines()[3][:8], "PAGE 1  ")
        self.assertFalse(any(cell.inverse for cell in decoded.rows[3][6:]))

    def test_non_default_tail_does_not_use_can(self):
        old = Screen()
        old.fill(3, 0, 40, " ", inverse=True)
        old.text(3, 0, "AAAAA", inverse=True)
        new = Screen()
        new.fill(3, 0, 40, " ", inverse=True)
        new.text(3, 0, "AAA", inverse=True)

        diff = render_diff(old, new, paint="cell")
        self.assertNotIn(bytes([codec.CAN]), diff)
        decoded = apply_diff(old, diff)
        self.assertEqual(decoded.text().splitlines()[3][:5], "AAA  ")
        self.assertTrue(all(cell.inverse for cell in decoded.rows[3]))

    def test_adjacent_only_runs(self):
        old = Screen()
        old.text(3, 0, "AAAAA")
        new = Screen()
        new.text(3, 0, "ABABA")

        diff = render_diff(old, new, paint="cell")
        self.assertIn(codec.pos(3, 1), diff)
        self.assertIn(codec.pos(3, 3), diff)
        self.assertNotIn(codec.pos(3, 2), diff)
        self.assertEqual(apply_diff(old, diff).text(), new.to_text())

    def test_identical_screens(self):
        screen = Screen()
        screen.text(3, 0, "HELLO")
        self.assertEqual(render_diff(screen, screen, paint="cell"), b"")

    def test_cursor_only_change(self):
        old = Screen()
        new = Screen()
        new.set_cursor(10, 5, True)

        diff = render_diff(old, new, paint="cell")
        self.assertNotIn(bytes([codec.CAN]), diff)
        decoded = apply_diff(old, diff)
        self.assertEqual((decoded.row, decoded.col), (10, 5))

    def test_underline_row_uses_row_path(self):
        old = Screen()
        old.text(5, 0, "ONE LINK TWO")
        old.text(5, 4, "LINK", underline=True)
        new = Screen()
        new.text(5, 0, "ONE LANK TWO")
        new.text(5, 4, "LANK", underline=True)

        with patch("minitel.render.render.cell_diff_row_bytes") as cell:
            diff = render_diff(old, new, paint="cell")
        cell.assert_not_called()
        self.assertEqual(apply_diff(old, diff).text(), new.to_text())

    def test_double_size_row_uses_row_path(self):
        old = Screen()
        old.text(5, 0, "BIG", size=codec.DOUBLE_WIDTH)
        new = Screen()
        new.text(5, 0, "BAG", size=codec.DOUBLE_WIDTH)

        with patch("minitel.render.render.cell_diff_row_bytes") as cell:
            diff = render_diff(old, new, paint="cell")
        cell.assert_not_called()
        self.assertEqual(apply_diff(old, diff).text(), new.to_text())

    def test_cell_diff_rejects_barrier_rows(self):
        old = Screen()
        old.text(5, 0, "LINK", underline=True)
        new = Screen()
        new.text(5, 0, "LANK", underline=True)
        with self.assertRaises(ValueError):
            cell_diff_row_bytes(5, old.rows[5], new.rows[5])

    def test_header_cell_and_body_row_modes(self):
        old = Screen()
        old.fill(0, 0, 40, " ", inverse=True)
        old.text(0, 0, "PAGE 100", inverse=True)
        old.text(5, 0, "HELLO")
        new = Screen()
        new.fill(0, 0, 40, " ", inverse=True)
        new.text(0, 0, "PAGE 110", inverse=True)
        new.text(5, 0, "HELLX")

        diff = render_diff(
            old, new, paint="row", header_paint="cell"
        )
        self.assertNotIn(codec.pos(0, 0), diff)
        self.assertIn(codec.pos(0, 6), diff)
        self.assertIn(codec.pos(5, 0), diff)
        self.assertEqual(apply_diff(old, diff).text(), new.to_text())

    def test_render_diff_rejects_full_modes(self):
        old = Screen()
        new = Screen()
        new.text(3, 0, "X")
        with self.assertRaises(ValueError):
            render_diff(old, new, paint="full")
        with self.assertRaises(ValueError):
            render_diff(old, new, paint="row", header_paint="full")

    def test_paint_none_defaults_to_row(self):
        old = Screen()
        old.text(3, 0, "HELLO")
        new = Screen()
        new.text(3, 0, "HELLX")
        self.assertEqual(
            render_diff(old, new, paint=None),
            render_diff(old, new, paint="row"),
        )

    def test_header_paint_none_falls_back_to_paint(self):
        old = Screen()
        old.text(3, 0, "HELLO")
        new = Screen()
        new.text(3, 0, "HELLX")
        self.assertEqual(
            render_diff(old, new, paint="cell", header_paint=None),
            render_diff(old, new, paint="cell", header_paint="cell"),
        )

    def test_validate_paint(self):
        self.assertIsNone(validate_paint(None))
        self.assertEqual(validate_paint("cell"), "cell")
        with self.assertRaises(ValueError):
            validate_paint("bogus")
        with self.assertRaises(TypeError):
            validate_paint(1)
        with self.assertRaises(ValueError):
            validate_paint("full", allow_full=False)


class StyledShiftDiffTests(unittest.TestCase):
    def screens(self):
        old = Screen()
        old.fill(0, 0, 40, " ", inverse=True)
        old.text(0, 0, "PAGE 100", inverse=True)
        for row in range(1, codec.ROWS):
            old.text(row, 0, f"LINE {row:02d}AAAA")
            old.put(row, 10, "!")

        new = Screen()
        new.fill(0, 0, 40, " ", inverse=True)
        new.text(0, 0, "PAGE 110", inverse=True)
        new.rows[1:codec.ROWS - 1] = [
            [Cell(**vars(cell)) for cell in row]
            for row in old.rows[2:codec.ROWS]
        ]
        new.text(codec.ROWS - 1, 0, "NEW LAST")
        new.rows[5][5] = Cell(
            ch=old.rows[6][5].ch, inverse=True
        )
        return old, new

    def test_scroll_style_change_keeps_the_shift_fast_path(self):
        old, new = self.screens()

        diff = render_diff(old, new, scroll=True, paint="cell")
        self.assertIn(bytes([codec.LF]), diff)
        self.assertNotIn(codec.pos(5, 0), diff)
        self.assertIn(codec.pos(5, 5), diff)
        decoded = decode(render(old, scroll=True) + diff)
        self.assertEqual(decoded.text(), new.to_text())
        self.assertTrue(decoded.rows[5][5].inverse)

    def test_scroll_style_change_falls_back_for_barrier_rows(self):
        old, new = self.screens()
        new.rows[5][5].underline = True

        diff = render_diff(old, new, scroll=True, paint="cell")
        self.assertNotIn(bytes([codec.LF]), diff)
        decoded = decode(render(old, scroll=True) + diff)
        self.assertEqual(decoded.text(), new.to_text())

    def test_down_shift_style_change_keeps_the_shift_fast_path(self):
        old = Screen()
        old.fill(0, 0, 40, " ", inverse=True)
        old.text(0, 0, "PAGE 100", inverse=True)
        for row in range(1, codec.ROWS):
            old.text(row, 0, f"LINE {row:02d}AAAA")

        new = Screen()
        new.fill(0, 0, 40, " ", inverse=True)
        new.text(0, 0, "PAGE 100", inverse=True)
        new.text(1, 0, "NEW FIRST")
        new.rows[2:codec.ROWS] = [
            [Cell(**vars(cell)) for cell in row]
            for row in old.rows[1:codec.ROWS - 1]
        ]
        new.rows[5][5] = Cell(
            ch=old.rows[4][5].ch, inverse=True
        )

        diff = render_diff(old, new, scroll=True, paint="cell")
        self.assertIn(bytes([codec.VT]), diff)
        self.assertNotIn(codec.pos(5, 0), diff)
        self.assertIn(codec.pos(5, 5), diff)
        decoded = decode(render(old, scroll=True) + diff)
        self.assertEqual(decoded.text(), new.to_text())
        self.assertTrue(decoded.rows[5][5].inverse)

    def test_scroll_style_change_is_not_used_in_row_mode(self):
        old, new = self.screens()

        diff = render_diff(old, new, scroll=True)
        self.assertNotIn(bytes([codec.LF]), diff)
        decoded = decode(render(old, scroll=True) + diff)
        self.assertEqual(decoded.text(), new.to_text())

    def test_exact_shift_row_zero_uses_header_cell_mode(self):
        old = Screen()
        old.fill(0, 0, 40, " ", inverse=True)
        old.text(0, 0, "PAGE 100", inverse=True)
        for row in range(1, codec.ROWS):
            old.text(row, 0, f"LINE {row:02d}")
        new = Screen()
        new.fill(0, 0, 40, " ", inverse=True)
        new.text(0, 0, "PAGE 110", inverse=True)
        new.rows[1:codec.ROWS - 1] = [
            [Cell(**vars(cell)) for cell in row]
            for row in old.rows[2:codec.ROWS]
        ]
        new.text(codec.ROWS - 1, 0, "NEW LAST")

        diff = render_diff(
            old, new, scroll=True, paint="cell", header_paint="cell"
        )
        self.assertIn(bytes([codec.LF]), diff)
        self.assertNotIn(codec.pos(0, 0), diff)
        self.assertIn(codec.pos(0, 6), diff)
        decoded = decode(render(old, scroll=True) + diff)
        self.assertEqual(decoded.text(), new.to_text())
        self.assertTrue(all(cell.inverse for cell in decoded.rows[0]))


class ScrollDiffTests(unittest.TestCase):
    def numbered(self):
        screen = Screen()
        screen.text(0, 0, "STATUS")
        for row in range(1, codec.ROWS):
            screen.text(row, 0, f"LINE {row}")
        return screen

    def test_full_paint_asserts_scroll_mode(self):
        screen = Screen()
        self.assertIn(codec.SCROLL_ON, render(screen, scroll=True))
        self.assertIn(codec.SCROLL_OFF, render(screen, scroll=False))
        self.assertNotIn(codec.SCROLL_ON, render(screen))
        self.assertNotIn(codec.SCROLL_OFF, render(screen))

    def test_one_line_up_shift_uses_line_feed(self):
        old = self.numbered()
        new = Screen()
        new.rows[0] = old.rows[0]
        new.rows[1:codec.ROWS - 1] = old.rows[2:codec.ROWS]
        new.text(codec.ROWS - 1, 0, "NEW LINE")

        diff = render_diff(old, new, scroll=True)
        self.assertIn(bytes([codec.LF]), diff)
        self.assertLess(len(diff), len(render(new)))

        decoded = decode(render(old, scroll=True) + diff)
        self.assertEqual(decoded.text(), new.to_text())
        self.assertTrue(decoded.text().splitlines()[0].startswith("STATUS"))

    def test_one_line_down_shift_uses_vertical_tab(self):
        old = self.numbered()
        new = Screen()
        new.rows[0] = old.rows[0]
        new.rows[2:codec.ROWS] = old.rows[1:codec.ROWS - 1]
        new.text(1, 0, "NEW TOP")

        diff = render_diff(old, new, scroll=True)
        self.assertIn(bytes([codec.VT]), diff)

        decoded = decode(render(old, scroll=True) + diff)
        self.assertEqual(decoded.text(), new.to_text())

    def test_scroll_shift_can_repaint_the_status_row(self):
        old = self.numbered()
        new = Screen()
        new.text(0, 0, "NEW STATUS")
        new.rows[1:codec.ROWS - 1] = old.rows[2:codec.ROWS]
        new.text(codec.ROWS - 1, 0, "NEW LINE")

        decoded = decode(
            render(old, scroll=True) + render_diff(old, new, scroll=True)
        )
        self.assertEqual(decoded.text(), new.to_text())
        self.assertTrue(decoded.text().splitlines()[0].startswith("NEW STATUS"))

    def test_page_mode_does_not_use_the_shift_path(self):
        old = self.numbered()
        new = Screen()
        new.rows[0] = old.rows[0]
        new.rows[1:codec.ROWS - 1] = old.rows[2:codec.ROWS]
        new.text(codec.ROWS - 1, 0, "NEW LINE")

        diff = render_diff(old, new)
        self.assertNotIn(bytes([codec.LF]), diff)
        decoded = decode(render(old) + diff)
        self.assertEqual(decoded.text(), new.to_text())


class PackageSurfaceTests(unittest.TestCase):
    def test_package_render_is_the_module_and_render_screen_is_the_function(self):
        self.assertTrue(hasattr(minitel.render, "render_diff"))
        self.assertIs(
            minitel.render_screen, minitel.render.render.render_screen
        )


if __name__ == "__main__":
    unittest.main()
