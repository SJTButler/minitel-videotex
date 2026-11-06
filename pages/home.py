from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen
from minitel.text import fit

from .common.clock import clock_text
from .common.layout import footer, status
from .common.widgets import page_input

CLOCK_ROW = 3
CLOCK_COL = 24
HOME_PAGE = "100"
MENU_ROW = 5
MENU_LIMIT = 10
PROFILE_ROW = 16


def menu_entries(registry):
    entries = []
    for entry in registry.all():
        if entry.number == HOME_PAGE:
            continue
        aliases = [
            alias
            for alias in registry.aliases_for(entry)
            if isinstance(alias, str)
            and alias.isascii()
            and alias.isdigit()
            and 1 <= len(alias) <= 2
            and int(alias) > 0
        ]
        if not aliases:
            continue
        alias = min(aliases, key=int)
        entries.append((int(alias), alias, entry))
    entries.sort(key=lambda item: (item[0], item[1]))
    return entries[:MENU_LIMIT], max(0, len(entries) - MENU_LIMIT)


def clock_tick(ctx):
    return codec.pos(CLOCK_ROW, CLOCK_COL + 6) + codec.text(clock_text())


@page("100", title="3615 KILO", aliases=("", "0"),
      tick_interval=1.0, on_tick=clock_tick)
def welcome(ctx):
    entries, extra = menu_entries(ctx.registry)

    s = Screen()
    status(s, "PAGE 100")
    s.text(1, 0, "3615 KILO", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(CLOCK_ROW, CLOCK_COL, "TIME: " + clock_text())
    s.text(3, 0, "A SMALL MINITEL SERVICE")
    for index, (_, alias, entry) in enumerate(entries):
        s.text(
            MENU_ROW + index,
            0,
            f"{alias:<2} {fit(entry.title, codec.COLS - 3)}",
        )
    hint = "TYPE A NUMBER, THEN ENVOI:"
    if extra:
        hint = f"TYPE A NUMBER, THEN ENVOI  (+{extra} MORE)"
    s.text(MENU_ROW + len(entries), 0, hint[:codec.COLS])
    s.text(PROFILE_ROW, 0, "M1 PROFILE / 1200 BAUD")
    page_input(s, ctx, cursor="auto")
    footer(s)
    return s
