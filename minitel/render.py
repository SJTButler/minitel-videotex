"""Render a Screen to a Videotex byte stream."""

from . import codec
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


def render(screen):
    out = bytearray()
    out += codec.cursor(False)
    out += reset()
    out += codec.pos(0, 0) + bytes([codec.CAN])
    out += codec.clear()
    state = default_state()
    out += reset()

    for row_index, row in enumerate(screen.rows):
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

            run = row[start:col]
            out += codec.pos(row_index, start)
            state = default_state()
            out += attr_bytes(state, run[0])
            if run[0].size != codec.NORMAL:
                out += codec.size(run[0].size)
            out += encode_run(run)
            if run[0].size != codec.NORMAL:
                out += codec.size(codec.NORMAL)

    out += codec.pos(screen.cursor_row, screen.cursor_col)
    state = default_state()
    out += codec.cursor(screen.cursor_visible)
    cell = screen.rows[screen.cursor_row][screen.cursor_col]
    out += attr_bytes(state, cell)
    if cell.size != codec.NORMAL:
        out += codec.size(cell.size)
    return bytes(out)


def render_diff(old, new):
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

    out = bytearray()
    if changed:
        out += codec.cursor(False)
    out += reset()

    state = default_state()

    for row_index in changed:
        row = new.rows[row_index]
        out += codec.pos(row_index, 0)
        state = default_state()
        out += attr_bytes(state, DEFAULT_CELL)
        out += bytes([codec.CAN])

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

            run = row[start:col]
            out += codec.pos(row_index, start)
            state = default_state()
            out += attr_bytes(state, run[0])
            if run[0].size != codec.NORMAL:
                out += codec.size(run[0].size)
            out += encode_run(run)
            if run[0].size != codec.NORMAL:
                out += codec.size(codec.NORMAL)

    out += codec.pos(new.cursor_row, new.cursor_col)
    state = default_state()
    out += codec.cursor(new.cursor_visible)
    cursor_cell = new.rows[new.cursor_row][new.cursor_col]
    out += attr_bytes(state, cursor_cell)
    if cursor_cell.size != codec.NORMAL:
        out += codec.size(cursor_cell.size)
    return bytes(out)
