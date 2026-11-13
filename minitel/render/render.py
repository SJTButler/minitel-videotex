"""Render a Screen to a Videotex byte stream."""

from ..protocol import codec
from .screen import Cell, validate_paint

DEFAULT_ATTRS = (codec.WHITE, codec.BLACK, False, False, False, codec.NORMAL)
DEFAULT_CELL = Cell()


def default_state():
    return {
        "fg": codec.WHITE,
        "bg": codec.BLACK,
        "inverse": False,
        "flash": False,
        "underline": False,
    }


def attrs(cell):
    return (cell.fg, cell.bg, cell.inverse, cell.flash, cell.underline, cell.size)


def reset():
    return b"".join([
        codec.fg(codec.WHITE),
        codec.bg(codec.BLACK),
        codec.inverse(False),
        codec.flash(False),
        codec.underline(False),
        codec.size(codec.NORMAL),
    ])


def attr_bytes(state, cell):
    out = bytearray()
    if cell.fg != state["fg"]:
        out += codec.fg(cell.fg)
        state["fg"] = cell.fg
    if cell.bg != state["bg"]:
        out += codec.bg(cell.bg)
        state["bg"] = cell.bg
    if cell.inverse != state["inverse"]:
        out += codec.inverse(cell.inverse)
        state["inverse"] = cell.inverse
    if cell.flash != state["flash"]:
        out += codec.flash(cell.flash)
        state["flash"] = cell.flash
    if cell.underline != state["underline"]:
        out += codec.underline(cell.underline)
        state["underline"] = cell.underline
    return bytes(out)


def encode_run(run):
    out = bytearray()
    i = 0
    while i < len(run):
        ch = run[i].ch
        j = i
        while j < len(run) and run[j].ch == ch:
            j += 1
        count = j - i
        if count >= 3:
            out += codec.repeat(ch, count)
        else:
            out += codec.text(ch * count)
        i = j
    return bytes(out)


SCROLL_MAX = 8


def paint_runs(out, row_index, row, *, include_default=False):
    col = 0
    while col < codec.COLS:
        cell = row[col]
        if (
            not include_default
            and cell.ch == " "
            and attrs(cell) == DEFAULT_ATTRS
        ):
            col += 1
            continue

        start = col
        run_attrs = attrs(cell)
        while col < codec.COLS and attrs(row[col]) == run_attrs:
            col += 1

        end = col
        if not include_default:
            while (
                end > start
                and row[end - 1].ch == " "
                and attrs(row[end - 1]) == DEFAULT_ATTRS
            ):
                end -= 1
            if end == start:
                continue

        run = row[start:end]
        out += codec.pos(row_index, start)
        state = default_state()
        out += attr_bytes(state, run[0])
        if run[0].size != codec.NORMAL:
            out += codec.size(run[0].size)
        out += encode_run(run)
        if run[0].size != codec.NORMAL:
            out += codec.size(codec.NORMAL)
        if run[0].underline:
            out += codec.underline(False)


def _row_has_underline(row):
    return any(cell.underline for cell in row)


def _row_has_non_normal_size(row):
    return any(cell.size != codec.NORMAL for cell in row)


def _is_default(cell):
    return cell == DEFAULT_CELL


def cell_diff_row_bytes(row_index, old_row, new_row):
    if (
        _row_has_underline(old_row)
        or _row_has_underline(new_row)
        or _row_has_non_normal_size(old_row)
        or _row_has_non_normal_size(new_row)
    ):
        raise ValueError(
            "cell diff requires a row without underline or non-normal size"
        )

    changed = [
        col for col in range(codec.COLS)
        if old_row[col] != new_row[col]
    ]
    if not changed:
        return b""

    tail_start = codec.COLS
    for col in range(codec.COLS - 1, -1, -1):
        if _is_default(new_row[col]):
            tail_start = col
        else:
            break
    clear_start = next(
        (col for col in changed if col >= tail_start), None
    )

    out = bytearray()
    limit = clear_start if clear_start is not None else codec.COLS
    index = 0
    while index < len(changed) and changed[index] < limit:
        start = changed[index]
        run_attrs = attrs(new_row[start])
        cols = [start]
        index += 1
        while (
            index < len(changed)
            and changed[index] == cols[-1] + 1
            and changed[index] < limit
            and attrs(new_row[changed[index]]) == run_attrs
        ):
            cols.append(changed[index])
            index += 1
        out += codec.pos(row_index, start)
        state = default_state()
        out += attr_bytes(state, new_row[start])
        out += encode_run([new_row[col] for col in cols])

    if clear_start is not None:
        out += codec.pos(row_index, clear_start)
        out += bytes([codec.CAN])
    return bytes(out)


def diff_row_bytes(row_index, row, *, full=False):
    out = bytearray()
    out += codec.pos(row_index, 0)
    state = default_state()
    out += attr_bytes(state, DEFAULT_CELL)
    if not full:
        out += bytes([codec.CAN])
    paint_runs(out, row_index, row, include_default=full)
    return bytes(out)


def paint_diff_row(out, row_index, old_row, new_row, *, paint, header_paint):
    mode = header_paint if row_index == 0 else paint
    underline = (
        _row_has_underline(old_row) or _row_has_underline(new_row)
    )
    sized = (
        _row_has_non_normal_size(old_row)
        or _row_has_non_normal_size(new_row)
    )
    if mode == "cell" and not underline and not sized:
        out += cell_diff_row_bytes(row_index, old_row, new_row)
        return
    out += diff_row_bytes(row_index, new_row, full=underline)


