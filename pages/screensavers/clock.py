from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from ..common.clock import clock_hm, clock_seconds, date_text, local_now


def _clock_screen():
    now = local_now()
    s = Screen()
    s.text(0, 0, "3615 KILO")
    s.text(4, 15, clock_hm(now), size=codec.DOUBLE_SIZE)
    s.text(7, 17, clock_seconds(now) + " SEC")
    s.text(9, 15, date_text(now))
    s.rule(11, 0, 40, "-")
    s.text(13, 0, "LOCAL TIME")
    s.text(23, 0, "PRESS ANY KEY")
    return s


def clock_tick(ctx):
    return _clock_screen()


@page("900", title="CLOCK", tick_interval=1.0, on_tick=clock_tick,
      back_page="190", screensaver="clock")
def clock(ctx):
    return _clock_screen()
