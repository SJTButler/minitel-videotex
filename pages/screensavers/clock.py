from math import cos, pi, sin

from minitel import Screen, codec, page
from minitel_kit import MosaicCanvas

from ..common.clock import clock_hm, date_text, local_now

CLOCK_MINUTE = "clock_minute"


def _minute_key(now):
    return (
        now.tm_year,
        now.tm_mon,
        now.tm_mday,
        now.tm_hour,
        now.tm_min,
    )


def _dial(now):
    canvas = MosaicCanvas(24, 19)
    cx, cy = 23.5, 28.0
    rx, ry = 23.5, 28.0
    for index in range(12):
        angle = -pi / 2 + index * pi / 6
        inner = 0.72 if index % 3 == 0 else 0.82
        outer = 0.90
        canvas.line(
            cx + cos(angle) * rx * inner,
            cy + sin(angle) * ry * inner,
            cx + cos(angle) * rx * outer,
            cy + sin(angle) * ry * outer,
        )
    canvas.ellipse(0, 0, 47, 56)
    minute = -pi / 2 + now.tm_min * pi / 30
    hour = -pi / 2 + (
        (now.tm_hour % 12) + now.tm_min / 60
    ) * pi / 6
    canvas.line(
        cx,
        cy,
        cx + cos(hour) * rx * 0.52,
        cy + sin(hour) * ry * 0.52,
    )
    canvas.line(
        cx,
        cy,
        cx + cos(minute) * rx * 0.80,
        cy + sin(minute) * ry * 0.80,
    )
    canvas.fill(cx - 1, cy - 1, cx + 1, cy + 1)
    return canvas


def _clock_screen(now=None):
    now = local_now() if now is None else now
    s = Screen()
    s.text(0, 0, "3615 KILO")
    s.text(1, 15, clock_hm(now), size=codec.DOUBLE_WIDTH)
    _dial(now).draw(s, 3, 8)
    date = date_text(now)
    s.text(22, 0, "LOCAL TIME")
    s.text(22, codec.COLS - len(date), date)
    s.text(23, 0, "PRESS ANY KEY")
    return s


def clock_tick(ctx):
    now = local_now()
    key = _minute_key(now)
    if ctx.state.get(CLOCK_MINUTE) == key:
        return None
    ctx.state[CLOCK_MINUTE] = key
    return _clock_screen(now)


@page(
    "900",
    title="CLOCK",
    tick_interval=30.0,
    on_tick=clock_tick,
    back_page="190",
    screensaver="clock",
    paint="cell",
)
def clock(ctx):
    now = local_now()
    ctx.state[CLOCK_MINUTE] = _minute_key(now)
    return _clock_screen(now)