def cursor_bytes(screen):
    out = bytearray()
    out += codec.pos(screen.cursor_row, screen.cursor_col)
    state = default_state()
    out += codec.cursor(screen.cursor_visible)
    cell = screen.rows[screen.cursor_row][screen.cursor_col]
    out += attr_bytes(state, cell)
    if cell.size != codec.NORMAL:
        out += codec.size(cell.size)
    return bytes(out)


def shift_delta(old, new):
    """Return (direction, lines) when rows 1-24 are a vertical shift."""
    for count in range(1, min(SCROLL_MAX, codec.ROWS - 1) + 1):
        if new.rows[1:codec.ROWS - count] == old.rows[1 + count:codec.ROWS]:
            return "up", count
        if new.rows[1 + count:codec.ROWS] == old.rows[1:codec.ROWS - count]:
            return "down", count
    return None


def _row_chars(row):
    return tuple(cell.ch for cell in row)


def shift_delta_chars(old, new):
    """Return a vertical shift when only characters are compared."""
    for count in range(1, min(SCROLL_MAX, codec.ROWS - 1) + 1):
        if (
            tuple(_row_chars(row) for row in new.rows[1:codec.ROWS - count])
            == tuple(_row_chars(row) for row in old.rows[1 + count:codec.ROWS])
        ):
            return "up", count
        if (
            tuple(_row_chars(row) for row in new.rows[1 + count:codec.ROWS])
            == tuple(_row_chars(row) for row in old.rows[1:codec.ROWS - count])
        ):
            return "down", count
    return None


def _shift_pairs(direction, count):
    """Return (target, source) row pairs for the overlapping rows."""
    if direction == "up":
        return tuple(
            (row, row + count)
            for row in range(1, codec.ROWS - count)
        )
    return tuple(
        (row, row - count)
        for row in range(1 + count, codec.ROWS)
    )


def _style_shift_supported(old, new, shifted):
    direction, count = shifted
    for target, source in _shift_pairs(direction, count):
        old_row = old.rows[source]
        new_row = new.rows[target]
        if old_row == new_row:
            continue
        if (
            _row_has_underline(old_row)
            or _row_has_underline(new_row)
            or _row_has_non_normal_size(old_row)
            or _row_has_non_normal_size(new_row)
        ):
            return False
    return True


def _paint_shift(out, old, new, shifted, *, paint, header_paint,
                 style_changes):
    direction, count = shifted
    if direction == "up":
        out += codec.pos(codec.ROWS - 1, 0)
        out += reset()
        out += bytes([codec.LF]) * count
        for row_index in range(codec.ROWS - count, codec.ROWS):
            underline = (
                _row_has_underline(old.rows[row_index])
                or _row_has_underline(new.rows[row_index])
            )
            out += diff_row_bytes(
                row_index, new.rows[row_index], full=underline
            )
    else:
        out += codec.pos(1, 0)
        out += reset()
        out += bytes([codec.VT]) * count
        for row_index in range(1, 1 + count):
            underline = (
                _row_has_underline(old.rows[row_index])
                or _row_has_underline(new.rows[row_index])
            )
            out += diff_row_bytes(
                row_index, new.rows[row_index], full=underline
            )

    if style_changes:
        for target, source in _shift_pairs(direction, count):
            old_row = old.rows[source]
            new_row = new.rows[target]
            if old_row != new_row:
                out += cell_diff_row_bytes(target, old_row, new_row)

    if old.rows[0] != new.rows[0]:
        paint_diff_row(
            out, 0, old.rows[0], new.rows[0],
            paint=paint, header_paint=header_paint,
        )


def render(screen, scroll=None):
    out = bytearray()
    out += codec.cursor(False)
    out += reset()
    out += codec.pos(0, 0) + bytes([codec.CAN])
    out += codec.clear()
    if scroll is not None:
        out += codec.scroll_mode(scroll)
    out += reset()

    if getattr(screen, "paint_order", "down") == "up":
        rows = [0] + list(range(codec.ROWS - 1, 0, -1))
    else:
        rows = range(codec.ROWS)
    for row_index in rows:
        paint_runs(out, row_index, screen.rows[row_index])

    out += cursor_bytes(screen)
    return bytes(out)


def render_diff(old, new, scroll=False, *, paint="row", header_paint=None):
    if paint is None:
        paint = "row"
    paint = validate_paint(paint, allow_full=False, what="paint")
    if header_paint is None:
        header_paint = paint
    else:
        header_paint = validate_paint(
            header_paint, allow_full=False, what="header_paint"
        )

    changed = [
        row for row in range(codec.ROWS)
        if old.rows[row] != new.rows[row]
    ]
    cursor_changed = (
        old.cursor_row != new.cursor_row
        or old.cursor_col != new.cursor_col
        or old.cursor_visible != new.cursor_visible
    )
    if not changed and not cursor_changed:
        return b""

    exact_shift = shift_delta(old, new) if scroll and changed else None
    style_shift = None
    if (
        scroll
        and changed
        and exact_shift is None
        and paint == "cell"
    ):
        candidate = shift_delta_chars(old, new)
        if candidate is not None and _style_shift_supported(
            old, new, candidate
        ):
            style_shift = candidate

    out = bytearray()
    if changed:
        out += codec.cursor(False)
    out += reset()

    if exact_shift is not None:
        _paint_shift(
            out, old, new, exact_shift,
            paint=paint, header_paint=header_paint, style_changes=False,
        )
    elif style_shift is not None:
        _paint_shift(
            out, old, new, style_shift,
            paint=paint, header_paint=header_paint, style_changes=True,
        )
    else:
        for row_index in changed:
            paint_diff_row(
                out, row_index,
                old.rows[row_index], new.rows[row_index],
                paint=paint, header_paint=header_paint,
            )

    out += cursor_bytes(new)
    return bytes(out)


render_screen = render
