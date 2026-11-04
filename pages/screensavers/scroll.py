"""Page 902: a scrolling public-domain text screensaver."""

from minitel.pagemodel import page
from minitel.protocol import codec
from minitel.render import Screen

from ._support.text import LINES

PAGE_NUMBER = "902"
STATE_KEY = "shakespeare_line"
VISIBLE_ROWS = codec.ROWS - 1
TICK_SECONDS = 0.5
LOOP_GAP = 4


def _index(ctx):
    return int(ctx.state.get(STATE_KEY, 0)) % (len(LINES) + LOOP_GAP)


def _screen(ctx):
    screen = Screen()
    screen.text(0, 0, "3615 KILO / SHAKESPEARE")
    start = _index(ctx)
    for offset in range(VISIBLE_ROWS):
        index = start + offset
        if index >= len(LINES):
            break
        screen.text(1 + offset, 0, LINES[index])
    return screen


def scroll_tick(ctx):
    ctx.state[STATE_KEY] = (_index(ctx) + 1) % (len(LINES) + LOOP_GAP)
    return _screen(ctx)


@page(
    PAGE_NUMBER,
    title="SHAKESPEARE",
    screensaver="scroll",
    tick_interval=TICK_SECONDS,
    on_tick=scroll_tick,
    back_page="190",
    scroll=True,
)
def shakespeare(ctx):
    return _screen(ctx)
