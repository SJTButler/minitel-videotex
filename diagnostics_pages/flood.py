"""981: full-paint flood.

Turn the flood on and the page forces a full 40x25 paint every tick. At the M1
serial rate one paint takes several seconds, during which the server is writing
and the dongle is blocked on its UART. Use it to reproduce delayed or lost
keypresses, then press GUIDE (or submit OFF) to stop.
"""

from minitel.pagemodel import page
from minitel.render import Screen
from minitel.text import fit

from pages.common.layout import status
from pages.common.widgets import form_footer, line_field

PAGE = "981"
FLOOD = "flood_on"
PASSES = "flood_passes"
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-*/"


def _row(seed, width=40):
    return "".join(
        ALPHABET[(seed * 7 + index) % len(ALPHABET)]
        for index in range(width)
    )


def _screen(ctx):
    flood = bool(ctx.state.get(FLOOD, False))
    passes = ctx.state.get(PASSES, 0)

    s = Screen()
    status(s, f"PAGE {PAGE}")
    for row in range(1, 19):
        s.text(row, 0, _row(row + passes))
    s.text(19, 0, "TYPE ON OR OFF THEN ENVOI")
    line_field(s, ctx, "mode", 20, 9, 16, label="MODE:")
    s.text(
        21,
        0,
        fit(f"FLOOD {'ON' if flood else 'OFF'}  PASS {passes}", 40),
    )
    form_footer(s, ctx, [("mode", "MODE")])
    if flood:
        s.force_full = True
    return s


def submit(ctx, values):
    value = values.get("mode", "").strip().upper()
    if value in ("ON", "GO", "START", "FLOOD"):
        ctx.state[FLOOD] = True
    elif value in ("OFF", "STOP", "QUIT"):
        ctx.state[FLOOD] = False
    ctx.values["mode"] = ""
    return PAGE


def on_key(ctx, key):
    if key == "GUIDE":
        ctx.state[FLOOD] = not ctx.state.get(FLOOD, False)
    return PAGE


def tick(ctx):
    if not ctx.state.get(FLOOD, False):
        return None
    ctx.state[PASSES] = ctx.state.get(PASSES, 0) + 1
    return _screen(ctx)


@page(
    PAGE,
    title="FLOOD",
    form=True,
    on_form=submit,
    on_key=on_key,
    on_tick=tick,
    tick_interval=1.0,
    no_screensaver=True,
    back_page="199",
)
def flood(ctx):
    return _screen(ctx)
