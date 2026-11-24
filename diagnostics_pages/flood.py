"""981: full-paint flood.

Turn the flood on and the page forces a full 40x25 paint every tick. At the M1
serial rate one paint takes several seconds. Input is still read while writes
drain: typing echoes immediately, and SOMMAIRE abandons the stale paint and
full-paints home. Use it to watch abort and echo behaviour on the wire. The
flood auto-stops after a few passes so the terminal cannot be stranded; GUIDE
also stops it early.
"""

from minitel.pagemodel import page
from minitel.render import Screen
from minitel.text import fit

from pages.common.layout import status
from pages.common.widgets import form_footer, line_field

PAGE = "981"
FLOOD = "flood_on"
PASSES = "flood_passes"
MAX_PASSES = 3
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
    s.text(19, 0, "TYPE ON/OFF  GUIDE=STOP  3 PASSES")
    line_field(s, ctx, "mode", 20, 9, 16, label="MODE:")
    s.text(
        21,
        0,
        fit(
            f"FLOOD {'ON' if flood else 'OFF'}  "
            f"PASS {passes}/{MAX_PASSES}",
            40,
        ),
    )
    form_footer(s, ctx, [("mode", "MODE")])
    if flood:
        s.force_full = True
    return s


def submit(ctx, values):
    value = values.get("mode", "").strip().upper()
    if value in ("ON", "GO", "START", "FLOOD"):
        ctx.state[FLOOD] = True
        ctx.state[PASSES] = 0
    elif value in ("OFF", "STOP", "QUIT"):
        ctx.state[FLOOD] = False
    ctx.values["mode"] = ""
    return PAGE


def on_key(ctx, key):
    if key == "GUIDE":
        flood = not ctx.state.get(FLOOD, False)
        ctx.state[FLOOD] = flood
        if flood:
            ctx.state[PASSES] = 0
    return PAGE


def tick(ctx):
    if not ctx.state.get(FLOOD, False):
        return None
    passes = ctx.state.get(PASSES, 0) + 1
    ctx.state[PASSES] = passes
    if passes >= MAX_PASSES:
        ctx.state[FLOOD] = False
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
