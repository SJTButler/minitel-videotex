"""Render a Screen to a Videotex byte stream."""

from ..protocol import codec
from .screen import Cell

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


def paint_runs(out, row_index, row):
    col = 0
    while col < codec.COLS:
        cell = row[col]
        if cell.ch == " " and attrs(cell) == DEFAULT_ATTRS:
            col += 1
            continue

        start = col
        run_attrs = attrs(cell)
        while col < codec.COLS and attrs(row[col]) == run_attrs:
            col += 1

        end = col
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


def diff_row_bytes(row_index, row):
    out = bytearray()
    out += codec.pos(row_index, 0)
    state = default_state()
    out += attr_bytes(state, DEFAULT_CELL)
    out += bytes([codec.CAN])
    paint_runs(out, row_index, row)
    return bytes(out)


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


def render(screen, scroll=None):
    out = bytearray()
    out += codec.cursor(False)
    out += reset()
    out += codec.pos(0, 0) + bytes([codec.CAN])
    out += codec.clear()
    if scroll is not None:
        out += codec.scroll_mode(scroll)
    out += reset()

    for row_index, row in enumerate(screen.rows):
        paint_runs(out, row_index, row)

    out += cursor_bytes(screen)
    return bytes(out)


def render_diff(old, new, scroll=False):
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

    shifted = shift_delta(old, new) if scroll and changed else None

    out = bytearray()
    if changed:
        out += codec.cursor(False)
    out += reset()

    if shifted is not None:
        direction, count = shifted
        if direction == "up":
            out += codec.pos(codec.ROWS - 1, 0)
            out += reset()
            out += bytes([codec.LF]) * count
            for row_index in range(codec.ROWS - count, codec.ROWS):
                out += diff_row_bytes(row_index, new.rows[row_index])
        else:
            out += codec.pos(1, 0)
            out += reset()
            out += bytes([codec.VT]) * count
            for row_index in range(1, 1 + count):
                out += diff_row_bytes(row_index, new.rows[row_index])
        if old.rows[0] != new.rows[0]:
            out += diff_row_bytes(0, new.rows[0])
    else:
        for row_index in changed:
            out += diff_row_bytes(row_index, new.rows[row_index])

    out += cursor_bytes(new)
    return bytes(out)


render_screen = render
