import time

from minitel import codec
from minitel.pages import page
from minitel.screen import Screen


def _clock_screen():
    now = time.localtime()
    s = Screen()
    s.text(0, 0, "3615 KILO")
    s.text(4, 15, time.strftime("%H:%M", now), size=codec.DOUBLE_SIZE)
    s.text(7, 17, time.strftime("%S", now) + " SEC")
    s.text(9, 15, time.strftime("%d/%m/%Y", now))
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
