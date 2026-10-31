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


def form_footer(screen):
    screen.text(22, 0, "SUITE: CHAMP  RETOUR: PREC/SORTIE")
    screen.text(23, 0, "ENVOI: VALIDER  SOMMAIRE: ACCUEIL")


def line_field(screen, ctx, name, row, col, width, *, label=None,
               label_col=0, value="", cursor="visible"):
    if label:
        screen.text(row, label_col, label)
    screen.field(row, col, width)
    current = ctx.values.get(name, value)
    if current:
        screen.text(row, col, current[:width], inverse=True)
    return ctx.add_field(
        name, row, col, width, value=value, cursor=cursor
    )


def page_input(screen, ctx, *, cursor="visible"):
    screen.text(FIELD_ROW, 0, "PAGE:")
    screen.field(FIELD_ROW, FIELD_COL, FIELD_WIDTH)
    ctx.set_input(FIELD_ROW, FIELD_COL, FIELD_WIDTH, cursor=cursor)
