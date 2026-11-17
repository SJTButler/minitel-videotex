"""Shared page layout: palette, landmarks, status, and footers."""

from minitel import codec

STATUS_MARGIN = 4
FIELD_ROW = 20
FIELD_COL = 6
FIELD_WIDTH = 10

BODY = codec.WHITE
ACCENT = codec.YELLOW
SECONDARY = codec.CYAN
WARNING = codec.MAGENTA


def status(screen, page):
    boundary = codec.COLS - STATUS_MARGIN
    page_text = f"{page:>8}"
    line_width = boundary + 1
    title_width = max(0, line_width - len(page_text))
    line = (f"{'3615 KILO':<{title_width}}" + page_text)[:line_width]
    screen.fill(0, 0, codec.COLS, " ", inverse=True)
    screen.text(0, 0, line, inverse=True)


def key_footer(screen, hints, row=22):
    if isinstance(hints, str):
        line = hints
    else:
        line = "  ".join(hints)
    screen.text(row, 0, line[:codec.COLS])


def footer(screen):
    key_footer(screen, ("SOMMAIRE=HOME", "RETOUR=BACK"))
