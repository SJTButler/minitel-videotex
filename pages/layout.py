"""Shared layout helpers for the example service."""

from minitel import codec

STATUS_MARGIN = 4
FIELD_ROW = 20
FIELD_COL = 6
FIELD_WIDTH = 10


def status(screen, page):
    boundary = codec.COLS - STATUS_MARGIN
    page_text = f"{page:>8}"
    line_width = boundary + 1
    title_width = max(0, line_width - len(page_text))
    line = (f"{'3615 KILO':<{title_width}}" + page_text)[:line_width]
    screen.fill(0, 0, codec.COLS, " ", inverse=True)
    screen.text(0, 0, line, inverse=True)


def footer(screen):
    screen.text(22, 0, "SOMMAIRE=ACCUEIL  RETOUR=PRECEDENT")


def page_input(screen, ctx, *, cursor="visible"):
    screen.text(FIELD_ROW, 0, "PAGE:")
    screen.field(FIELD_ROW, FIELD_COL, FIELD_WIDTH)
    ctx.set_input(FIELD_ROW, FIELD_COL, FIELD_WIDTH, cursor=cursor)
