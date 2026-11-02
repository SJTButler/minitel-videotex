from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen

from .common.layout import footer, status
from .common.widgets import page_input


@page("130", title="ABOUT", aliases=("3",))
def about(ctx):
    s = Screen()
    status(s, "PAGE 130")
    s.text(1, 0, "ABOUT", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "3615 KILO IS A")
    s.text(4, 0, "PRESTEL-STYLE SERVICE")
    s.text(5, 0, "FOR A MINITEL 1.")
    s.text(7, 0, "BUILT WITH PYTHON.")
    page_input(s, ctx)
    footer(s)
    return s
