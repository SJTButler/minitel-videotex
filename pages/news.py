from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from .layout import footer, page_input, status


@page("110", title="NEWS", aliases=("1",))
def news(ctx):
    s = Screen()
    status(s, "PAGE 110")
    s.text(1, 0, "NEWS", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "THE MINITEL TURNS 45.")
    s.text(4, 0, "FRANCE TELECOM SHIPPED")
    s.text(5, 0, "MILLIONS OF TERMINALS.")
    s.text(7, 0, "TODAY: A SMALL SERVER")
    s.text(8, 0, "IN A SPARE ROOM.")
    page_input(s, ctx)
    footer(s)
    return s
