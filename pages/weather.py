from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from .layout import footer, page_input, status


@page("120", title="WEATHER", aliases=("2",))
def weather(ctx):
    s = Screen()
    status(s, "PAGE 120")
    s.text(1, 0, "WEATHER", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "PARIS      12 C  CLOUDY")
    s.text(4, 0, "LYON       15 C  CLEAR")
    s.text(5, 0, "MARSEILLE  18 C  SUNNY")
    s.text(7, 0, "(DEMO DATA, NOT A FORECAST)")
    page_input(s, ctx)
    footer(s)
    return s
