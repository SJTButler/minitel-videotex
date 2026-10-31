from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from .layout import footer, page_input, status


@page("100", title="3615 KILO", aliases=("", "0"))
def welcome(ctx):
    s = Screen()
    status(s, "PAGE 100")
    s.text(1, 0, "3615 KILO", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "A SMALL MINITEL SERVICE")
    s.text(5, 0, "1  NEWS")
    s.text(6, 0, "2  WEATHER")
    s.text(7, 0, "3  ABOUT")
    s.text(9, 0, "TYPE A NUMBER, THEN ENVOI:")
    s.text(16, 0, "M1 PROFILE / 1200 BAUD")
    page_input(s, ctx)
    footer(s)
    return s
