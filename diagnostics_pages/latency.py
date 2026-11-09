"""980: input echo and tick latency monitor.

The page keeps a one-second heartbeat running while a field is active. If typed
characters appear in bursts after the heartbeat stalls, the server was busy in
a paced write and was not reading input.
"""

import time

from minitel.pagemodel import page
from minitel.protocol import codec
from minitel.render import Screen
from minitel.text import fit

from pages.common.layout import status
from pages.common.widgets import form_footer, line_field

PAGE = "980"
START = "latency_start"
TICKS = "latency_ticks"
EVENTS = "latency_events"
LAST_EVENT = "latency_last_event"
LAST_LINE = "latency_last_line"


def _screen(ctx):
    now = time.monotonic()
    start = ctx.state.setdefault(START, now)
    elapsed = max(0, int(now - start))
    ticks = ctx.state.get(TICKS, 0)
    events = ctx.state.get(EVENTS, 0)
    last_event = ctx.state.get(LAST_EVENT, "-")
    last_line = ctx.state.get(LAST_LINE, "-")

    s = Screen()
    status(s, f"PAGE {PAGE}")
    s.text(1, 0, "INPUT / LATENCY", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(
        3,
        0,
        fit(f"UPTIME {elapsed // 60:02d}:{elapsed % 60:02d}  TICKS {ticks}", 40),
    )
    s.text(
        4,
        0,
        fit(f"EVENTS {events}  LAST {last_event}", 40),
    )
    s.text(6, 0, "SERVER ECHOES EACH CHARACTER.")
    s.text(7, 0, "IF THE ECHO STALLS, THE SERVER IS")
    s.text(8, 0, "WRITING AND NOT READING INPUT.")
    s.text(10, 0, "TYPE BELOW, THEN ENVOI:")
    line_field(s, ctx, "probe", 11, 9, 28, label="PROBE:")
    s.text(13, 0, fit(f"LAST LINE: {last_line}", 40))
    s.text(15, 0, "GUIDE AND ARROWS ARE LOGGED.")
    s.text(17, 0, f"{PAGE} DIAGNOSTIC PAGE")
    form_footer(s, ctx, [("probe", "PROBE")])
    return s


def _record(ctx, name):
    ctx.state[EVENTS] = ctx.state.get(EVENTS, 0) + 1
    ctx.state[LAST_EVENT] = name


def submit(ctx, values):
    line = values.get("probe", "").strip()
    _record(ctx, "ENVOI")
    if line:
        ctx.state[LAST_LINE] = line
    ctx.values["probe"] = ""
    return PAGE


def on_key(ctx, key):
    _record(ctx, key)
    return PAGE


def tick(ctx):
    ctx.state[TICKS] = ctx.state.get(TICKS, 0) + 1
    return _screen(ctx)


@page(
    PAGE,
    title="INPUT LATENCY",
    form=True,
    on_form=submit,
    on_key=on_key,
    on_tick=tick,
    tick_interval=1.0,
    no_screensaver=True,
    back_page="199",
)
def latency(ctx):
    return _screen(ctx)
